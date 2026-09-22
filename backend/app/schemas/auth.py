from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional
from datetime import datetime
from uuid import UUID


class TokenBase(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class Token(TokenBase):
    pass


class TokenPayload(BaseModel):
    sub: UUID
    org_id: UUID
    exp: int
    type: str


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    organization_name: str = Field("My Organization", min_length=1, max_length=255)


class MemberCreate(UserBase):
    password: str = Field(..., min_length=8)
    role: str = "developer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None


class UserResponse(UserBase):
    id: UUID
    organization_id: UUID
    avatar_url: Optional[str] = None
    timezone: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectMemberResponse(UserResponse):
    role: str


class MeResponse(UserResponse):
    role: str
    permissions: list[str]


class ProjectMemberAdd(BaseModel):
    user_id: UUID
    role: str = "developer"


class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    settings: Optional[dict] = None


class OrganizationResponse(OrganizationBase):
    id: UUID
    settings: dict
    created_at: datetime

    class Config:
        from_attributes = True


class RoleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    permissions: list = []


class RoleCreate(RoleBase):
    pass


class RoleResponse(RoleBase):
    id: UUID
    organization_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class UserRoleAssign(BaseModel):
    user_id: UUID
    role_id: UUID
    project_id: Optional[UUID] = None


class TeamBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class TeamCreate(TeamBase):
    pass


class TeamResponse(TeamBase):
    id: UUID
    organization_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    key: str = Field(..., min_length=1, max_length=10)
    start_date: Optional[datetime] = None
    target_end_date: Optional[datetime] = None


class ProjectCreate(ProjectBase):
    team_id: Optional[UUID] = None


# The statuses the product understands. "archived" hides a project from the workspace
# without deleting it; setting any other status restores it.
ProjectStatus = Literal["active", "on_hold", "completed", "archived"]


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    start_date: Optional[datetime] = None
    target_end_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None
    # Story points per sprint; null clears it, so the team's measured velocity is used.
    sprint_capacity_points: Optional[int] = Field(None, ge=1, le=10000)


class ProjectResponse(ProjectBase):
    id: UUID
    organization_id: UUID
    team_id: Optional[UUID] = None
    status: str
    health_score: Optional[float] = None
    risk_score: Optional[float] = None
    actual_end_date: Optional[datetime] = None
    sprint_capacity_points: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MilestoneBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    target_date: datetime


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None
    status: Optional[str] = None
    progress: Optional[float] = None
    completed_at: Optional[datetime] = None


class MilestoneResponse(MilestoneBase):
    id: UUID
    project_id: UUID
    status: str
    progress: float
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int