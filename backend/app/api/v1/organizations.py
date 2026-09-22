from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, func
from sqlalchemy.orm import selectinload
from app.api.deps import get_db, get_current_user, get_current_user_id, get_current_org_id, get_pagination_params
from app.core.security import get_password_hash_async
from app.models.organization import Organization
from app.models.user import User
from app.models.project import Project, ProjectMember
from app.models.role import Role, UserRole
from app.api.deps import CurrentRole, ensure_can_manage, get_current_role, require_permission
from app.core.permissions import can_grant, default_roles
from app.models.team import Team, TeamMember
from app.schemas.auth import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    RoleCreate,
    RoleResponse,
    UserRoleAssign,
    TeamBase,
    TeamCreate,
    TeamResponse,
    PaginatedResponse,
    UserResponse,
    MemberCreate,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    pagination: PaginatedResponse = Depends(get_pagination_params),
):
    # Get organizations where user is a member
    result = await db.execute(
        select(Organization)
        .join(User, User.organization_id == Organization.id)
        .where(User.id == user_id)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    organizations = result.scalars().all()
    
    total_result = await db.execute(
        select(func.count(Organization.id))
        .join(User, User.organization_id == Organization.id)
        .where(User.id == user_id)
    )
    total = total_result.scalar()
    
    return PaginatedResponse(
        items=[OrganizationResponse.model_validate(org) for org in organizations],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.post("", response_model=OrganizationResponse)
async def create_organization(
    org_data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    # Check if slug is taken
    result = await db.execute(select(Organization).where(Organization.slug == org_data.slug))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already taken",
        )
    
    org = Organization(name=org_data.name, slug=org_data.slug, settings=org_data.settings or {})
    db.add(org)
    await db.flush()
    
    # Create default roles
    roles = default_roles(org.id)
    db.add_all(roles)
    await db.flush()
    
    # Assign owner role to creator
    owner_role = next(r for r in roles if r.name == "owner")
    user_role = UserRole(
        user_id=user_id,
        role_id=owner_role.id,
        organization_id=org.id,
    )
    db.add(user_role)
    
    # Add user to organization
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.organization_id = org.id
    
    await db.commit()
    await db.refresh(org)
    
    return OrganizationResponse.model_validate(org)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
):
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    
    return OrganizationResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrganizationResponse,
              dependencies=[Depends(require_permission("organization:update"))])
async def update_organization(
    org_id: UUID,
    org_data: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
):
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    
    for field, value in org_data.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    
    await db.commit()
    await db.refresh(org)
    
    return OrganizationResponse.model_validate(org)


@router.post("/{org_id}/members", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission("member:invite"))])
async def add_member(
    org_id: UUID,
    member: MemberCreate,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
    actor: CurrentRole = Depends(get_current_role),
):
    """Create a teammate's account inside this organization.

    Registration always creates a new organization, so without this there is no
    way to put a second person in an existing org — and therefore nobody to
    assign tasks to. The creator supplies an initial password and shares it.
    """
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    existing = await db.execute(select(User).where(User.email == member.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    role_result = await db.execute(
        select(Role).where(Role.organization_id == org_id, Role.name == member.role)
    )
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown role '{member.role}'",
        )
    if not can_grant(actor.name, role.name):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"A {actor.name.replace('_', ' ')} cannot grant the {role.name.replace('_', ' ')} role",
        )

    user = User(
        organization_id=org_id,
        email=member.email,
        password_hash=await get_password_hash_async(member.password),
        full_name=member.full_name,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id, organization_id=org_id, project_id=None))
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/{org_id}/members", response_model=PaginatedResponse)
async def list_members(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
    pagination: PaginatedResponse = Depends(get_pagination_params),
):
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
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
        items=[UserResponse.model_validate(user) for user in users],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.patch("/{org_id}/members/{user_id}", dependencies=[Depends(require_permission("member:update_role"))])
