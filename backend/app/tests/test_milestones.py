from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.permissions import default_roles
from app.core.security import create_access_token, get_password_hash
from app.database import _add_missing_columns
from app.models.organization import Organization
from app.models.project import Milestone, Project
from app.models.role import UserRole
from app.models.user import User
from app.services.snapshot_builder import build_project_snapshot

pytestmark = pytest.mark.mvp


async def test_a_database_created_before_start_date_gains_the_column():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE milestones (id VARCHAR PRIMARY KEY, name VARCHAR)"))
        await conn.run_sync(_add_missing_columns)
        await conn.run_sync(_add_missing_columns)  # running it again is harmless
        columns = await conn.run_sync(lambda c: {col["name"] for col in inspect(c).get_columns("milestones")})
    await engine.dispose()
    assert "start_date" in columns


class TestMilestoneSchedule:
    async def test_start_date_reaches_the_analysis_snapshot(
        self, client: AsyncClient, auth_headers, test_project, db_session
    ):
        response = await client.post(
            f"/api/v1/projects/{test_project.id}/milestones",
            json={"name": "Sprint 1", "start_date": "2026-09-01T00:00:00", "target_date": "2026-09-15T00:00:00"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["start_date"].startswith("2026-09-01")

        snapshot = await build_project_snapshot(db_session, test_project)
        (milestone,) = snapshot["milestones"]
        assert milestone["start_date"].startswith("2026-09-01")
        assert milestone["target_date"].startswith("2026-09-15")

    async def test_start_date_is_optional(self, client: AsyncClient, auth_headers, test_project):
        response = await client.post(
            f"/api/v1/projects/{test_project.id}/milestones",
            json={"name": "Sprint 2", "target_date": "2026-09-15T00:00:00"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["start_date"] is None


async def _sprint(client: AsyncClient, headers, project_id, start="2026-09-01T00:00:00", end="2026-09-15T00:00:00"):
    response = await client.post(
        f"/api/v1/projects/{project_id}/milestones",
        json={"name": "Sprint", "start_date": start, "target_date": end},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestMilestoneRules:
    async def test_a_sprint_must_end_after_it_starts(self, client: AsyncClient, auth_headers, test_project):
        url = f"/api/v1/projects/{test_project.id}/milestones"
        backwards = await client.post(
            url, json={"name": "Backwards", "start_date": "2026-09-15T00:00:00", "target_date": "2026-09-01T00:00:00"},
            headers=auth_headers,
        )
        assert backwards.status_code == 400

        sprint = await _sprint(client, auth_headers, test_project.id)
        past_the_end = await client.patch(f"{url}/{sprint['id']}", json={"start_date": "2026-09-20T00:00:00"}, headers=auth_headers)
        assert past_the_end.status_code == 400
        moved = await client.patch(f"{url}/{sprint['id']}", json={"start_date": "2026-09-03T00:00:00"}, headers=auth_headers)
        assert moved.status_code == 200
        assert moved.json()["start_date"].startswith("2026-09-03")

    async def test_another_organization_cannot_edit_a_sprint(
        self, client: AsyncClient, auth_headers, test_project, db_session
    ):
        sprint = await _sprint(client, auth_headers, test_project.id)

        org = Organization(name="Other Org", slug="other-org", settings={})
        db_session.add(org)
        await db_session.commit()
        roles = default_roles(org.id)
        outsider = User(
            organization_id=org.id, email="outsider@example.com",
            password_hash=get_password_hash("password123"), full_name="Outsider", is_active=True,
        )
        db_session.add_all([*roles, outsider])
        await db_session.commit()
        owner = next(r for r in roles if r.name == "owner")
        db_session.add(UserRole(user_id=outsider.id, role_id=owner.id, organization_id=org.id))
        await db_session.commit()
        headers = {"Authorization": f"Bearer {create_access_token({'sub': str(outsider.id), 'org_id': str(org.id)})}"}

        response = await client.patch(
            f"/api/v1/projects/{test_project.id}/milestones/{sprint['id']}", json={"name": "Taken over"}, headers=headers
        )
        assert response.status_code == 404

    async def test_tasks_only_join_sprints_of_their_own_project(
        self, client: AsyncClient, auth_headers, test_project, test_task, test_org, db_session
    ):
        own = await _sprint(client, auth_headers, test_project.id)
        other = Project(organization_id=test_org.id, name="Other", key="OTH", status="active")
        db_session.add(other)
        await db_session.commit()
        foreign = Milestone(project_id=other.id, name="Elsewhere", target_date=date(2026, 9, 15))
        db_session.add(foreign)
        await db_session.commit()

        tasks = f"/api/v1/projects/{test_project.id}/tasks"
        stray = {"milestone_id": str(foreign.id)}
        assert (await client.post(tasks, json={"title": "Stray", **stray}, headers=auth_headers)).status_code == 400
        assert (await client.patch(f"{tasks}/{test_task.id}", json=stray, headers=auth_headers)).status_code == 400
        assert (await client.patch(f"{tasks}/{test_task.id}/move", json=stray, headers=auth_headers)).status_code == 400

        joined = await client.patch(f"{tasks}/{test_task.id}", json={"milestone_id": own["id"]}, headers=auth_headers)
        assert joined.status_code == 200
        assert joined.json()["milestone_id"] == own["id"]
        left = await client.patch(f"{tasks}/{test_task.id}", json={"milestone_id": None}, headers=auth_headers)
        assert left.status_code == 200
        assert left.json()["milestone_id"] is None
