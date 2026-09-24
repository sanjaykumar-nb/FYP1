"""Reading a project's GitHub repository: sync, and what it linked.

The sync itself is app.services.github_sync; this exposes it, checks the caller may
change tasks, and turns GitHub being unreachable into a clear message rather than a 500.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_id, get_db, require_permission
from app.models.project import Project
from app.models.task import Task, TaskGithubLink
from app.schemas.github import GithubLinkResponse, GithubSyncResult
from app.services.github_sync import GitHubUnavailable, sync_project

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
