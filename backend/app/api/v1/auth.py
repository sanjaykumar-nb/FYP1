from datetime import datetime, timedelta
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db, get_current_user, get_current_user_id
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.models.organization import Organization
from app.models.role import Role, UserRole
from app.api.deps import CurrentRole, get_current_role
from app.core.permissions import default_roles
from app.schemas.auth import MeResponse
from app.schemas.auth import (
    Token,
    LoginRequest,
    RefreshRequest,
    UserCreate,
    UserUpdate,
    UserResponse,
    OrganizationCreate,
    OrganizationResponse,
    RoleCreate,
    RoleResponse,
    UserRoleAssign,
)

router = APIRouter()


@router.post("/register", response_model=Token)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create organization
    org_name = user_data.organization_name
    org_slug = org_name.lower().replace(" ", "-")[:100]

    # Slugs are globally unique; disambiguate on collision
    existing_slug = await db.execute(select(Organization).where(Organization.slug == org_slug))
    if existing_slug.scalar_one_or_none():
        org_slug = f"{org_slug[:91]}-{uuid4().hex[:8]}"

    org = Organization(name=org_name, slug=org_slug)
    db.add(org)
    await db.flush()
    
    # Create default roles
    roles = default_roles(org.id)
    db.add_all(roles)
    await db.flush()
    
    # Create user
    user = User(
        organization_id=org.id,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(user)
    await db.flush()
    
    # Assign owner role to user
    owner_role = next(r for r in roles if r.name == "owner")
    user_role = UserRole(
        user_id=user.id,
        role_id=owner_role.id,
        organization_id=org.id,
        project_id=None,
    )
    db.add(user_role)
    
    await db.commit()
    
    # Create tokens
    access_token = create_access_token({"sub": str(user.id), "org_id": str(org.id)})
    refresh_token = create_refresh_token({"sub": str(user.id), "org_id": str(org.id)})
    
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # OAuth2 spec names the identity field "username"; ours is an email address.
    email = form_data.username
    password = form_data.password

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()
    
    access_token = create_access_token({"sub": str(user.id), "org_id": str(user.organization_id)})
    refresh_token = create_refresh_token({"sub": str(user.id), "org_id": str(user.organization_id)})
    
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(body.refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    user_id = payload.get("sub")
    org_id = payload.get("org_id")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )
    
    new_access_token = create_access_token({"sub": user_id, "org_id": org_id})
    new_refresh_token = create_refresh_token({"sub": user_id, "org_id": org_id})
    
    return Token(access_token=new_access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=MeResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    role: CurrentRole = Depends(get_current_role),
):
    # The role lets the UI hide what this person cannot do; the API still enforces it.
    return MeResponse(
        **UserResponse.model_validate(current_user).model_dump(),
        role=role.name,
        permissions=role.permissions,
    )


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for field, value in user_data.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    return current_user