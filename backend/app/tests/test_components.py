import pytest
from httpx import AsyncClient

from app.services.snapshot_builder import build_project_snapshot

pytestmark = pytest.mark.mvp


class TestTaskComponent:
    async def test_component_is_saved_normalised_and_clearable(
        self, client: AsyncClient, auth_headers, test_project
    ):
        tasks = f"/api/v1/projects/{test_project.id}/tasks"
        created = await client.post(
            tasks, json={"title": "Payments bug", "component": "  Payment   service "}, headers=auth_headers
        )
        assert created.status_code == 201
        assert created.json()["component"] == "Payment service"

        cleared = await client.patch(f"{tasks}/{created.json()['id']}", json={"component": "  "}, headers=auth_headers)
        assert cleared.status_code == 200
        assert cleared.json()["component"] is None

    async def test_component_reaches_the_analysis_snapshot(
        self, client: AsyncClient, auth_headers, test_project, test_task, db_session
    ):
        response = await client.patch(
            f"/api/v1/projects/{test_project.id}/tasks/{test_task.id}", json={"component": "Scheduler"},
            headers=auth_headers,
        )
        assert response.status_code == 200

        snapshot = await build_project_snapshot(db_session, test_project)
        (task,) = snapshot["tasks"]
        assert task["component"] == "Scheduler"
