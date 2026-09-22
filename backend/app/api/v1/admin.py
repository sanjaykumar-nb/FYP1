from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.api.deps import (CurrentRole, ensure_can_manage, get_current_org_id, get_current_role,
                          get_current_user_id, get_db, get_pagination_params, require_permission)
from app.models.organization import Organization
from app.models.user import User
from app.models.memory import AuditLog, Notification
from app.models.project import Project
from app.models.task import Task
from app.schemas.analytics import AuditLogResponse, NotificationResponse
from app.schemas.auth import PaginatedResponse, UserResponse

# The admin area (organization stats, the user list, audit logs) is for admins and owners.
router = APIRouter(dependencies=[Depends(require_permission("settings:read"))])


@router.get("/stats")
async def get_org_stats(
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    # Get counts
    users_count = await db.execute(select(func.count(User.id)).where(User.organization_id == org_id))
    projects_count = await db.execute(select(func.count(Project.id)).where(Project.organization_id == org_id))
    tasks_count = await db.execute(
        select(func.count(Task.id))
        .join(Project, Project.id == Task.project_id)
        .where(Project.organization_id == org_id)
    )
    
    return {
        "users": users_count.scalar() or 0,
        "projects": projects_count.scalar() or 0,
        "tasks": tasks_count.scalar() or 0,
    }


@router.get("/audit-logs", response_model=PaginatedResponse)
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    pagination: PaginatedResponse = Depends(get_pagination_params),
    user_id: UUID = Query(None),
    action: str = Query(None),
    entity_type: str = Query(None),
):
    query = select(AuditLog).where(AuditLog.organization_id == org_id)
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    
    query = query.order_by(AuditLog.created_at.desc()).offset(pagination.offset).limit(pagination.limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    total_query = select(func.count(AuditLog.id)).where(AuditLog.organization_id == org_id)
    if user_id:
        total_query = total_query.where(AuditLog.user_id == user_id)
    if action:
        total_query = total_query.where(AuditLog.action == action)
    if entity_type:
        total_query = total_query.where(AuditLog.entity_type == entity_type)
    
    total_result = await db.execute(total_query)
    total = total_result.scalar()
    
    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.get("/users", response_model=PaginatedResponse)
async def list_all_users(
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    pagination: PaginatedResponse = Depends(get_pagination_params),
):
    result = await db.execute(
        select(User)
        .where(User.organization_id == org_id)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    users = result.scalars().all()
    
    total_result = await db.execute(
        select(func.count(User.id)).where(User.organization_id == org_id)
    )
    total = total_result.scalar()
    
    return PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


# Deactivating an account removes someone's access, so it needs the right to remove members.
@router.patch("/users/{user_id}", dependencies=[Depends(require_permission("member:remove"))])
async def update_user(
    user_id: UUID,
    is_active: bool,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    actor: CurrentRole = Depends(get_current_role),
    actor_id: UUID = Depends(get_current_user_id),
):
    await ensure_can_manage(db, actor, actor_id, org_id, user_id, "deactivate" if not is_active else "reactivate")
    result = await db.execute(
        select(User).where(User.id == user_id, User.organization_id == org_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    user.is_active = is_active
    await db.commit()
    
    return {"message": "User updated", "is_active": is_active}