from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.permissions import PERMISSIONS
from app.core.security import create_access_token, get_password_hash
from app.models.role import Role
from app.models.user import User

pytestmark = pytest.mark.mvp


def _new_member(email: str, role: str) -> dict:
    return {"email": email, "full_name": "New Person", "password": "password123", "role": role}


async def _expect_forbidden(client: AsyncClient, headers: dict, attempts: list[tuple[str, str, dict | None]]):
    for method, url, body in attempts:
        response = await client.request(method, url, json=body, headers=headers)
        assert response.status_code == 403, (method, url, response.status_code, response.text)


class TestViewer:
    async def test_viewer_can_read_the_project(self, client: AsyncClient, user_with_role, test_project, test_task):
        headers = await user_with_role("viewer")
        pid = test_project.id
        for url in (
            f"/api/v1/projects/{pid}",
            f"/api/v1/projects/{pid}/tasks",
            f"/api/v1/projects/{pid}/tasks/{test_task.id}/comments",
            f"/api/v1/projects/{pid}/dependencies",
            f"/api/v1/analytics/projects/{pid}/agent-runs",
        ):
            assert (await client.get(url, headers=headers)).status_code == 200, url

    async def test_viewer_cannot_change_anything(
        self, client: AsyncClient, user_with_role, auth_headers, test_project, test_task, test_org
    ):
        headers = await user_with_role("viewer")
        pid, tid = test_project.id, test_task.id
        await _expect_forbidden(client, headers, [
            ("post", f"/api/v1/projects/{pid}/tasks", {"title": "New"}),
            ("patch", f"/api/v1/projects/{pid}/tasks/{tid}", {"title": "Renamed"}),
            ("patch", f"/api/v1/projects/{pid}/tasks/{tid}/move", {"status": "done"}),
            ("delete", f"/api/v1/projects/{pid}/tasks/{tid}", None),
            ("post", f"/api/v1/projects/{pid}/tasks/{tid}/comments", {"content": "hello"}),
            ("post", f"/api/v1/projects/{pid}/tasks/{tid}/dependencies", {"blocking_task_id": str(uuid4())}),
            ("post", f"/api/v1/analytics/projects/{pid}/analyze", None),
            ("patch", f"/api/v1/projects/{pid}", {"name": "Renamed"}),
            ("post", f"/api/v1/organizations/{test_org.id}/members", _new_member("x@example.com", "viewer")),
        ])

        task = (await client.get(f"/api/v1/projects/{pid}/tasks/{tid}", headers=auth_headers)).json()
        assert (task["title"], task["status"]) == ("Test Task", "backlog")


class TestDeveloper:
    async def test_developer_does_the_work(self, client: AsyncClient, user_with_role, test_project, test_task):
        headers = await user_with_role("developer")
        base = f"/api/v1/projects/{test_project.id}/tasks"
        assert (await client.post(base, json={"title": "Dev task"}, headers=headers)).status_code == 201
        assert (await client.patch(f"{base}/{test_task.id}", json={"status": "in_progress"}, headers=headers)).status_code == 200
        assert (await client.post(f"{base}/{test_task.id}/comments", json={"content": "On it"}, headers=headers)).status_code == 201

    async def test_developer_cannot_manage_the_project(
        self, client: AsyncClient, user_with_role, test_project, test_task, test_org
    ):
        headers = await user_with_role("developer")
        pid = test_project.id
        await _expect_forbidden(client, headers, [
            ("delete", f"/api/v1/projects/{pid}/tasks/{test_task.id}", None),
            ("post", f"/api/v1/analytics/projects/{pid}/analyze", None),
            ("post", f"/api/v1/organizations/{test_org.id}/members", _new_member("y@example.com", "developer")),
            ("delete", f"/api/v1/projects/{pid}", None),
        ])


class TestGrantingRoles:
    async def test_manager_adds_teammates_but_never_above_their_own_role(
        self, client: AsyncClient, user_with_role, test_org
    ):
        headers = await user_with_role("project_manager")
        url = f"/api/v1/organizations/{test_org.id}/members"
        for email, role in (("dev@example.com", "developer"), ("pm2@example.com", "project_manager")):
            assert (await client.post(url, json=_new_member(email, role), headers=headers)).status_code == 201, role
        for role in ("admin", "owner"):
            response = await client.post(url, json=_new_member(f"{role}@team.example.com", role), headers=headers)
            assert response.status_code == 403, role

    async def test_project_roles_follow_the_same_rule(self, client: AsyncClient, user_with_role, test_project):
        headers = await user_with_role("project_manager")
        developer = (await client.get("/api/v1/auth/me", headers=await user_with_role("developer"))).json()
        url = f"/api/v1/projects/{test_project.id}/members"

        assert (await client.post(url, json={"user_id": developer["id"], "role": "owner"}, headers=headers)).status_code == 403
        assert (await client.post(url, json={"user_id": developer["id"], "role": "wizard"}, headers=headers)).status_code == 400
        assert (await client.post(url, json={"user_id": developer["id"], "role": "developer"}, headers=headers)).status_code == 201


class TestCurrentRole:
    async def test_me_reports_role_and_permissions(self, client: AsyncClient, auth_headers, user_with_role):
        me = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()
        assert (me["role"], me["permissions"]) == ("owner", ["*"])

        viewer = (await client.get("/api/v1/auth/me", headers=await user_with_role("viewer"))).json()
        assert viewer["role"] == "viewer"
        assert "task:update" not in viewer["permissions"]

    async def test_someone_without_a_role_is_a_viewer(self, client: AsyncClient, db_session, test_org, test_project):
        user = User(
            organization_id=test_org.id, email="norole@example.com",
            password_hash=get_password_hash("password123"), full_name="No Role", is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {create_access_token({'sub': str(user.id), 'org_id': str(test_org.id)})}"}

        assert (await client.get("/api/v1/auth/me", headers=headers)).json()["role"] == "viewer"
        response = await client.post(f"/api/v1/projects/{test_project.id}/tasks", json={"title": "x"}, headers=headers)
        assert response.status_code == 403

    async def test_registration_seeds_the_shared_policy(self, client: AsyncClient, db_session):
        token = (await client.post("/api/v1/auth/register", json={
            "email": "founder@example.com", "password": "password123",
            "full_name": "Founder", "organization_name": "Founders",
        })).json()["access_token"]
        me = (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})).json()
        assert me["role"] == "owner"

        org_id = UUID(me["organization_id"])
        roles = (await db_session.execute(select(Role).where(Role.organization_id == org_id))).scalars().all()
        assert {r.name: r.permissions for r in roles} == PERMISSIONS
