from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from app.api.deps import get_db, get_current_user_id, get_current_org_id, get_pagination_params
from app.models.project import Project, ProjectMember, Milestone
from app.models.task import Task
from app.models.user import User
from app.schemas.auth import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    MilestoneCreate,
    MilestoneUpdate,
    MilestoneResponse,
    PaginatedResponse,
    UserResponse,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_projects(
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    pagination: PaginatedResponse = Depends(get_pagination_params),
    status: Optional[str] = Query(None),
    team_id: Optional[UUID] = Query(None),
):
    query = select(Project).where(Project.organization_id == org_id)
    total_query = select(func.count(Project.id)).where(Project.organization_id == org_id)

    if status:
        query = query.where(Project.status == status)
        total_query = total_query.where(Project.status == status)
    else:
        # Archived projects are hidden unless explicitly requested.
        query = query.where(Project.status != "archived")
        total_query = total_query.where(Project.status != "archived")
    if team_id:
        query = query.where(Project.team_id == team_id)
        total_query = total_query.where(Project.team_id == team_id)

    query = query.offset(pagination.offset).limit(pagination.limit).order_by(Project.created_at.desc())

    result = await db.execute(query)
    projects = result.scalars().all()
    
    total_result = await db.execute(total_query)
    total = total_result.scalar()
    
    return PaginatedResponse(
        items=[ProjectResponse.model_validate(project) for project in projects],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    user_id: UUID = Depends(get_current_user_id),
):
    # Check if key is unique within organization
    result = await db.execute(
        select(Project).where(
            Project.organization_id == org_id,
            Project.key == project_data.key.upper(),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project key already exists in this organization",
        )
    
    project = Project(
        organization_id=org_id,
        team_id=project_data.team_id,
        name=project_data.name,
        description=project_data.description,
        key=project_data.key.upper(),
        start_date=project_data.start_date,
        target_end_date=project_data.target_end_date,
    )
    db.add(project)
    await db.flush()
    
    # Add creator as project manager
    member = ProjectMember(
        project_id=project.id,
        user_id=user_id,
        role="project_manager",
    )
    db.add(member)
    
    await db.commit()
    await db.refresh(project)
    
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    # DELETE archives rather than hard-deletes; archived projects are not
    # retrievable through the normal read path.
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == org_id,
            Project.status != "archived",
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == org_id,
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    for field, value in project_data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    
    await db.commit()
    await db.refresh(project)
    
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == org_id,
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    project.status = "archived"
    await db.commit()


# Project members
@router.get("/{project_id}/members", response_model=PaginatedResponse)
async def list_project_members(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    pagination: PaginatedResponse = Depends(get_pagination_params),
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
    
    result = await db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    members = result.all()
    
    total_result = await db.execute(
        select(func.count(ProjectMember.id)).where(ProjectMember.project_id == project_id)
    )
    total = total_result.scalar()
    
    items = []
    for pm, user in members:
        user_resp = UserResponse.model_validate(user)
        user_resp.role = pm.role  # Add project role
        items.append(user_resp)
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.post("/{project_id}/members")
async def add_project_member(
    project_id: UUID,
    user_id: UUID,
    role: str = "developer",
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
    
    # Check if user is in organization
    user_result = await db.execute(
        select(User).where(User.id == user_id, User.organization_id == org_id)
    )
    if not user_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in organization",
        )
    
    # Check if already a member
    existing = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this project",
        )
    
    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    db.add(member)
    await db.commit()
    
    return {"message": "Member added"}


@router.patch("/{project_id}/members/{user_id}")
async def update_project_member(
    project_id: UUID,
    user_id: UUID,
    role: str,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    
    member.role = role
    await db.commit()
    
    return {"message": "Member role updated"}


@router.delete("/{project_id}/members/{user_id}")
async def remove_project_member(
    project_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    
    await db.delete(member)
    await db.commit()
    
    return {"message": "Member removed"}


# Milestones
@router.get("/{project_id}/milestones", response_model=PaginatedResponse)
async def list_milestones(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
    pagination: PaginatedResponse = Depends(get_pagination_params),
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
        select(Milestone)
        .where(Milestone.project_id == project_id)
        .order_by(Milestone.target_date)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    milestones = result.scalars().all()
    
    total_result = await db.execute(
        select(func.count(Milestone.id)).where(Milestone.project_id == project_id)
    )
    total = total_result.scalar()
    
    return PaginatedResponse(
        items=[MilestoneResponse.model_validate(m) for m in milestones],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.post("/{project_id}/milestones", response_model=MilestoneResponse)
async def create_milestone(
    project_id: UUID,
    milestone_data: MilestoneCreate,
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
    
    milestone = Milestone(
        project_id=project_id,
        name=milestone_data.name,
        description=milestone_data.description,
        target_date=milestone_data.target_date,
    )
    db.add(milestone)
    await db.commit()
    await db.refresh(milestone)
    
    return MilestoneResponse.model_validate(milestone)


@router.patch("/{project_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    project_id: UUID,
    milestone_id: UUID,
    milestone_data: MilestoneUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Milestone).where(
            Milestone.id == milestone_id,
            Milestone.project_id == project_id,
        )
    )
    milestone = result.scalar_one_or_none()
    
    if not milestone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milestone not found",
        )
    
    for field, value in milestone_data.model_dump(exclude_unset=True).items():
        setattr(milestone, field, value)
    
    await db.commit()
    await db.refresh(milestone)
    
    return MilestoneResponse.model_validate(milestone)