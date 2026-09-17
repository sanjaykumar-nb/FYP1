import pytest
from httpx import AsyncClient

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
