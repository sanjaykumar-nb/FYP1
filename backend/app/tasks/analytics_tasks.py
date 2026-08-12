from celery import shared_task
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task
def update_project_health_scores():
    """Update health and risk scores for all active projects"""
    import asyncio
    
    async def _run():
        async with async_session_maker() as db:
            from app.models.project import Project
            from app.models.task import Task
            from app.models.risk import RiskScore
            from sqlalchemy import select, func
            
            projects = await db.execute(
                select(Project).where(Project.status == "active")
            )
            
            for project in projects.scalars().all():
                # Calculate health score based on completion rate, overdue, blocked
                stats = await db.execute(
                    select(
                        func.count(Task.id).label("total"),
                        func.sum(Task.story_points).label("total_points"),
                        func.count(Task.id).filter(Task.status == "done").label("completed"),
                        func.sum(Task.story_points).filter(Task.status == "done").label("completed_points"),
                        func.count(Task.id).filter(Task.status == "blocked").label("blocked"),
                        func.count(Task.id).filter(Task.due_date < func.now()).filter(Task.status != "done").label("overdue"),
                    ).where(Task.project_id == project.id)
                )
                s = stats.one()
                
                total_points = s.total_points or 1
                completion_rate = (s.completed_points or 0) / total_points
                overdue_rate = (s.overdue or 0) / max(s.total or 1, 1)
                blocked_rate = (s.blocked or 0) / max(s.total or 1, 1)
                
                # Health score: high completion, low overdue, low blocked
                health = max(0, min(1, completion_rate * 0.6 + (1 - overdue_rate) * 0.2 + (1 - blocked_rate) * 0.2))
                
                # Risk score: inverse of health with some noise
                risk = max(0, min(1, 1 - health + 0.1))
                
                project.health_score = round(health, 2)
                project.risk_score = round(risk, 2)
                
                await db.commit()
            
            return {"updated": len(list(projects.scalars().all()))}
    
    return asyncio.run(_run())


@shared_task
def compute_risk_scores():
    """Compute detailed risk scores for projects"""
    import asyncio
    
    async def _run():
        async with async_session_maker() as db:
            from app.models.project import Project
            from app.models.risk import RiskScore, AgentRun
            from sqlalchemy import select, func
            from datetime import datetime
            
            projects = await db.execute(
                select(Project).where(Project.status == "active")
            )
            
            risk_types = [
                "delay", "coordination", "workload", "dependency", "knowledge", "silent_member"
            ]
            
            for project in projects.scalars().all():
                for risk_type in risk_types:
                    # Create a basic risk score (placeholder - AI service would compute real ones)
                    score = RiskScore(
                        project_id=project.id,
                        risk_type=risk_type,
                        score=0.3,
                        level="low",
                        factors=[],
                        evidence=[],
                        trend="stable",
                        computed_at=datetime.utcnow(),
                    )
                    db.add(score)
                
                await db.commit()
            
            return {"computed": len(list(projects.scalars().all()))}
    
    return asyncio.run(_run())