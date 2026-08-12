from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.risk import RiskScore, Recommendation, AgentRun
from app.models.project import Project
from app.core.exceptions import NotFoundError


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_project_health(self, project_id: UUID, org_id: UUID) -> dict:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project not found")
        
        # Task statistics
        from app.models.task import Task
        from app.models.meeting import Meeting
        
        task_stats = await self.db.execute(
            select(
                func.count(Task.id).label("total"),
                func.sum(Task.story_points).label("total_points"),
                func.count(Task.id).filter(Task.status == "done").label("completed"),
                func.sum(Task.story_points).filter(Task.status == "done").label("completed_points"),
                func.count(Task.id).filter(Task.status == "blocked").label("blocked"),
                func.count(Task.id).filter(Task.due_date < func.now()).filter(Task.status != "done").label("overdue"),
            ).where(Task.project_id == project_id)
        )
        stats = task_stats.one()
        
        team_size_result = await self.db.execute(
            select(func.count(ProjectMember.id)).where(ProjectMember.project_id == project_id)
        )
        
        completion_rate = 0
        if stats.total_points and stats.total_points > 0:
            completion_rate = (stats.completed_points or 0) / stats.total_points
        
        return {
            "health_score": project.health_score or 0.5,
            "risk_score": project.risk_score or 0.3,
            "completion_rate": completion_rate,
            "overdue_tasks": stats.overdue or 0,
            "blocked_tasks": stats.blocked or 0,
            "active_milestones": 0,  # Placeholder
            "team_size": team_size_result.scalar() or 0,
            "workload_balance": 0.8,  # Placeholder
        }
    
    async def get_risk_scores(self, project_id: UUID, org_id: UUID) -> dict:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("Project not found")
        
        result = await self.db.execute(
            select(RiskScore)
            .where(RiskScore.project_id == project_id)
            .order_by(RiskScore.risk_type, RiskScore.computed_at.desc())
        )
        all_scores = result.scalars().all()
        
        latest_by_type = {}
        for score in all_scores:
            if score.risk_type not in latest_by_type:
                latest_by_type[score.risk_type] = score
        
        return {
            risk_type: {
                "score": score.score,
                "level": score.level,
                "factors": score.factors,
                "evidence": score.evidence,
                "trend": score.trend,
                "computed_at": score.computed_at,
            }
            for risk_type, score in latest_by_type.items()
        }
    
    async def get_workload_distribution(self, project_id: UUID, org_id: UUID) -> list:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("Project not found")
        
        from app.models.workload import WorkloadSnapshot
        from app.models.user import User
        
        result = await self.db.execute(
            select(WorkloadSnapshot, User.full_name)
            .join(User, User.id == WorkloadSnapshot.user_id)
            .where(WorkloadSnapshot.project_id == project_id)
            .order_by(WorkloadSnapshot.user_id, WorkloadSnapshot.snapshot_date.desc())
        )
        all_snapshots = result.all()
        
        latest_by_user = {}
        for snapshot, name in all_snapshots:
            if snapshot.user_id not in latest_by_user:
                latest_by_user[snapshot.user_id] = (snapshot, name)
        
        return [
            {
                "user_id": user_id,
                "user_name": name,
                "assigned_points": snapshot.assigned_story_points,
                "completed_points": snapshot.completed_story_points,
                "in_progress_points": snapshot.in_progress_story_points,
                "blocked_points": snapshot.blocked_story_points,
                "active_tasks": snapshot.active_task_count,
                "overdue_tasks": snapshot.overdue_task_count,
                "utilization_score": snapshot.utilization_score,
            }
            for user_id, (snapshot, name) in latest_by_user.items()
        ]
    
    async def get_communication_analysis(self, project_id: UUID, org_id: UUID) -> dict:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("Project not found")
        
        from app.models.workload import CommunicationEvent
        
        stats = await self.db.execute(
            select(
                func.count(CommunicationEvent.id).label("total"),
                func.avg(CommunicationEvent.response_time_seconds).label("avg_response"),
                func.count(CommunicationEvent.id).filter(CommunicationEvent.is_question == True).label("questions"),
                func.count(CommunicationEvent.id).filter(CommunicationEvent.is_blocker_mention == True).label("blockers"),
            ).where(CommunicationEvent.project_id == project_id)
        )
        comm_stats = stats.one()
        
        participants = await self.db.execute(
            select(func.count(func.distinct(CommunicationEvent.user_id))).where(
                CommunicationEvent.project_id == project_id
            )
        )
        
        from app.models.project import ProjectMember
        team_size_result = await self.db.execute(
            select(func.count(ProjectMember.id)).where(ProjectMember.project_id == project_id)
        )
        team_size = team_size_result.scalar() or 1
        
        return {
            "total_messages": comm_stats.total or 0,
            "avg_response_time_hours": (comm_stats.avg_response or 0) / 3600,
            "unanswered_questions": 0,
            "participation_rate": (participants.scalar() or 0) / team_size,
            "blocker_mentions": comm_stats.blockers or 0,
            "low_participation_users": [],
        }
    
    async def get_bottlenecks(self, project_id: UUID, org_id: UUID) -> list:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("Project not found")
        
        from app.models.task import Task, TaskDependency
        
        result = await self.db.execute(
            select(
                Task.id,
                Task.title,
                func.count(TaskDependency.id).label("blocked_count"),
                func.array_agg(TaskDependency.blocked_task_id).label("blocked_tasks"),
                Task.assignee_id,
            )
            .join(TaskDependency, TaskDependency.blocking_task_id == Task.id)
            .where(Task.project_id == project_id)
            .group_by(Task.id, Task.title, Task.assignee_id)
            .having(func.count(TaskDependency.id) > 1)
            .order_by(func.count(TaskDependency.id).desc())
            .limit(10)
        )
        bottlenecks = result.all()
        
        return [
            {
                "task_id": row.id,
                "task_title": row.title,
                "blocked_count": row.blocked_count,
                "blocking_tasks": row.blocked_tasks or [],
                "assignee_id": row.assignee_id,
            }
            for row in bottlenecks
        ]
    
    async def get_intelligence_index(self, project_id: UUID, org_id: UUID) -> dict:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project not found")
        
        from datetime import datetime
        return {
            "score": 75.0,
            "tier": "Good",
            "health_score": project.health_score or 0.5,
            "risk_score": project.risk_score or 0.3,
            "communication_score": 0.7,
            "workload_balance": 0.8,
            "memory_utilization": 0.6,
            "computed_at": datetime.utcnow(),
        }
    
    async def list_agent_runs(self, project_id: UUID, org_id: UUID, limit: int = 20) -> list:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("Project not found")
        
        result = await self.db.execute(
            select(AgentRun)
            .where(AgentRun.project_id == project_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        runs = result.scalars().all()
        return runs
    
    async def search_memory(self, org_id: UUID, query: str = "", memory_type: str = None, project_id: UUID = None, limit: int = 20) -> list:
        from app.models.memory import OrganizationMemory
        
        q = select(OrganizationMemory).where(OrganizationMemory.organization_id == org_id)
        
        if query:
            q = q.where(OrganizationMemory.title.ilike(f"%{query}%"))
        if memory_type:
            q = q.where(OrganizationMemory.memory_type == memory_type)
        if project_id:
            q = q.where(OrganizationMemory.project_id == project_id)
        
        q = q.order_by(OrganizationMemory.created_at.desc()).limit(limit)
        
        result = await self.db.execute(q)
        memories = result.scalars().all()
        return memories
    
    async def add_memory(self, org_id: UUID, user_id: UUID, data: dict):
        from app.models.memory import OrganizationMemory
        
        memory = OrganizationMemory(
            organization_id=org_id,
            project_id=data.get("project_id"),
            memory_type=data.get("memory_type"),
            title=data.get("title"),
            content=data.get("content"),
            context=data.get("context", {}),
            source=data.get("source"),
            source_id=data.get("source_id"),
            confidence=data.get("confidence"),
            created_by=user_id,
        )
        self.db.add(memory)
        await self.db.commit()
        await self.db.refresh(memory)
        return memory