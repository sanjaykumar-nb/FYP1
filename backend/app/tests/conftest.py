import asyncio
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.main import app
from app.database import get_db, Base
from app.config import get_settings
from app.models.user import User
from app.models.organization import Organization
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.role import Role, UserRole
from app.core.permissions import default_roles
from app.core.security import get_password_hash, create_access_token
from sqlalchemy import select
from uuid import uuid4
from datetime import datetime

settings = get_settings()

# SQLite in memory by default. CI also runs the suite against PostgreSQL, the
# database the Docker setup uses, by pointing TEST_DATABASE_URL at one.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or "sqlite+aiosqlite:///:memory:"

if TEST_DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # Each test runs in its own event loop; a pooled asyncpg connection would
    # outlive the loop it was opened on.
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


def pytest_sessionfinish(session, exitstatus):
    # The in-memory database keeps one connection open for the whole run, and
    # aiosqlite serves each connection from a non-daemon thread. Left open, it
    # holds the process after the last test: the run prints "passed" and never
    # exits.
    asyncio.run(engine.dispose())


@pytest_asyncio.fixture
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_org(db_session: AsyncSession):
    org = Organization(name="Test Org", slug="test-org", settings={})
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    db_session.add_all(default_roles(org.id))
    await db_session.commit()
    return org


async def assign_role(db_session: AsyncSession, user: User, org: Organization, role_name: str) -> None:
    role = (
        await db_session.execute(select(Role).where(Role.organization_id == org.id, Role.name == role_name))
    ).scalar_one()
    db_session.add(UserRole(user_id=user.id, role_id=role.id, organization_id=org.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_org: Organization):
    user = User(
        organization_id=test_org.id,
        email="test@example.com",
        password_hash=get_password_hash("password123"),
        full_name="Test User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    await assign_role(db_session, user, test_org, "owner")
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User):
    token = create_access_token({"sub": str(test_user.id), "org_id": str(test_user.organization_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_with_role(db_session: AsyncSession, test_org: Organization):
    """Factory: a signed-in teammate in test_org holding the given role; returns auth headers."""

    async def create(role_name: str) -> dict:
        user = User(
            organization_id=test_org.id,
            email=f"{role_name}@example.com",
            password_hash=get_password_hash("password123"),
            full_name=role_name.replace("_", " ").title(),
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await assign_role(db_session, user, test_org, role_name)
        token = create_access_token({"sub": str(user.id), "org_id": str(test_org.id)})
        return {"Authorization": f"Bearer {token}"}

    return create


@pytest_asyncio.fixture
async def test_project(db_session: AsyncSession, test_org: Organization, test_user: User):
    project = Project(
        organization_id=test_org.id,
        team_id=None,
        name="Test Project",
        description="Test project description",
        key="TEST",
        status="active",
        start_date=datetime.utcnow().date(),
        target_end_date=None,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    member = ProjectMember(project_id=project.id, user_id=test_user.id, role="owner")
    db_session.add(member)
    await db_session.commit()
    return project


@pytest_asyncio.fixture
async def test_task(db_session: AsyncSession, test_project: Project, test_user: User):
    task = Task(
        project_id=test_project.id,
        assignee_id=test_user.id,
        reporter_id=test_user.id,
        title="Test Task",
        description="Test task description",
        status="backlog",
        priority="medium",
        story_points=5,
        position=0,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task