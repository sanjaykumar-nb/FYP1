"""Typed project snapshot — the input to the knowledge graph.

This is the single read of project state per analysis. Everything downstream
(graph, metrics, prompts) is derived from it, so the project data is fetched
once rather than re-serialized per agent.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MemberSnapshot(BaseModel):
    id: UUID
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str = "developer"


class MilestoneSnapshot(BaseModel):
    id: UUID
    name: str
    start_date: Optional[datetime] = None  # with target_date, the schedule window the pace signal uses
    target_date: Optional[datetime] = None
    status: str = "planned"


class TaskSnapshot(BaseModel):
    id: UUID
    title: str
    status: str = "backlog"
    priority: str = "medium"
    story_points: Optional[int] = None
    assignee_id: Optional[UUID] = None
    reporter_id: Optional[UUID] = None
    milestone_id: Optional[UUID] = None
    parent_task_id: Optional[UUID] = None
    component: Optional[str] = None  # the code area or module the task touches
    due_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DependencySnapshot(BaseModel):
    """`blocking_task_id` must finish before `blocked_task_id` can proceed."""

    blocking_task_id: UUID
    blocked_task_id: UUID
    dependency_type: str = "blocks"


class CommentSnapshot(BaseModel):
    task_id: UUID
    user_id: UUID
    created_at: Optional[datetime] = None


class ProjectSnapshot(BaseModel):
    project_id: UUID
    name: str = ""
    members: list[MemberSnapshot] = Field(default_factory=list)
    milestones: list[MilestoneSnapshot] = Field(default_factory=list)
    tasks: list[TaskSnapshot] = Field(default_factory=list)
    dependencies: list[DependencySnapshot] = Field(default_factory=list)
    comments: list[CommentSnapshot] = Field(default_factory=list)
    team_capacity_points: Optional[int] = None
    velocity_history: list[float] = Field(default_factory=list)
    as_of: Optional[datetime] = None

    def content_hash(self) -> str:
        """Stable hash of project state, for delta-analysis caching (T6)."""
        import hashlib

        payload = self.model_dump_json(exclude={"as_of"})
        return hashlib.sha256(payload.encode()).hexdigest()
