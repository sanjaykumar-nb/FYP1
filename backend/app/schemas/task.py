from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime
from uuid import UUID

# Kanban workflow: backlog -> planned -> in_progress -> blocked -> review -> done
TaskStatus = Literal["backlog", "planned", "in_progress", "blocked", "review", "done"]
TaskPriority = Literal["low", "medium", "high", "critical"]


def _clean_component(value: Optional[str]) -> Optional[str]:
    """Blank means no component; inner spacing is normalised."""
    return (" ".join(value.split()) or None) if value else None


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    component: Optional[str] = Field(None, max_length=100)

    @field_validator("component")
    @classmethod
    def _component(cls, value: Optional[str]) -> Optional[str]:
        return _clean_component(value)
    status: TaskStatus = "backlog"
    priority: TaskPriority = "medium"
    story_points: Optional[int] = None
    estimated_hours: Optional[float] = None
    due_date: Optional[datetime] = None
    blocked_reason: Optional[str] = None
    position: int = 0


class TaskCreate(TaskBase):
    # project_id comes from the path; reporter_id from the authenticated user.
    milestone_id: Optional[UUID] = None
    parent_task_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    component: Optional[str] = Field(None, max_length=100)

    @field_validator("component")
    @classmethod
    def _component(cls, value: Optional[str]) -> Optional[str]:
        return _clean_component(value)
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    story_points: Optional[int] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    due_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    blocked_reason: Optional[str] = None
    milestone_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None
    position: Optional[int] = None


class TaskResponse(TaskBase):
    id: UUID
    project_id: UUID
    milestone_id: Optional[UUID] = None
    parent_task_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None
    reporter_id: UUID
    actual_hours: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TaskWithRelations(TaskResponse):
    assignee: Optional["UserResponse"] = None
    reporter: "UserResponse"
    subtasks: list["TaskResponse"] = []
    comments_count: int = 0
    dependencies_count: int = 0


class TaskDependencyCreate(BaseModel):
    # blocked_task_id comes from the path.
    blocking_task_id: UUID
    dependency_type: str = "blocks"


class TaskDependencyResponse(BaseModel):
    id: UUID
    project_id: UUID
    blocking_task_id: UUID
    blocked_task_id: UUID
    dependency_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskCommentCreate(BaseModel):
    content: str


class TaskCommentResponse(BaseModel):
    id: UUID
    task_id: UUID
    user_id: UUID
    author_name: Optional[str] = None
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskMove(BaseModel):
    status: Optional[TaskStatus] = None
    position: Optional[int] = None
    milestone_id: Optional[UUID] = None


# Forward reference
from app.schemas.auth import UserResponse
TaskWithRelations.model_rebuild()