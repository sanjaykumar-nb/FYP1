"""Nobody can lock out or remove someone ranked above them, or themselves.

These were open before v1.0-mvp was hardened: the admin deactivation endpoint had
no role check at all (a viewer could deactivate the owner), and member removal had
no rank check (an admin could remove the owner).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.role import UserRole
from app.models.user import User

pytestmark = pytest.mark.mvp


async def _me(client: AsyncClient, headers: dict) -> str:
    return (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]


async def _deactivate(client: AsyncClient, headers: dict, user_id) -> int:
    response = await client.patch(f"/api/v1/admin/users/{user_id}", params={"is_active": False}, headers=headers)
    return response.status_code


class TestDeactivation:
    async def test_a_viewer_cannot_deactivate_the_owner(self, client, user_with_role, test_user, db_session):
        viewer = await user_with_role("viewer")
        assert await _deactivate(client, viewer, test_user.id) == 403
        await db_session.refresh(test_user)
        assert test_user.is_active

    async def test_an_admin_cannot_deactivate_the_owner(self, client, user_with_role, test_user, db_session):
        admin = await user_with_role("admin")
        assert await _deactivate(client, admin, test_user.id) == 403
        await db_session.refresh(test_user)
        assert test_user.is_active

    async def test_an_admin_can_deactivate_a_developer(self, client, user_with_role, db_session):
        admin = await user_with_role("admin")
        developer_id = await _me(client, await user_with_role("developer"))
        assert await _deactivate(client, admin, developer_id) == 200
        developer = (await db_session.execute(select(User).where(User.email == "developer@example.com"))).scalar_one()
        await db_session.refresh(developer)
        assert not developer.is_active

    async def test_nobody_deactivates_themselves(self, client, auth_headers, test_user):
        assert await _deactivate(client, auth_headers, test_user.id) == 403


class TestRemoval:
    async def test_an_admin_cannot_remove_the_owner(self, client, user_with_role, test_user, test_org, db_session):
        admin = await user_with_role("admin")
        response = await client.delete(f"/api/v1/organizations/{test_org.id}/members/{test_user.id}", headers=admin)
        assert response.status_code == 403
        await db_session.refresh(test_user)
        assert test_user.organization_id == test_org.id

    async def test_removing_a_member_revokes_their_access(
        self, client, auth_headers, user_with_role, test_org, test_project, db_session
    ):
        developer = await user_with_role("developer")
        developer_id = await _me(client, developer)
        tasks = f"/api/v1/projects/{test_project.id}/tasks"
        assert (await client.post(tasks, json={"title": "Before removal"}, headers=developer)).status_code == 201

        response = await client.delete(f"/api/v1/organizations/{test_org.id}/members/{developer_id}", headers=auth_headers)
        assert response.status_code == 200

        remaining = await db_session.execute(select(UserRole).where(UserRole.organization_id == test_org.id))
        assert developer_id not in {str(r.user_id) for r in remaining.scalars().all()}
        removed = (await db_session.execute(select(User).where(User.email == "developer@example.com"))).scalar_one()
        await db_session.refresh(removed)
        assert not removed.is_active
        # Their token has not expired, but they can no longer change anything.
        assert (await client.post(tasks, json={"title": "After removal"}, headers=developer)).status_code == 403

    async def test_removing_someone_who_is_not_a_member_is_a_404(self, client, auth_headers, test_org):
        from uuid import uuid4

        response = await client.delete(f"/api/v1/organizations/{test_org.id}/members/{uuid4()}", headers=auth_headers)
        assert response.status_code == 404
