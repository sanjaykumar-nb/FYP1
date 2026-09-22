from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.api.deps import get_db, get_current_user_id, get_current_org_id, get_pagination_params, require_permission
from app.models.project import Project
from app.models.meeting import Meeting, MeetingParticipant, MeetingActionItem, MeetingDecision
from app.models.user import User
from app.models.task import Task
from app.schemas.meeting import (
    MeetingCreate,
    MeetingUpdate,
    MeetingResponse,
    MeetingWithDetails,
    MeetingActionItemCreate,
    MeetingActionItemUpdate,
    MeetingActionItemResponse,
)
from app.schemas.auth import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_meetings(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    pagination: PaginatedResponse = Depends(get_pagination_params),
):
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    result = await db.execute(
        select(Meeting)
        .where(Meeting.project_id == project_id)
        .order_by(Meeting.started_at.desc().nullslast())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    meetings = result.scalars().all()
    
    total_result = await db.execute(
        select(func.count(Meeting.id)).where(Meeting.project_id == project_id)
    )
    total = total_result.scalar()
    
    return PaginatedResponse(
        items=[MeetingResponse.model_validate(m) for m in meetings],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.post("", response_model=MeetingResponse, dependencies=[Depends(require_permission("meeting:create"))])
async def create_meeting(
    project_id: UUID,
    meeting_data: MeetingCreate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    user_id: UUID = Depends(get_current_user_id),
):
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    meeting = Meeting(
        project_id=project_id,
        organizer_id=user_id,
        title=meeting_data.title,
        description=meeting_data.description,
        meeting_type=meeting_data.meeting_type,
        started_at=meeting_data.started_at,
        ended_at=meeting_data.ended_at,
    )
    db.add(meeting)
    await db.flush()
    
    # Add organizer as participant
    participant = MeetingParticipant(meeting_id=meeting.id, user_id=user_id)
    db.add(participant)
    
    await db.commit()
    await db.refresh(meeting)
    
    return MeetingResponse.model_validate(meeting)


@router.get("/{meeting_id}", response_model=MeetingWithDetails)
async def get_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Meeting)
        .options(
            selectinload(Meeting.participants).selectinload(MeetingParticipant.user),
            selectinload(Meeting.action_items).selectinload(MeetingActionItem.assignee).selectinload(MeetingActionItem.task),
            selectinload(Meeting.decisions),
        )
        .join(Project, Project.id == Meeting.project_id)
        .where(Meeting.id == meeting_id, Project.organization_id == org_id)
    )
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    return MeetingWithDetails.model_validate(meeting)


@router.patch("/{meeting_id}", response_model=MeetingResponse, dependencies=[Depends(require_permission("meeting:update"))])
async def update_meeting(
    meeting_id: UUID,
    meeting_data: MeetingUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Meeting)
        .join(Project, Project.id == Meeting.project_id)
        .where(Meeting.id == meeting_id, Project.organization_id == org_id)
    )
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    for field, value in meeting_data.model_dump(exclude_unset=True).items():
        setattr(meeting, field, value)
    
    await db.commit()
    await db.refresh(meeting)
    
    return MeetingResponse.model_validate(meeting)


@router.post("/{meeting_id}/transcript", dependencies=[Depends(require_permission("meeting:update"))])
async def upload_transcript(
    meeting_id: UUID,
    transcript: str,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Meeting)
        .join(Project, Project.id == Meeting.project_id)
        .where(Meeting.id == meeting_id, Project.organization_id == org_id)
    )
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    meeting.transcript = transcript
    meeting.source = "upload"
    await db.commit()
    
    return {"message": "Transcript uploaded"}


@router.post("/{meeting_id}/analyze", dependencies=[Depends(require_permission("meeting:update"))])
async def analyze_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Meeting)
        .join(Project, Project.id == Meeting.project_id)
        .where(Meeting.id == meeting_id, Project.organization_id == org_id)
    )
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    # TODO: Trigger AI analysis via AI service
    # This would call the AI service to extract action items, decisions, etc.
    
    return {"message": "Analysis started", "meeting_id": str(meeting_id)}


# Action items
@router.get("/{meeting_id}/action-items", response_model=list[MeetingActionItemResponse])
async def list_action_items(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(MeetingActionItem)
        .options(selectinload(MeetingActionItem.assignee), selectinload(MeetingActionItem.task))
        .where(MeetingActionItem.meeting_id == meeting_id)
    )
    items = result.scalars().all()
    
    return [MeetingActionItemResponse.model_validate(item) for item in items]


@router.patch("/action-items/{item_id}", response_model=MeetingActionItemResponse,
              dependencies=[Depends(require_permission("meeting:update"))])
async def update_action_item(
    item_id: UUID,
    item_data: MeetingActionItemUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(MeetingActionItem)
        .join(Meeting, Meeting.id == MeetingActionItem.meeting_id)
        .join(Project, Project.id == Meeting.project_id)
        .where(MeetingActionItem.id == item_id, Project.organization_id == org_id)
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action item not found",
        )
    
    for field, value in item_data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    
    await db.commit()
    await db.refresh(item)
    
    return MeetingActionItemResponse.model_validate(item)


# Decisions
@router.get("/{meeting_id}/decisions", response_model=list)
async def list_decisions(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(MeetingDecision)
        .join(Meeting, Meeting.id == MeetingDecision.meeting_id)
        .join(Project, Project.id == Meeting.project_id)
        .where(MeetingDecision.meeting_id == meeting_id, Project.organization_id == org_id)
    )
    decisions = result.scalars().all()
    
    return decisions