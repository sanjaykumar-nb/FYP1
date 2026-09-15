"""Builds the project-state payload the AI service's knowledge graph consumes.

The AI service is stateless (see ai-service/app/graph/snapshot.py's
ProjectSnapshot) — it never queries Postgres itself. The backend, which owns
the data, reads it once here and hands over a plain dict matching that
model's shape. Field names must stay in sync with ProjectSnapshot; there is
no shared package between the two services to enforce that at import time.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Milestone, Project, ProjectMember
from app.models.task import Task, TaskComment, TaskDependency
from app.models.user import User


async def build_project_snapshot(db: AsyncSession, project: Project) -> dict:
    members_result = await db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project.id)
    )
    members = [
        {
            "id": str(member.user_id),
            "full_name": user.full_name,
            "email": user.email,
            "role": member.role,
        }
        for member, user in members_result.all()
    ]

    milestones_result = await db.execute(
        select(Milestone).where(Milestone.project_id == project.id)
    )
    milestones = [
        {
            "id": str(m.id),
            "name": m.name,
            "start_date": m.start_date.isoformat() if m.start_date else None,
            "target_date": m.target_date.isoformat() if m.target_date else None,
            "status": m.status,
        }
        for m in milestones_result.scalars().all()
    ]

    tasks_result = await db.execute(select(Task).where(Task.project_id == project.id))
    task_rows = tasks_result.scalars().all()
    tasks = [
        {
            "id": str(t.id),
            "title": t.title,
            "component": t.component,
            "status": t.status,
            "priority": t.priority,
            "story_points": t.story_points,
            "assignee_id": str(t.assignee_id) if t.assignee_id else None,
            "reporter_id": str(t.reporter_id) if t.reporter_id else None,
            "milestone_id": str(t.milestone_id) if t.milestone_id else None,
            "parent_task_id": str(t.parent_task_id) if t.parent_task_id else None,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in task_rows
    ]
    task_ids = {t.id for t in task_rows}

    deps_result = await db.execute(
        select(TaskDependency).where(TaskDependency.project_id == project.id)
    )
    dependencies = [
        {
            "blocking_task_id": str(d.blocking_task_id),
            "blocked_task_id": str(d.blocked_task_id),
            "dependency_type": d.dependency_type,
        }
        for d in deps_result.scalars().all()
        # Guard against a dependency pointing at a task outside this project
        # (shouldn't happen given FK scoping, but the graph builder assumes
        # every referenced id resolves within the same snapshot).
        if d.blocking_task_id in task_ids and d.blocked_task_id in task_ids
    ]

    comments_result = await db.execute(
        select(TaskComment)
        .join(Task, Task.id == TaskComment.task_id)
        .where(Task.project_id == project.id)
    )
    comments = [
        {
            "task_id": str(c.task_id),
            "user_id": str(c.user_id),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comments_result.scalars().all()
    ]

    return {
        "project_id": str(project.id),
        "name": project.name,
        "members": members,
        "milestones": milestones,
        "tasks": tasks,
        "dependencies": dependencies,
        "comments": comments,
        "team_capacity_points": None,
        "velocity_history": [],
    }
