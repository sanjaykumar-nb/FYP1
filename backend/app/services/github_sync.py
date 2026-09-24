"""Read a project's GitHub repository and move its tasks along accordingly.

What it does, and deliberately no more:

- Reads the repository's recent commits and pull requests (public repos need no
  credentials; a read-only token raises the rate limit and reaches private ones).
- Matches each one to a task by what the author wrote: a task key like `MESOS-8383`
  at the start of the task's title, or the task's short reference (the first eight
  characters of its id, as the task dialog shows it) in a branch name, commit message
  or pull-request title or body.
- Records what it found as a link on the task — who wrote it, when, and where to read
  it — so every change it makes can be checked against the real thing.
- Moves the task forward only: a commit starts work, an open pull request sends it to
  review, a merged one finishes it. It never moves a task backwards and never reopens
  a task someone has closed.

It does not write to GitHub, create tasks, or reassign anyone.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Awaitable, Callable, Iterable, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.project import Project
from app.models.task import Task, TaskGithubLink

settings = get_settings()

# "owner/name", or a GitHub URL to normalise into one.
REPO = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")
REPO_URL = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([^/\s]+/[^/\s#?]+?)(?:\.git)?/?$", re.I)
TASK_KEY = re.compile(r"\b([A-Z][A-Z0-9]{0,9}-\d+)\b")
SHORT_REF = re.compile(r"\b([0-9a-f]{8})\b", re.I)

# How far a task can be pushed. A task only ever moves down this list, never up.
ORDER = ["backlog", "planned", "in_progress", "blocked", "review", "done"]
PAGE = 100  # recent history is what matters; one page of each is plenty


class GitHubUnavailable(RuntimeError):
    """GitHub could not be read — bad repository, rate limit, or no access."""


def normalise_repo(value: Optional[str]) -> Optional[str]:
    """Accept "owner/name" or a GitHub URL; return "owner/name"."""
    if value is None:
        return None
    text = value.strip().rstrip("/")
    if not text:
        return None
    url = REPO_URL.match(text)
    if url:
        text = url.group(1)
    if text.endswith(".git"):
        text = text[:-4]
    if not REPO.match(text):
        raise ValueError('Use "owner/repository", or a github.com link to it')
    return text


def short_ref(task_id) -> str:
    """The handle a person can type in a branch name: the first eight characters of the id."""
    return str(task_id).replace("-", "")[:8]


async def _fetch(path: str, params: dict) -> list:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "teamsync-ai",
               "X-GitHub-Api-Version": "2022-11-28"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    async with httpx.AsyncClient(base_url=settings.GITHUB_API_URL, timeout=30, headers=headers) as http:
        response = await http.get(path, params=params)
    if response.status_code == 404:
        raise GitHubUnavailable("Repository not found. Check the name, and add a token if it is private.")
    if response.status_code in (401, 403, 429):
        limited = response.headers.get("x-ratelimit-remaining") == "0"
        raise GitHubUnavailable(
            "GitHub's rate limit is spent; set GITHUB_TOKEN or wait for it to reset."
            if limited else "GitHub refused the request. Check GITHUB_TOKEN and that it can read this repository.")
    if response.status_code >= 400:
        raise GitHubUnavailable(f"GitHub returned {response.status_code}.")
    return response.json()


def _mentions(task_index: dict[str, Task], *texts: Optional[str]) -> list[Task]:
    """Every task named in these texts, by task key or by short reference."""
    found, seen = [], set()
    for text in texts:
        for pattern in (TASK_KEY, SHORT_REF):
            for token in pattern.findall(text or ""):
                task = task_index.get(token.lower())
                if task is not None and task.id not in seen:
                    seen.add(task.id)
                    found.append(task)
    return found


def _index(tasks: Iterable[Task]) -> dict[str, Task]:
    """Tasks by every handle a person might write: their key, and their short reference.

    A handle shared by two tasks is dropped rather than guessed at.
    """
    index: dict[str, Task] = {}
    clashes: set[str] = set()
    for task in tasks:
        handles = {short_ref(task.id).lower()}
        key = TASK_KEY.match((task.title or "").split(":", 1)[0].strip())
        if key:
            handles.add(key.group(1).lower())
        for handle in handles:
            if handle in index and index[handle].id != task.id:
                clashes.add(handle)
            index[handle] = task
    for handle in clashes:
        index.pop(handle, None)
    return index


def _advance(task: Task, to: str) -> Optional[str]:
    """Move the task forward to `to`, if that is forward. Returns the old status, or None."""
    current = task.status if task.status in ORDER else "backlog"
    if ORDER.index(to) <= ORDER.index(current):
        return None
    task.status = to
    now = datetime.now(timezone.utc)
    if to in ("in_progress", "review") and task.started_at is None:
        task.started_at = now
    if to == "done" and task.completed_at is None:
        task.completed_at = now
    return current


def _when(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def sync_project(
    db: AsyncSession, project: Project,
    fetch: Callable[[str, dict], Awaitable[list]] = _fetch,
) -> dict:
    """Read the repository and apply what it says to this project's tasks."""
    repo = normalise_repo(project.github_repo)
    if not repo:
        raise ValueError("This project has no GitHub repository set.")

    tasks = (await db.execute(select(Task).where(Task.project_id == project.id))).scalars().all()
    index = _index(tasks)
    existing = {
        (link.task_id, link.kind, link.ref)
        for link in (await db.execute(
            select(TaskGithubLink).join(Task, Task.id == TaskGithubLink.task_id)
            .where(Task.project_id == project.id))).scalars().all()
    }

    commits = await fetch(f"/repos/{repo}/commits", {"per_page": PAGE})
    pulls = await fetch(f"/repos/{repo}/pulls", {"state": "all", "per_page": PAGE,
                                                 "sort": "updated", "direction": "desc"})

    moved: list[dict] = []
    links_added = 0
    matched_commits = matched_pulls = 0

    def link(task: Task, kind: str, ref: str, url: str, title: str, login: Optional[str],
             state: Optional[str], when: Optional[datetime]) -> None:
        nonlocal links_added
        if (task.id, kind, ref) in existing:
            return
        existing.add((task.id, kind, ref))
        db.add(TaskGithubLink(task_id=task.id, kind=kind, ref=ref, url=url, title=title[:500],
                              author_login=login, state=state, authored_at=when))
        links_added += 1

    def move(task: Task, to: str, because: str) -> None:
        was = _advance(task, to)
        if was:
            moved.append({"task_id": str(task.id), "title": task.title, "from": was, "to": to, "because": because})

    for commit in commits:
        info = (commit.get("commit") or {})
        message = info.get("message") or ""
        named = _mentions(index, message)
        if not named:
            continue
        matched_commits += 1
        author = (commit.get("author") or {}).get("login")
        when = _when(((info.get("author") or {}).get("date")))
        for task in named:
            link(task, "commit", (commit.get("sha") or "")[:40], commit.get("html_url") or "",
                 message.splitlines()[0] if message else "(no message)", author, None, when)
            move(task, "in_progress", f"commit {(commit.get('sha') or '')[:7]}")

    for pull in pulls:
        head = ((pull.get("head") or {}).get("ref")) or ""
        named = _mentions(index, pull.get("title"), pull.get("body"), head)
        if not named:
            continue
        matched_pulls += 1
        merged = bool(pull.get("merged_at"))
        state = "merged" if merged else (pull.get("state") or "open")
        author = (pull.get("user") or {}).get("login")
        when = _when(pull.get("merged_at") or pull.get("created_at"))
        for task in named:
            link(task, "pull_request", str(pull.get("number")), pull.get("html_url") or "",
                 pull.get("title") or f"pull request #{pull.get('number')}", author, state, when)
            if merged:
                move(task, "done", f"pull request #{pull.get('number')} merged")
            elif state == "open":
                move(task, "review", f"pull request #{pull.get('number')} open")

    await db.commit()
    return {
        "repository": repo,
        "commits_read": len(commits), "commits_matched": matched_commits,
        "pull_requests_read": len(pulls), "pull_requests_matched": matched_pulls,
        "links_added": links_added,
        "tasks_moved": moved,
    }
