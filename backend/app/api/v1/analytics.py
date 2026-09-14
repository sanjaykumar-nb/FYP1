from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from app.api.deps import get_db, get_current_org_id, get_current_user_id
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.meeting import Meeting
from app.models.workload import WorkloadSnapshot, CommunicationEvent
from app.models.risk import RiskScore, Recommendation, AgentRun
from app.models.memory import OrganizationMemory, AuditLog, Notification
from app.services.ai_client import ai_client
from app.services.snapshot_builder import build_project_snapshot
from app.core.exceptions import AIServiceError
from app.schemas.analytics import (
    ProjectHealthResponse,
    WorkloadDistributionResponse,
    BottleneckResponse,
    CommunicationAnalysisResponse,
    TeamIntelligenceIndexResponse,
    AgentRunResponse,
    OrganizationMemoryResponse,
    AuditLogResponse,
    NotificationResponse,
)

router = APIRouter()

RISK_SCORE_BY_LEVEL = {"low": 0.2, "medium": 0.45, "high": 0.7, "critical": 0.9}


@router.get("/projects/{project_id}/dashboard", response_model=ProjectHealthResponse)
async def get_project_dashboard(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    # Get task statistics
    task_stats = await db.execute(
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
    
    # Get active milestones
    milestones_result = await db.execute(
        select(func.count(Project.id)).where(
            Project.id == project_id,
            Project.status == "active",
        )
    )
    
    # Get team size
    team_size_result = await db.execute(
        select(func.count(ProjectMember.id)).where(ProjectMember.project_id == project_id)
    )
    
    # Calculate workload balance (simplified)
    workload_balance = 0.8  # Placeholder
    
    completion_rate = 0
    if stats.total_points and stats.total_points > 0:
        completion_rate = (stats.completed_points or 0) / stats.total_points
    
    return ProjectHealthResponse(
        health_score=project.health_score or 0.5,
        risk_score=project.risk_score or 0.3,
        completion_rate=completion_rate,
        overdue_tasks=stats.overdue or 0,
        blocked_tasks=stats.blocked or 0,
        active_milestones=milestones_result.scalar() or 0,
        team_size=team_size_result.scalar() or 0,
        workload_balance=workload_balance,
    )


@router.get("/projects/{project_id}/health", response_model=ProjectHealthResponse)
async def get_project_health(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    return await get_project_dashboard(project_id, db, org_id)


@router.get("/projects/{project_id}/risk")
async def get_risk_scores(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    # Get latest risk scores by type
    result = await db.execute(
        select(RiskScore)
        .where(RiskScore.project_id == project_id)
        .order_by(RiskScore.risk_type, RiskScore.computed_at.desc())
    )
    all_scores = result.scalars().all()
    
    # Get latest for each type
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


@router.get("/projects/{project_id}/workload", response_model=list[WorkloadDistributionResponse])
async def get_workload_distribution(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    # Get latest workload snapshot for each user
    result = await db.execute(
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
        WorkloadDistributionResponse(
            user_id=user_id,
            user_name=name,
            assigned_points=snapshot.assigned_story_points,
            completed_points=snapshot.completed_story_points,
            in_progress_points=snapshot.in_progress_story_points,
            blocked_points=snapshot.blocked_story_points,
            active_tasks=snapshot.active_task_count,
            overdue_tasks=snapshot.overdue_task_count,
            utilization_score=snapshot.utilization_score,
        )
        for user_id, (snapshot, name) in latest_by_user.items()
    ]


@router.get("/projects/{project_id}/communication", response_model=CommunicationAnalysisResponse)
async def get_communication_analysis(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    # Get communication stats
    stats = await db.execute(
        select(
            func.count(CommunicationEvent.id).label("total"),
            func.avg(CommunicationEvent.response_time_seconds).label("avg_response"),
            func.count(CommunicationEvent.id).filter(CommunicationEvent.is_question == True).label("questions"),
            func.count(CommunicationEvent.id).filter(CommunicationEvent.is_blocker_mention == True).label("blockers"),
        ).where(CommunicationEvent.project_id == project_id)
    )
    comm_stats = stats.one()
    
    # Get participation rate
    participants = await db.execute(
        select(func.count(func.distinct(CommunicationEvent.user_id))).where(
            CommunicationEvent.project_id == project_id
        )
    )
    
    team_size_result = await db.execute(
        select(func.count(ProjectMember.id)).where(ProjectMember.project_id == project_id)
    )
    team_size = team_size_result.scalar() or 1
    
    return CommunicationAnalysisResponse(
        total_messages=comm_stats.total or 0,
        avg_response_time_hours=(comm_stats.avg_response or 0) / 3600,
        unanswered_questions=0,  # Placeholder
        participation_rate=(participants.scalar() or 0) / team_size,
        blocker_mentions=comm_stats.blockers or 0,
        low_participation_users=[],
    )


@router.get("/projects/{project_id}/bottlenecks", response_model=list[BottleneckResponse])
async def get_bottlenecks(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    # Find tasks that block many other tasks
    result = await db.execute(
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
        BottleneckResponse(
            task_id=row.id,
            task_title=row.title,
            blocked_count=row.blocked_count,
            blocking_tasks=row.blocked_tasks or [],
            assignee_id=row.assignee_id,
        )
        for row in bottlenecks
    ]


@router.get("/projects/{project_id}/intelligence-index", response_model=TeamIntelligenceIndexResponse)
async def get_intelligence_index(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    # Calculate index (placeholder implementation)
    return TeamIntelligenceIndexResponse(
        score=75.0,
        tier="Good",
        health_score=project.health_score or 0.5,
        risk_score=project.risk_score or 0.3,
        communication_score=0.7,
        workload_balance=0.8,
        memory_utilization=0.6,
        computed_at=datetime.utcnow(),
    )


@router.post("/projects/{project_id}/analyze", response_model=AgentRunResponse)
async def trigger_analysis(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    user_id: UUID = Depends(get_current_user_id),
):
    """Run the multi-agent analysis pipeline and persist the result.

    Runs synchronously — the MVP has no Celery worker (see plan Part B3).
    The AI service is stateless, so the project state is read here and
    handed over as a snapshot; the AgentRun row this creates is the only
    persistent record of the run.
    """
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    snapshot = await build_project_snapshot(db, project)

    run = AgentRun(
        project_id=project_id,
        triggered_by=user_id,
        trigger_type="manual",
        status="running",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    try:
        result = await ai_client.analyze_project(
            project_id=project_id,
            scope=["planning", "progress", "workload"],
            trigger_type="manual",
            snapshot=snapshot,
        )
    except AIServiceError as e:
        run.status = "failed"
        run.error_message = str(e.detail)
        await db.commit()
        await db.refresh(run)
        return AgentRunResponse.model_validate(run)

    analysis = result.get("result") or {}
    run.status = "completed"
    run.coordinator_output = analysis
    run.specialist_outputs = analysis.get("specialist_outputs")
    run.final_recommendations = {"items": analysis.get("merged_recommendations", [])}
    run.completed_at = datetime.utcnow()
    # The dashboard and workspace read these columns; without this they keep
    # showing defaults that contradict the analysis the user just ran.
    risk = RISK_SCORE_BY_LEVEL.get(analysis.get("overall_risk_level"))
    if risk is not None:
        project.risk_score = risk
        project.health_score = round(1 - risk, 2)
    await db.commit()
    await db.refresh(run)

    return AgentRunResponse.model_validate(run)


@router.get("/projects/{project_id}/agent-runs", response_model=list[AgentRunResponse])
async def list_agent_runs(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
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
        select(AgentRun)
        .where(AgentRun.project_id == project_id)
        .order_by(AgentRun.created_at.desc())
        .limit(20)
    )
    runs = result.scalars().all()
    
    return [AgentRunResponse.model_validate(r) for r in runs]


@router.get("/organizations/{org_id}/memory", response_model=list[OrganizationMemoryResponse])
async def search_memory(
    org_id: UUID,
    query: str = "",
    memory_type: str = None,
    project_id: UUID = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
):
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    q = select(OrganizationMemory).where(OrganizationMemory.organization_id == org_id)
    
    if query:
        q = q.where(OrganizationMemory.title.ilike(f"%{query}%"))
    if memory_type:
        q = q.where(OrganizationMemory.memory_type == memory_type)
    if project_id:
        q = q.where(OrganizationMemory.project_id == project_id)
    
    q = q.order_by(OrganizationMemory.created_at.desc()).limit(limit)
    
    result = await db.execute(q)
    memories = result.scalars().all()
    
    return [OrganizationMemoryResponse.model_validate(m) for m in memories]


@router.post("/organizations/{org_id}/memory", response_model=OrganizationMemoryResponse)
async def add_memory(
    org_id: UUID,
    memory_data: OrganizationMemoryResponse,
    db: AsyncSession = Depends(get_db),
    org_id_check: UUID = Depends(get_current_org_id),
    user_id: UUID = Depends(get_current_user_id),
):
    if org_id != org_id_check:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    memory = OrganizationMemory(
        organization_id=org_id,
        project_id=memory_data.project_id,
        memory_type=memory_data.memory_type,
        title=memory_data.title,
        content=memory_data.content,
        context=memory_data.context,
        source=memory_data.source,
        source_id=memory_data.source_id,
        confidence=memory_data.confidence,
        created_by=user_id,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    
    return OrganizationMemoryResponse.model_validate(memory)