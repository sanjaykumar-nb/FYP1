import pytest
from httpx import AsyncClient

from app.core.permissions import default_roles
from app.core.security import create_access_token, get_password_hash
from app.models.role import UserRole
from app.models.organization import Organization
from app.models.project import Project
from app.models.task import Task
from app.models.user import User

pytestmark = pytest.mark.mvp


async def _task(client: AsyncClient, headers, project_id, title):
    response = await client.post(f"/api/v1/projects/{project_id}/tasks", json={"title": title}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _block(client: AsyncClient, headers, project_id, *, blocked, blocking):
    return await client.post(
        f"/api/v1/projects/{project_id}/tasks/{blocked}/dependencies",
        json={"blocking_task_id": blocking},
        headers=headers,
    )


class TestDependencies:
    async def test_circular_dependency_rejected(self, client: AsyncClient, auth_headers, test_project):
        pid = test_project.id
        a, b, c = [await _task(client, auth_headers, pid, title) for title in "ABC"]
        assert (await _block(client, auth_headers, pid, blocked=b, blocking=a)).status_code == 201
        assert (await _block(client, auth_headers, pid, blocked=c, blocking=b)).status_code == 201

        # A blocks B blocks C, so C blocking A would close a loop.
        response = await _block(client, auth_headers, pid, blocked=a, blocking=c)
        assert response.status_code == 400
        assert "circular" in response.json()["detail"]

    async def test_duplicate_dependency_rejected(self, client: AsyncClient, auth_headers, test_project):
        pid = test_project.id
        a, b = [await _task(client, auth_headers, pid, title) for title in "AB"]
        assert (await _block(client, auth_headers, pid, blocked=b, blocking=a)).status_code == 201
        assert (await _block(client, auth_headers, pid, blocked=b, blocking=a)).status_code == 409

    async def test_self_dependency_rejected(self, client: AsyncClient, auth_headers, test_project, test_task):
        response = await _block(
            client, auth_headers, test_project.id, blocked=test_task.id, blocking=str(test_task.id)
        )
        assert response.status_code == 400

    async def test_blocker_from_another_project_rejected(
        self, client: AsyncClient, auth_headers, test_project, test_task, test_org, test_user, db_session
    ):
        other = Project(organization_id=test_org.id, name="Other", key="OTH", status="active")
        db_session.add(other)
        await db_session.commit()
        foreign = Task(
            project_id=other.id, reporter_id=test_user.id, title="Elsewhere",
            status="backlog", priority="medium", position=0,
        )
        db_session.add(foreign)
        await db_session.commit()

        response = await _block(
            client, auth_headers, test_project.id, blocked=test_task.id, blocking=str(foreign.id)
        )
        assert response.status_code == 404

    async def test_project_dependencies_listed_and_removed(self, client: AsyncClient, auth_headers, test_project):
        pid = test_project.id
        a, b = [await _task(client, auth_headers, pid, title) for title in "AB"]
        dep = (await _block(client, auth_headers, pid, blocked=b, blocking=a)).json()

        listed = await client.get(f"/api/v1/projects/{pid}/dependencies", headers=auth_headers)
        assert listed.status_code == 200
        assert [(d["blocking_task_id"], d["blocked_task_id"]) for d in listed.json()] == [(a, b)]

        removed = await client.delete(
            f"/api/v1/projects/{pid}/tasks/{b}/dependencies/{dep['id']}", headers=auth_headers
        )
        assert removed.status_code == 204
        assert (await client.get(f"/api/v1/projects/{pid}/dependencies", headers=auth_headers)).json() == []

    async def test_other_org_cannot_see_or_remove_dependencies(
        self, client: AsyncClient, auth_headers, test_project, db_session
    ):
        pid = test_project.id
        a, b = [await _task(client, auth_headers, pid, title) for title in "AB"]
        dep = (await _block(client, auth_headers, pid, blocked=b, blocking=a)).json()

        org = Organization(name="Other Org", slug="other-org", settings={})
        db_session.add(org)
        await db_session.commit()
        roles = default_roles(org.id)
        intruder = User(
            organization_id=org.id, email="intruder@example.com",
            password_hash=get_password_hash("password123"), full_name="Intruder", is_active=True,
        )
        db_session.add_all([*roles, intruder])
        await db_session.commit()
        # An owner of their own organization: tenancy, not role, is what must stop them.
        owner = next(r for r in roles if r.name == "owner")
        db_session.add(UserRole(user_id=intruder.id, role_id=owner.id, organization_id=org.id))
        await db_session.commit()
        intruder_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(intruder.id), 'org_id': str(org.id)})}"
        }

        listed = await client.get(f"/api/v1/projects/{pid}/dependencies", headers=intruder_headers)
        assert listed.status_code == 404
        removed = await client.delete(
            f"/api/v1/projects/{pid}/tasks/{b}/dependencies/{dep['id']}", headers=intruder_headers
        )
        assert removed.status_code == 404
        still_there = await client.get(f"/api/v1/projects/{pid}/dependencies", headers=auth_headers)
        assert len(still_there.json()) == 1


class TestComments:
    async def test_comments_name_their_author_and_read_oldest_first(
        self, client: AsyncClient, auth_headers, test_project, test_task
    ):
        url = f"/api/v1/projects/{test_project.id}/tasks/{test_task.id}/comments"
        for text in ("first", "second", "third"):
            created = await client.post(url, json={"content": text}, headers=auth_headers)
            assert created.status_code == 201
            assert created.json()["author_name"] == "Test User"

        listed = (await client.get(url, headers=auth_headers)).json()
        assert [c["content"] for c in listed["items"]] == ["first", "second", "third"]
        assert {c["author_name"] for c in listed["items"]} == {"Test User"}
