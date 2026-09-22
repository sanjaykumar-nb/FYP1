from datetime import date
from types import SimpleNamespace as Row

import pytest
from httpx import AsyncClient

from app.services.snapshot_builder import build_project_snapshot, velocity_history

pytestmark = pytest.mark.mvp


class TestProjectSettings:
    async def test_a_project_must_end_after_it_starts(self, client: AsyncClient, auth_headers, test_project):
        url = f"/api/v1/projects/{test_project.id}"
        backwards = await client.patch(
            url, json={"start_date": "2026-10-10T00:00:00", "target_end_date": "2026-10-01T00:00:00"},
            headers=auth_headers,
        )
        assert backwards.status_code == 400

        updated = await client.patch(
            url,
            json={"description": "Updated", "start_date": "2026-10-01T00:00:00", "target_end_date": "2026-12-01T00:00:00"},
            headers=auth_headers,
        )
        assert updated.status_code == 200
        assert updated.json()["description"] == "Updated"
        assert updated.json()["target_end_date"].startswith("2026-12-01")

    async def test_a_developer_cannot_change_or_archive_a_project(
        self, client: AsyncClient, user_with_role, test_project
    ):
        headers = await user_with_role("developer")
        url = f"/api/v1/projects/{test_project.id}"
        assert (await client.patch(url, json={"name": "Renamed"}, headers=headers)).status_code == 403
        assert (await client.delete(url, headers=headers)).status_code == 403

    async def test_an_archived_project_can_be_found_and_restored(
        self, client: AsyncClient, auth_headers, test_project
    ):
        url = f"/api/v1/projects/{test_project.id}"
        assert (await client.delete(url, headers=auth_headers)).status_code == 204

        listed = await client.get("/api/v1/projects", headers=auth_headers)
        assert test_project.name not in [p["name"] for p in listed.json()["items"]]
        archived = await client.get("/api/v1/projects", params={"status": "archived"}, headers=auth_headers)
        assert [p["name"] for p in archived.json()["items"]] == [test_project.name]

        restored = await client.patch(url, json={"status": "active"}, headers=auth_headers)
        assert restored.status_code == 200
        assert (await client.get(url, headers=auth_headers)).json()["status"] == "active"

    async def test_a_project_status_must_be_one_the_product_knows(
        self, client: AsyncClient, auth_headers, test_project
    ):
        url = f"/api/v1/projects/{test_project.id}"
        assert (await client.patch(url, json={"status": "banana"}, headers=auth_headers)).status_code == 422
        assert (await client.patch(url, json={"status": "on_hold"}, headers=auth_headers)).status_code == 200


class TestSprintCapacity:
    async def test_capacity_is_set_cleared_and_reaches_the_analysis(
        self, client: AsyncClient, auth_headers, test_project, db_session
    ):
        url = f"/api/v1/projects/{test_project.id}"
        assert (await client.patch(url, json={"sprint_capacity_points": 0}, headers=auth_headers)).status_code == 422

        updated = await client.patch(url, json={"sprint_capacity_points": 34}, headers=auth_headers)
        assert updated.status_code == 200
        assert updated.json()["sprint_capacity_points"] == 34
        await db_session.refresh(test_project)
        assert (await build_project_snapshot(db_session, test_project))["team_capacity_points"] == 34

        # Clearing it hands the estimate back to the team's measured velocity.
        cleared = await client.patch(url, json={"sprint_capacity_points": None}, headers=auth_headers)
        assert cleared.json()["sprint_capacity_points"] is None

    async def test_a_developer_cannot_change_capacity(self, client: AsyncClient, user_with_role, test_project):
        headers = await user_with_role("developer")
        response = await client.patch(f"/api/v1/projects/{test_project.id}", json={"sprint_capacity_points": 99},
                                      headers=headers)
        assert response.status_code == 403

    def test_velocity_is_what_each_finished_sprint_completed(self):
        sprints = [
            Row(id="c", status="upcoming", target_date=date(2026, 10, 1)),  # not over yet
            Row(id="b", status="active", target_date=date(2026, 9, 15)),    # past its end date
            Row(id="a", status="completed", target_date=date(2026, 9, 1)),
        ]
        tasks = [
            Row(milestone_id="a", status="done", story_points=5),
            Row(milestone_id="a", status="done", story_points=None),        # unestimated
            Row(milestone_id="a", status="in_progress", story_points=8),    # not finished
            Row(milestone_id="b", status="done", story_points=13),
            Row(milestone_id="c", status="done", story_points=3),
        ]
        assert velocity_history(sprints, tasks, today=date(2026, 9, 20)) == [5.0, 13.0]
