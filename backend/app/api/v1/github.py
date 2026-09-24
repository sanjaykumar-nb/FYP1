"""Reading a project's GitHub repository: sync, and what it linked.

The sync itself is app.services.github_sync; this exposes it, checks the caller may
change tasks, and turns GitHub being unreachable into a clear message rather than a 500.
"""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_id, get_db, require_permission
from app.models.project import Project
from app.models.task import Task, TaskGithubLink
from app.schemas.github import (
    GithubLinkResponse,
    GithubSyncResult,
    GithubWebhookReceipt,
    GithubWebhookSecret,
)
from app.services.github_sync import (
    GitHubUnavailable,
    apply_event,
    new_webhook_secret,
    signature_matches,
    sync_project,
)

router = APIRouter()


async def _project(db: AsyncSession, project_id: UUID, org_id: UUID) -> Project:
    project = (await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("/sync", response_model=GithubSyncResult,
             dependencies=[Depends(require_permission("task:update"))])
async def sync_with_github(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    """Read the repository's recent commits and pull requests and move tasks along."""
    project = await _project(db, project_id, org_id)
    try:
        return await sync_project(db, project)
    except ValueError as exc:  # no repository set, or an unusable one
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except GitHubUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.get("/links", response_model=list[GithubLinkResponse])
async def list_github_links(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    """Every commit and pull request linked to this project's tasks, newest first."""
    await _project(db, project_id, org_id)
    rows = (await db.execute(
        select(TaskGithubLink).join(Task, Task.id == TaskGithubLink.task_id)
        .where(Task.project_id == project_id)
        .order_by(TaskGithubLink.authored_at.desc().nullslast(), TaskGithubLink.created_at.desc())
    )).scalars().all()
    return rows


@router.post("/webhook-secret", response_model=GithubWebhookSecret,
             dependencies=[Depends(require_permission("project:update"))])
async def create_webhook_secret(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    """Make a new secret for this project's webhook, and show it once.

    It is shown here and never again: the API only ever reports whether one exists.
    Making a new one replaces the old, so GitHub must be given the new one.
    """
    project = await _project(db, project_id, org_id)
    project.github_webhook_secret = new_webhook_secret()
    await db.commit()
    return GithubWebhookSecret(
        secret=project.github_webhook_secret,
        path=f"/api/v1/projects/{project_id}/github/webhook",
        events=["push", "pull_request"],
    )


@router.delete("/webhook-secret", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_permission("project:update"))])
async def delete_webhook_secret(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    """Stop accepting webhook calls for this project."""
    project = await _project(db, project_id, org_id)
    project.github_webhook_secret = None
    await db.commit()


@router.post("/webhook", response_model=GithubWebhookReceipt)
async def receive_webhook(project_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """Receive one event from GitHub and apply it.

    This is the one write path with no role check: GitHub has no account here. Instead
    every request must carry a signature made with this project's own secret, and a
    request without a good one is refused before its body is looked at.
    """
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    body = await request.body()
    if project is None or not signature_matches(project.github_webhook_secret, body,
                                                request.headers.get("X-Hub-Signature-256")):
        # The same answer either way: an unsigned caller learns nothing about the project.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature does not match")

    event = request.headers.get("X-GitHub-Event", "")
    if event == "ping":
        return GithubWebhookReceipt(event=event, applied=False, detail="Webhook reached the project.")
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Body is not JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Body is not an object")

    result = await apply_event(db, project, event, payload)
    if result is None:
        return GithubWebhookReceipt(event=event, applied=False, detail="Nothing in this event to apply.")
    moved = result["tasks_moved"]
    return GithubWebhookReceipt(
        event=event, applied=True, links_added=result["links_added"], tasks_moved=moved,
        detail=f"{len(moved)} task(s) moved." if moved else "Nothing named a task that had moved on.",
    )
