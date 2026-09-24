"""Reading a repository and moving tasks along (app.services.github_sync).

GitHub itself is never called: every test supplies the commits and pull requests it
would have returned, so these run offline and deterministically.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.task import Task, TaskGithubLink
from app.services.github_sync import normalise_repo, short_ref, sync_project

pytestmark = pytest.mark.mvp


def fake_github(commits=(), pulls=()):
    async def fetch(path: str, params: dict):
        return list(commits) if path.endswith("/commits") else list(pulls)

    return fetch


def commit(sha, message, login="octocat", date="2026-09-01T10:00:00Z"):
    return {"sha": sha, "html_url": f"https://github.com/o/r/commit/{sha}",
            "author": {"login": login}, "commit": {"message": message, "author": {"date": date}}}


def pull(number, title, branch="work", body="", merged=False, state="open"):
    return {"number": number, "title": title, "body": body, "state": "closed" if merged else state,
            "merged_at": "2026-09-02T12:00:00Z" if merged else None, "created_at": "2026-09-01T09:00:00Z",
            "html_url": f"https://github.com/o/r/pull/{number}", "user": {"login": "octocat"},
            "head": {"ref": branch}}


async def make_task(db_session, project, user, title="Fix the reconnect loop", status="backlog"):
    task = Task(project_id=project.id, reporter_id=user.id, title=title, status=status)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


class TestRepositoryNames:
    def test_accepts_a_name_or_a_link(self):
        assert normalise_repo("apache/mesos") == "apache/mesos"
        assert normalise_repo(" https://github.com/apache/mesos ") == "apache/mesos"
        assert normalise_repo("github.com/apache/mesos.git") == "apache/mesos"
        assert normalise_repo("") is None
        assert normalise_repo(None) is None

    def test_rejects_anything_else(self):
        for bad in ("mesos", "https://gitlab.com/a/b", "a/b/c", "/mesos", "apache/"):
            with pytest.raises(ValueError):
                normalise_repo(bad)


class TestSync:
    async def test_a_commit_naming_a_task_starts_it_and_leaves_evidence(self, db_session, test_project, test_user):
        task = await make_task(db_session, test_project, test_user)
        test_project.github_repo = "apache/mesos"
        message = f"{short_ref(task.id)} rework the retry loop"

        result = await sync_project(db_session, test_project, fetch=fake_github(commits=[commit("a" * 40, message)]))

        await db_session.refresh(task)
        assert task.status == "in_progress"
        assert task.started_at is not None
        assert result["commits_matched"] == 1 and result["links_added"] == 1
        assert result["tasks_moved"][0]["from"] == "backlog" and result["tasks_moved"][0]["to"] == "in_progress"
        link = (await db_session.execute(select(TaskGithubLink).where(TaskGithubLink.task_id == task.id))).scalar_one()
        assert link.kind == "commit" and link.author_login == "octocat"
        assert link.url.endswith("a" * 40)

    async def test_an_imported_task_is_found_by_its_key(self, db_session, test_project, test_user):
        task = await make_task(db_session, test_project, test_user, title="MESOS-8383: Fix the agent reconnect loop")
        test_project.github_repo = "apache/mesos"

        await sync_project(db_session, test_project,
                           fetch=fake_github(commits=[commit("b" * 40, "MESOS-8383 stop the loop")]))

        await db_session.refresh(task)
        assert task.status == "in_progress"

    async def test_an_open_pull_request_sends_it_to_review_and_a_merge_finishes_it(
        self, db_session, test_project, test_user
    ):
        task = await make_task(db_session, test_project, test_user, status="in_progress")
        test_project.github_repo = "apache/mesos"
        branch = f"feature/{short_ref(task.id)}-retry"

        await sync_project(db_session, test_project, fetch=fake_github(pulls=[pull(7, "Retry loop", branch)]))
        await db_session.refresh(task)
        assert task.status == "review"

        result = await sync_project(db_session, test_project,
                                    fetch=fake_github(pulls=[pull(7, "Retry loop", branch, merged=True)]))
        await db_session.refresh(task)
        assert task.status == "done" and task.completed_at is not None
        # The same pull request is one link, however often it is read.
        assert result["links_added"] == 0
        links = (await db_session.execute(select(TaskGithubLink).where(TaskGithubLink.task_id == task.id))).scalars().all()
        assert len(links) == 1

    async def test_it_never_moves_a_task_backwards(self, db_session, test_project, test_user):
        task = await make_task(db_session, test_project, test_user, status="done")
        test_project.github_repo = "apache/mesos"

        result = await sync_project(db_session, test_project, fetch=fake_github(
            commits=[commit("c" * 40, f"{short_ref(task.id)} one more fix")],
            pulls=[pull(9, f"Another go at {short_ref(task.id)}")]))

        await db_session.refresh(task)
        assert task.status == "done"
        assert result["tasks_moved"] == []
        assert result["links_added"] == 2  # the evidence is still recorded

    async def test_work_naming_nothing_is_ignored(self, db_session, test_project, test_user):
        task = await make_task(db_session, test_project, test_user)
        test_project.github_repo = "apache/mesos"

        result = await sync_project(db_session, test_project, fetch=fake_github(
            commits=[commit("d" * 40, "tidy up the README"), commit("e" * 40, "deadbeef is not a task here")],
            pulls=[pull(3, "Bump dependencies")]))

        await db_session.refresh(task)
        assert task.status == "backlog"
        assert result["commits_read"] == 2 and result["commits_matched"] == 0
        assert result["links_added"] == 0

    async def test_a_project_with_no_repository_is_refused(self, db_session, test_project):
        test_project.github_repo = None
        with pytest.raises(ValueError):
            await sync_project(db_session, test_project, fetch=fake_github())


class TestEndpoint:
    async def test_the_repository_is_saved_normalised_and_bad_ones_refused(
        self, client: AsyncClient, auth_headers, test_project
    ):
        url = f"/api/v1/projects/{test_project.id}"
        saved = await client.patch(url, json={"github_repo": "https://github.com/apache/mesos"}, headers=auth_headers)
        assert saved.status_code == 200
        assert saved.json()["github_repo"] == "apache/mesos"
        assert (await client.patch(url, json={"github_repo": "not a repo"}, headers=auth_headers)).status_code == 422

    async def test_sync_without_a_repository_says_so(self, client: AsyncClient, auth_headers, test_project):
        response = await client.post(f"/api/v1/projects/{test_project.id}/github/sync", headers=auth_headers)
        assert response.status_code == 400
        assert "repository" in response.json()["detail"].lower()

    async def test_a_viewer_cannot_sync(self, client: AsyncClient, user_with_role, test_project):
        headers = await user_with_role("viewer")
        response = await client.post(f"/api/v1/projects/{test_project.id}/github/sync", headers=headers)
        assert response.status_code == 403

    async def test_a_task_carries_the_reference_people_write_in_branch_names(
        self, client: AsyncClient, auth_headers, test_project
    ):
        created = await client.post(f"/api/v1/projects/{test_project.id}/tasks",
                                    json={"title": "Wire the sync"}, headers=auth_headers)
        assert created.status_code == 201
        body = created.json()
        assert body["reference"] == short_ref(body["id"])

    async def test_a_person_can_record_their_github_handle(self, client: AsyncClient, auth_headers):
        updated = await client.patch("/api/v1/auth/me", json={"github_username": "octocat"}, headers=auth_headers)
        assert updated.status_code == 200
        assert updated.json()["github_username"] == "octocat"
        bad = await client.patch("/api/v1/auth/me", json={"github_username": "not a handle!"}, headers=auth_headers)
        assert bad.status_code == 422