async def update_member_role(
    org_id: UUID,
    user_id: UUID,
    role_id: UUID,
    project_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
    actor: CurrentRole = Depends(get_current_role),
):
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    new_role = (
        await db.execute(select(Role).where(Role.id == role_id, Role.organization_id == org_id))
    ).scalar_one_or_none()
    if not new_role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role")
    held = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, UserRole.organization_id == org_id)
    )
    # Neither grant a role above your own nor change the role of someone above you.
    if not all(can_grant(actor.name, name) for name in [new_role.name, *held.scalars().all()]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot grant a role above your own or change the role of someone above you",
        )
    
    # Find existing user role
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.organization_id == org_id,
            UserRole.project_id == project_id,
        )
    )
    user_role = result.scalar_one_or_none()
    
    if user_role:
        user_role.role_id = role_id
    else:
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            organization_id=org_id,
            project_id=project_id,
        )
        db.add(user_role)
    
    await db.commit()
    
    return {"message": "Role updated"}


@router.delete("/{org_id}/members/{user_id}", dependencies=[Depends(require_permission("member:remove"))])
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
    actor: CurrentRole = Depends(get_current_role),
    actor_id: UUID = Depends(get_current_user_id),
):
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    await ensure_can_manage(db, actor, actor_id, org_id, user_id, "remove")

    user = (
        await db.execute(select(User).where(User.id == user_id, User.organization_id == org_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # A person belongs to exactly one organization (users.organization_id is required),
    # so removal revokes access rather than detaching them: their roles and project
    # memberships go, and the account is disabled.
    await db.execute(delete(UserRole).where(UserRole.user_id == user_id, UserRole.organization_id == org_id))
    await db.execute(
        delete(ProjectMember).where(
            ProjectMember.user_id == user_id,
            ProjectMember.project_id.in_(select(Project.id).where(Project.organization_id == org_id)),
        )
    )
    user.is_active = False

    await db.commit()
    
    return {"message": "Member removed"}


# Teams endpoints
@router.get("/{org_id}/teams", response_model=PaginatedResponse)
async def list_teams(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
    pagination: PaginatedResponse = Depends(get_pagination_params),
):
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    result = await db.execute(
        select(Team)
        .where(Team.organization_id == org_id)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    teams = result.scalars().all()
    
    total_result = await db.execute(
        select(func.count(Team.id)).where(Team.organization_id == org_id)
    )
    total = total_result.scalar()
    
    return PaginatedResponse(
        items=[TeamResponse.model_validate(team) for team in teams],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.post("/{org_id}/teams", response_model=TeamResponse,
             dependencies=[Depends(require_permission("member:invite"))])
async def create_team(
    org_id: UUID,
    team_data: TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
):
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    team = Team(organization_id=org_id, name=team_data.name, description=team_data.description)
    db.add(team)
    await db.commit()
    await db.refresh(team)
    
    return TeamResponse.model_validate(team)


@router.post("/{org_id}/teams/{team_id}/members", dependencies=[Depends(require_permission("member:invite"))])
async def add_team_member(
    org_id: UUID,
    team_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
):
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    member = TeamMember(team_id=team_id, user_id=user_id)
    db.add(member)
    await db.commit()
    
    return {"message": "Member added"}


# Roles endpoints
@router.get("/{org_id}/roles", response_model=list[RoleResponse])
async def list_roles(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
):
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    result = await db.execute(select(Role).where(Role.organization_id == org_id))
    roles = result.scalars().all()
    
    return [RoleResponse.model_validate(role) for role in roles]


@router.post("/{org_id}/roles", response_model=RoleResponse,
             dependencies=[Depends(require_permission("settings:update"))])
async def create_role(
    org_id: UUID,
    role_data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_org_id: UUID = Depends(get_current_org_id),
):
    if org_id != current_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    role = Role(organization_id=org_id, name=role_data.name, permissions=role_data.permissions)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    return RoleResponse.model_validate(role)