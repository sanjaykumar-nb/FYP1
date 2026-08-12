from functools import wraps
from typing import Callable
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.security import get_user_id_from_token, get_org_id_from_token
from app.database import get_db
from app.models.role import Role, UserRole
from app.models.user import User


# Permission definitions
PERMISSIONS = {
    "owner": ["*"],
    "admin": [
        "organization:read", "organization:update", "organization:delete",
        "project:create", "project:read", "project:update", "project:delete",
        "task:create", "task:read", "task:update", "task:delete",
        "member:invite", "member:remove", "member:update_role",
        "analytics:read", "settings:read", "settings:update",
    ],
    "project_manager": [
        "project:read", "project:update",
        "task:create", "task:read", "task:update", "task:delete",
        "member:invite", "member:update_role",
        "analytics:read", "meeting:create", "meeting:read", "meeting:update",
    ],
    "developer": [
        "project:read",
        "task:create", "task:read", "task:update",
        "meeting:read",
    ],
    "viewer": [
        "project:read",
        "task:read",
        "meeting:read",
    ],
}


def has_permission(user_role: str, permission: str) -> bool:
    role_permissions = PERMISSIONS.get(user_role, [])
    return "*" in role_permissions or permission in role_permissions


async def get_current_user_role(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id_from_token),
    org_id: str = Depends(get_org_id_from_token),
) -> str:
    # Check user role for project
    result = await db.execute(
        select(UserRole.role_id)
        .where(UserRole.user_id == user_id)
        .where(UserRole.organization_id == org_id)
        .where(UserRole.project_id == project_id)
    )
    user_role_id = result.scalar_one_or_none()
    
    if user_role_id:
        role_result = await db.execute(select(Role).where(Role.id == user_role_id))
        role = role_result.scalar_one_or_none()
        if role:
            return role.name
    
    # Check org-level role
    result = await db.execute(
        select(UserRole.role_id)
        .where(UserRole.user_id == user_id)
        .where(UserRole.organization_id == org_id)
        .where(UserRole.project_id.is_(None))
    )
    user_role_id = result.scalar_one_or_none()
    
    if user_role_id:
        role_result = await db.execute(select(Role).where(Role.id == user_role_id))
        role = role_result.scalar_one_or_none()
        if role:
            return role.name
    
    return "viewer"


def require_permission(permission: str):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # This would need to be implemented with proper dependency injection
            # For now, we'll rely on the service layer for permission checks
            return await func(*args, **kwargs)
        return wrapper
    return decorator