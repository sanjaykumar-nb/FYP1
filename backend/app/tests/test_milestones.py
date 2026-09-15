import pytest
from httpx import AsyncClient
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import _add_missing_columns
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
