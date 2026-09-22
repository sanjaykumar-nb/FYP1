from typing import Optional
from uuid import UUID
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.core.security import get_user_id_from_token, get_org_id_from_token, decode_token
from app.core.permissions import DEFAULT_ROLE, ROLE_RANK, has_permission, permissions_for
from app.models.role import Role, UserRole
from app.models.user import User


async def get_current_user_id(
    authorization: Optional[str] = Header(None),
) -> UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    user_id = get_user_id_from_token(token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_id


async def get_current_org_id(
    authorization: Optional[str] = Header(None),
) -> UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    org_id = get_org_id_from_token(token)
    
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return org_id


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    return user


class PaginationParams:
    def __init__(self, page: int = 1, page_size: int = 20):
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 100)
        self.offset = (self.page - 1) * self.page_size
        self.limit = self.page_size


async def get_pagination_params(page: int = 1, page_size: int = 20) -> PaginationParams:
    return PaginationParams(page, page_size)


class CurrentRole:
    """The caller's organization-level role and the permissions it grants."""

    def __init__(self, name: str, permissions: list[str]):
        self.name = name
        self.permissions = permissions

    def allows(self, permission: str) -> bool:
        return has_permission(self.permissions, permission)


async def get_current_role(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    org_id: UUID = Depends(get_current_org_id),
) -> CurrentRole:
    # Tokens are only checked against the database at sign-in and refresh. Every
    # permission check comes through here, so a deactivated account loses the
    # ability to change anything at once rather than when its token expires.
    active = (await db.execute(select(User.is_active).where(User.id == user_id))).scalar_one_or_none()
    if not active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
    result = await db.execute(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            UserRole.organization_id == org_id,
            UserRole.project_id.is_(None),
        )
    )
    roles = result.scalars().all()
    if not roles:
        return CurrentRole(DEFAULT_ROLE, permissions_for(DEFAULT_ROLE))
    role = max(roles, key=lambda r: ROLE_RANK.get(r.name, -1))
    return CurrentRole(role.name, permissions_for(role.name, role.permissions))


async def ensure_can_manage(
    db: AsyncSession, actor: CurrentRole, actor_id: UUID, org_id: UUID, user_id: UUID, action: str
) -> None:
    """403 unless the actor may take `action` (remove, deactivate) on this member.

    The rule role changes already follow: nobody acts on someone holding a role
    above their own — so an admin cannot remove or lock out the owner — and
    nobody does it to themselves, which would leave them locked out.
    """
    if user_id == actor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"You cannot {action} yourself")
    held = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, UserRole.organization_id == org_id)
    )
    if any(ROLE_RANK.get(name, ROLE_RANK["owner"]) > ROLE_RANK.get(actor.name, -1) for name in held.scalars().all()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot {action} someone whose role is above your own",
        )


def require_permission(permission: str):
    """Route dependency: 403 unless the caller's role grants `permission`."""

    async def check(role: CurrentRole = Depends(get_current_role)) -> CurrentRole:
        if not role.allows(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role ({role.name.replace('_', ' ')}) does not allow this",
            )
        return role

    return check