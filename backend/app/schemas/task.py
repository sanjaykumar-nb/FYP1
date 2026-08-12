from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    status: str = "backlog"
    priority: str = "medium"
    story_points: Optional[int] = None
    estimated_hours: Optional[float] = None
    due_date: Optional[datetime] = None
    blocked_reason: Optional[str] = None
    position: int = 0


class TaskCreate(TaskBase):
    project_id: UUID
    milestone_id: Optional[UUID] = None
    parent_task_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None
    reporter_id: UUID


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
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
    blocking_task_id: UUID
    blocked_task_id: UUID
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
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskMove(BaseModel):
    status: Optional[str] = None
    position: Optional[int] = None
    milestone_id: Optional[UUID] = None


# Forward reference
from app.schemas.auth import UserResponse
TaskWithRelations.model_rebuild()