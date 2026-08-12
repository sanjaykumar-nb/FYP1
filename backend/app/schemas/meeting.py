from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class MeetingBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    meeting_type: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class MeetingCreate(MeetingBase):
    project_id: UUID
    organizer_id: UUID


class MeetingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    meeting_type: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None


class MeetingResponse(MeetingBase):
    id: UUID
    project_id: UUID
    organizer_id: UUID
    transcript: Optional[str] = None
    summary: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingParticipantResponse(BaseModel):
    id: UUID
    meeting_id: UUID
    user_id: UUID

    class Config:
        from_attributes = True


class MeetingActionItemBase(BaseModel):
    description: str
    due_date: Optional[datetime] = None
    status: str = "pending"


class MeetingActionItemCreate(MeetingActionItemBase):
    meeting_id: UUID
    task_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None


class MeetingActionItemUpdate(BaseModel):
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None
    task_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None


class MeetingActionItemResponse(MeetingActionItemBase):
    id: UUID
    meeting_id: UUID
    task_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None
    extracted_by_ai: bool
    confidence: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingDecisionBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    rationale: Optional[str] = None


class MeetingDecisionCreate(MeetingDecisionBase):
    meeting_id: UUID
    decided_by: Optional[UUID] = None


class MeetingDecisionResponse(MeetingDecisionBase):
    id: UUID
    meeting_id: UUID
    decided_by: Optional[UUID] = None
    extracted_by_ai: bool
    confidence: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingWithDetails(MeetingResponse):
    participants: list[MeetingParticipantResponse] = []
    action_items: list[MeetingActionItemResponse] = []
    decisions: list[MeetingDecisionResponse] = []