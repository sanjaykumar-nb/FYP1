from uuid import uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.mvp


def _member(email="dev@example.com", role="developer"):
    return {"email": email, "full_name": "Dev One", "password": "password123", "role": role}


class TestOrganizationMembers:
    async def test_added_member_can_sign_in(self, client: AsyncClient, auth_headers, test_org, db_session):

        response = await client.post(
            f"/api/v1/organizations/{test_org.id}/members", headers=auth_headers, json=_member()
        )
        assert response.status_code == 201
        assert response.json()["organization_id"] == str(test_org.id)

        login = await client.post(
            "/api/v1/auth/login", data={"username": "dev@example.com", "password": "password123"}
        )
        assert login.status_code == 200

    async def test_duplicate_email_rejected(self, client: AsyncClient, auth_headers, test_org, db_session):
        url = f"/api/v1/organizations/{test_org.id}/members"
        assert (await client.post(url, headers=auth_headers, json=_member())).status_code == 201
        assert (await client.post(url, headers=auth_headers, json=_member())).status_code == 409

    async def test_unknown_role_rejected(self, client: AsyncClient, auth_headers, test_org):
        response = await client.post(
            f"/api/v1/organizations/{test_org.id}/members", headers=auth_headers, json=_member(role="wizard")
        )
        assert response.status_code == 400

    async def test_cannot_add_member_to_another_org(self, client: AsyncClient, auth_headers):
        response = await client.post(
            f"/api/v1/organizations/{uuid4()}/members", headers=auth_headers, json=_member()
        )
        assert response.status_code == 403


class TestProjectMembers:
    async def test_add_then_list_members_with_roles(
        self, client: AsyncClient, auth_headers, test_org, test_project, db_session
    ):
        created = await client.post(
            f"/api/v1/organizations/{test_org.id}/members", headers=auth_headers, json=_member()
        )

        added = await client.post(
            f"/api/v1/projects/{test_project.id}/members",
            headers=auth_headers,
            json={"user_id": created.json()["id"], "role": "developer"},
        )
        assert added.status_code == 201

        listed = await client.get(f"/api/v1/projects/{test_project.id}/members", headers=auth_headers)
        assert listed.status_code == 200
        roles = {m["email"]: m["role"] for m in listed.json()["items"]}
        assert roles == {"test@example.com": "owner", "dev@example.com": "developer"}


class TestProjectDashboard:
    async def test_dashboard_reports_team_size(self, client: AsyncClient, auth_headers, test_project, test_task):
        response = await client.get(f"/api/v1/analytics/projects/{test_project.id}/dashboard", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["team_size"] == 1
