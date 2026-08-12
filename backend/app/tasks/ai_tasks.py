from celery import shared_task
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings
from app.models import Base
from app.services.ai_client import ai_client

settings = get_settings()

# Create async engine for Celery tasks
engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(bind=True, max_retries=3)
def run_ai_analysis(self, project_id: str, scope: list = None, trigger_type: str = "manual", user_id: str = None):
    """Run AI analysis for a project"""
    import asyncio
    
    async def _run():
        async with async_session_maker() as db:
            from app.models.risk import AgentRun
            from app.models.project import Project
            from sqlalchemy import select
            
            # Create agent run record
            run = AgentRun(
                project_id=project_id,
                triggered_by=user_id,
                trigger_type=trigger_type,
                status="running",
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)
            
            try:
                # Call AI service
                result = await ai_client.analyze_project(
                    project_id=project_id,
                    scope=scope,
                    trigger_type=trigger_type,
                )
                
                # Update run with results
                run.status = "completed"
                run.coordinator_output = result.get("coordinator_output")
                run.specialist_outputs = result.get("specialist_outputs")
                run.final_recommendations = result.get("final_recommendations")
                run.completed_at = asyncio.get_event_loop().time()
                
                await db.commit()
                
                return {"status": "completed", "run_id": str(run.id)}
            
            except Exception as e:
                run.status = "failed"
                run.error_message = str(e)
                await db.commit()
                raise
    
    return asyncio.run(_run())


@shared_task
def create_daily_workload_snapshots():
    """Create daily workload snapshots for all active projects"""
    import asyncio
    from datetime import date
    
    async def _run():
        async with async_session_maker() as db:
            from app.models.project import Project
            from app.models.task import Task
            from app.models.workload import WorkloadSnapshot
            from app.models.user import User
            from sqlalchemy import select, func
            
            # Get all active projects
            projects = await db.execute(
                select(Project).where(Project.status == "active")
            )
            
            for project in projects.scalars().all():
                # Get project members
                members = await db.execute(
                    select(ProjectMember.user_id)
                    .where(ProjectMember.project_id == project.id)
                )
                member_ids = [m[0] for m in members.all()]
                
                for user_id in member_ids:
                    # Calculate workload stats
                    task_stats = await db.execute(
                        select(
                            func.count(Task.id).label("total"),
                            func.sum(Task.story_points).label("total_points"),
                            func.count(Task.id).filter(Task.status == "done").label("completed"),
                            func.sum(Task.story_points).filter(Task.status == "done").label("completed_points"),
                            func.count(Task.id).filter(Task.status == "in_progress").label("in_progress"),
                            func.sum(Task.story_points).filter(Task.status == "in_progress").label("in_progress_points"),
                            func.count(Task.id).filter(Task.status == "blocked").label("blocked"),
                            func.sum(Task.story_points).filter(Task.status == "blocked").label("blocked_points"),
                            func.count(Task.id).filter(Task.due_date < func.now()).filter(Task.status != "done").label("overdue"),
                        ).where(
                            Task.project_id == project.id,
                            Task.assignee_id == user_id,
                        )
                    )
                    stats = task_stats.one()
                    
                    # Calculate utilization
                    total_points = stats.total_points or 0
                    utilization = min(total_points / 40, 1.0) if total_points > 0 else 0  # Assuming 40 points = full capacity
                    
                    # Create or update snapshot
                    existing = await db.execute(
                        select(WorkloadSnapshot).where(
                            WorkloadSnapshot.project_id == project.id,
                            WorkloadSnapshot.user_id == user_id,
                            WorkloadSnapshot.snapshot_date == date.today(),
                        )
                    )
                    snapshot = existing.scalar_one_or_none()
                    
                    if snapshot:
                        snapshot.assigned_story_points = total_points
                        snapshot.completed_story_points = stats.completed_points or 0
                        snapshot.in_progress_story_points = stats.in_progress_points or 0
                        snapshot.blocked_story_points = stats.blocked_points or 0
                        snapshot.active_task_count = stats.total or 0
                        snapshot.overdue_task_count = stats.overdue or 0
                        snapshot.utilization_score = utilization
                    else:
                        snapshot = WorkloadSnapshot(
                            project_id=project.id,
                            user_id=user_id,
                            snapshot_date=date.today(),
                            assigned_story_points=total_points,
                            completed_story_points=stats.completed_points or 0,
                            in_progress_story_points=stats.in_progress_points or 0,
                            blocked_story_points=stats.blocked_points or 0,
                            active_task_count=stats.total or 0,
                            overdue_task_count=stats.overdue or 0,
                            utilization_score=utilization,
                        )
                        db.add(snapshot)
                
                await db.commit()
    
    return asyncio.run(_run())


@shared_task
def run_scheduled_analyses():
    """Run scheduled AI analyses for projects that need it"""
    import asyncio
    
    async def _run():
        async with async_session_maker() as db:
            from app.models.project import Project
            from app.models.risk import AgentRun
            from sqlalchemy import select, func
            from datetime import datetime, timedelta
            
            # Find projects that haven't been analyzed in 24 hours
            cutoff = datetime.utcnow() - timedelta(hours=24)
            
            projects = await db.execute(
                select(Project.id)
                .where(Project.status == "active")
                .where(~Project.id.in_(
                    select(AgentRun.project_id)
                    .where(AgentRun.created_at > cutoff)
                    .where(AgentRun.status == "completed")
                ))
            )
            
            for project in projects.scalars().all():
                # Queue analysis task
                run_ai_analysis.delay(str(project), trigger_type="scheduled")
    
    return asyncio.run(_run())


# Import ProjectMember at top level for the task
from app.models.project import ProjectMember