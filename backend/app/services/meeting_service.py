from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.meeting import Meeting, MeetingParticipant, MeetingActionItem, MeetingDecision
from app.models.project import Project
from app.core.exceptions import NotFoundError


class MeetingService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_meeting(self, meeting_id: UUID, org_id: UUID) -> Optional[Meeting]:
        result = await self.db.execute(
            select(Meeting)
            .join(Project, Project.id == Meeting.project_id)
            .where(Meeting.id == meeting_id, Project.organization_id == org_id)
        )
        return result.scalar_one_or_none()
    
    async def list_meetings(
        self,
        project_id: UUID,
        org_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Meeting], int]:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("Project not found")
        
        query = select(Meeting).where(Meeting.project_id == project_id)
        
        count_query = select(func.count(Meeting.id)).where(Meeting.project_id == project_id)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        query = query.order_by(Meeting.started_at.desc().nullslast()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        meetings = result.scalars().all()
        
        return meetings, total
    
    async def create_meeting(
        self,
        project_id: UUID,
        org_id: UUID,
        user_id: UUID,
        title: str,
        description: str = None,
        meeting_type: str = None,
        started_at: str = None,
        ended_at: str = None,
    ) -> Meeting:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("Project not found")
        
        meeting = Meeting(
            project_id=project_id,
            organizer_id=user_id,
            title=title,
            description=description,
            meeting_type=meeting_type,
            started_at=started_at,
            ended_at=ended_at,
        )
        self.db.add(meeting)
        await self.db.flush()
        
        # Add organizer as participant
        participant = MeetingParticipant(meeting_id=meeting.id, user_id=user_id)
        self.db.add(participant)
        
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting
    
    async def update_meeting(self, meeting_id: UUID, org_id: UUID, data: dict) -> Meeting:
        meeting = await self.get_meeting(meeting_id, org_id)
        if not meeting:
            raise NotFoundError("Meeting not found")
        
        for key, value in data.items():
            setattr(meeting, key, value)
        
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting
    
    async def upload_transcript(self, meeting_id: UUID, org_id: UUID, transcript: str) -> Meeting:
        meeting = await self.get_meeting(meeting_id, org_id)
        if not meeting:
            raise NotFoundError("Meeting not found")
        
        meeting.transcript = transcript
        meeting.source = "upload"
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting
    
    async def add_participant(self, meeting_id: UUID, org_id: UUID, user_id: UUID) -> MeetingParticipant:
        meeting = await self.get_meeting(meeting_id, org_id)
        if not meeting:
            raise NotFoundError("Meeting not found")
        
        # Check if already participant
        result = await self.db.execute(
            select(MeetingParticipant).where(
                MeetingParticipant.meeting_id == meeting_id,
                MeetingParticipant.user_id == user_id,
            )
        )
        if result.scalar_one_or_none():
            raise ConflictError("User is already a participant")
        
        participant = MeetingParticipant(meeting_id=meeting_id, user_id=user_id)
        self.db.add(participant)
        await self.db.commit()
        await self.db.refresh(participant)
        return participant


class ConflictError(Exception):
    pass