from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from app.api.deps import get_db, get_current_user_id, get_current_org_id, get_pagination_params
from app.models.project import Project
from app.models.task import Task, TaskDependency, TaskComment
from app.models.user import User
from app.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskWithRelations,
    TaskDependencyCreate,
    TaskDependencyResponse,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskMove,
    PaginatedResponse,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_tasks(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    pagination: PaginatedResponse = Depends(get_pagination_params),
    status: Optional[str] = Query(None),
    assignee_id: Optional[UUID] = Query(None),
    milestone_id: Optional[UUID] = Query(None),
    priority: Optional[str] = Query(None),
):
    # Verify project belongs to org
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    query = select(Task).where(Task.project_id == project_id)
    
    if status:
        query = query.where(Task.status == status)
    if assignee_id:
        query = query.where(Task.assignee_id == assignee_id)
    if milestone_id:
        query = query.where(Task.milestone_id == milestone_id)
    if priority:
        query = query.where(Task.priority == priority)
    
    query = query.order_by(Task.position).offset(pagination.offset).limit(pagination.limit)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    total_query = select(func.count(Task.id)).where(Task.project_id == project_id)
    if status:
        total_query = total_query.where(Task.status == status)
    if assignee_id:
        total_query = total_query.where(Task.assignee_id == assignee_id)
    if milestone_id:
        total_query = total_query.where(Task.milestone_id == milestone_id)
    if priority:
        total_query = total_query.where(Task.priority == priority)
    
    total_result = await db.execute(total_query)
    total = total_result.scalar()
    
    return PaginatedResponse(
        items=[TaskResponse.model_validate(task) for task in tasks],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.post("", response_model=TaskResponse)
async def create_task(
    project_id: UUID,
    task_data: TaskCreate,
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
    
    # Get max position for the status
    max_pos_result = await db.execute(
        select(func.max(Task.position)).where(
            Task.project_id == project_id,
            Task.status == task_data.status,
        )
    )
    max_position = max_pos_result.scalar() or 0
    
    task = Task(
        project_id=project_id,
        milestone_id=task_data.milestone_id,
        parent_task_id=task_data.parent_task_id,
        assignee_id=task_data.assignee_id,
        reporter_id=user_id,
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        priority=task_data.priority,
        story_points=task_data.story_points,
        estimated_hours=task_data.estimated_hours,
        due_date=task_data.due_date,
        blocked_reason=task_data.blocked_reason,
        position=max_position + 1,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.model_validate(task)


@router.get("/{task_id}", response_model=TaskWithRelations)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.assignee),
            selectinload(Task.reporter),
            selectinload(Task.subtasks),
            selectinload(Task.comments),
        )
        .join(Project, Project.id == Task.project_id)
        .where(Task.id == task_id, Project.organization_id == org_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    # Build response with relations
    task_data = TaskResponse.model_validate(task)
    comments_count = len(task.comments) if task.comments else 0
    
    # Count dependencies
    blocking_count_result = await db.execute(
        select(func.count(TaskDependency.id)).where(TaskDependency.blocking_task_id == task_id)
    )
    blocked_count_result = await db.execute(
        select(func.count(TaskDependency.id)).where(TaskDependency.blocked_task_id == task_id)
    )
    
    return TaskWithRelations(
        **task_data.model_dump(),
        assignee=task.assignee,
        reporter=task.reporter,
        subtasks=[TaskResponse.model_validate(t) for t in task.subtasks] if task.subtasks else [],
        comments_count=comments_count,
        dependencies_count=(blocking_count_result.scalar() or 0) + (blocked_count_result.scalar() or 0),
    )


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Task.id == task_id, Project.organization_id == org_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    for field, value in task_data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}")
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Task.id == task_id, Project.organization_id == org_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    await db.delete(task)
    await db.commit()
    
    return {"message": "Task deleted"}


@router.patch("/{task_id}/move", response_model=TaskResponse)
async def move_task(
    task_id: UUID,
    move_data: TaskMove,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Task.id == task_id, Project.organization_id == org_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    old_status = task.status
    new_status = move_data.status or old_status
    
    # Update position if provided
    if move_data.position is not None:
        task.position = move_data.position
    
    # Update status if changed
    if move_data.status and move_data.status != old_status:
        task.status = move_data.status
        
        # Update timestamps
        from datetime import datetime
        if move_data.status == "in_progress" and not task.started_at:
            task.started_at = datetime.utcnow()
        elif move_data.status == "done" and not task.completed_at:
            task.completed_at = datetime.utcnow()
    
    # Update milestone if provided
    if move_data.milestone_id is not None:
        task.milestone_id = move_data.milestone_id
    
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.model_validate(task)


# Subtasks
@router.post("/{task_id}/subtasks", response_model=TaskResponse)
async def create_subtask(
    task_id: UUID,
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    user_id: UUID = Depends(get_current_user_id),
):
    parent_result = await db.execute(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Task.id == task_id, Project.organization_id == org_id)
    )
    parent_task = parent_result.scalar_one_or_none()
    
    if not parent_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent task not found",
        )
    
    task = Task(
        project_id=parent_task.project_id,
        parent_task_id=task_id,
        assignee_id=task_data.assignee_id,
        reporter_id=user_id,
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        priority=task_data.priority,
        story_points=task_data.story_points,
        estimated_hours=task_data.estimated_hours,
        due_date=task_data.due_date,
        blocked_reason=task_data.blocked_reason,
        position=0,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.model_validate(task)


# Dependencies
@router.get("/{task_id}/dependencies", response_model=list[TaskDependencyResponse])
async def list_dependencies(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    # Verify task belongs to org
    task_result = await db.execute(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Task.id == task_id, Project.organization_id == org_id)
    )
    if not task_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    # Get blocking dependencies (tasks that block this task)
    blocking_result = await db.execute(
        select(TaskDependency).where(TaskDependency.blocked_task_id == task_id)
    )
    blocking = blocking_result.scalars().all()
    
    # Get blocked dependencies (tasks this task blocks)
    blocked_result = await db.execute(
        select(TaskDependency).where(TaskDependency.blocking_task_id == task_id)
    )
    blocked = blocked_result.scalars().all()
    
    return [
        TaskDependencyResponse.model_validate(d) for d in blocking + blocked
    ]


@router.post("/{task_id}/dependencies", response_model=TaskDependencyResponse)
async def add_dependency(
    task_id: UUID,
    dep_data: TaskDependencyCreate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    # Verify both tasks exist and belong to org
    for tid in [dep_data.blocking_task_id, dep_data.blocked_task_id]:
        result = await db.execute(
            select(Task)
            .join(Project, Project.id == Task.project_id)
            .where(Task.id == tid, Project.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {tid} not found",
            )
    
    # Check for circular dependency
    # Simple check: ensure we're not creating a cycle
    if dep_data.blocking_task_id == dep_data.blocked_task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create dependency on self",
        )
    
    dep = TaskDependency(
        project_id=(await db.execute(select(Task.project_id).where(Task.id == dep_data.blocking_task_id))).scalar(),
        blocking_task_id=dep_data.blocking_task_id,
        blocked_task_id=dep_data.blocked_task_id,
        dependency_type=dep_data.dependency_type,
    )
    db.add(dep)
    await db.commit()
    await db.refresh(dep)
    
    return TaskDependencyResponse.model_validate(dep)


@router.delete("/{task_id}/dependencies/{dep_id}")
async def remove_dependency(
    task_id: UUID,
    dep_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(TaskDependency).where(TaskDependency.id == dep_id)
    )
    dep = result.scalar_one_or_none()
    
    if not dep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dependency not found",
        )
    
    await db.delete(dep)
    await db.commit()
    
    return {"message": "Dependency removed"}


# Comments
@router.get("/{task_id}/comments", response_model=PaginatedResponse)
async def list_comments(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    pagination: PaginatedResponse = Depends(get_pagination_params),
):
    task_result = await db.execute(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Task.id == task_id, Project.organization_id == org_id)
    )
    if not task_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    result = await db.execute(
        select(TaskComment)
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    comments = result.scalars().all()
    
    total_result = await db.execute(
        select(func.count(TaskComment.id)).where(TaskComment.task_id == task_id)
    )
    total = total_result.scalar()
    
    return PaginatedResponse(
        items=[TaskCommentResponse.model_validate(c) for c in comments],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.post("/{task_id}/comments", response_model=TaskCommentResponse)
async def add_comment(
    task_id: UUID,
    comment_data: TaskCommentCreate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    user_id: UUID = Depends(get_current_user_id),
):
    task_result = await db.execute(
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(Task.id == task_id, Project.organization_id == org_id)
    )
    if not task_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    comment = TaskComment(
        task_id=task_id,
        user_id=user_id,
        content=comment_data.content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    
    return TaskCommentResponse.model_validate(comment)