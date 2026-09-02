import pytest
from httpx import AsyncClient
from uuid import uuid4


pytestmark = pytest.mark.mvp

class TestProjects:
    async def test_create_project(self, client: AsyncClient, auth_headers, test_org):
        response = await client.post(
            "/api/v1/projects",
            json={
                "name": "New Project",
                "description": "Project description",
                "key": "NEW",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Project"
        assert data["key"] == "NEW"
        assert "id" in data

    async def test_list_projects(self, client: AsyncClient, auth_headers, test_project):
        response = await client.get("/api/v1/projects", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1
        assert data["items"][0]["name"] == "Test Project"

    async def test_get_project(self, client: AsyncClient, auth_headers, test_project):
        response = await client.get(f"/api/v1/projects/{test_project.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_project.id)
        assert data["name"] == "Test Project"

    async def test_update_project(self, client: AsyncClient, auth_headers, test_project):
        response = await client.patch(
            f"/api/v1/projects/{test_project.id}",
            json={"name": "Updated Project", "description": "Updated description"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Project"

    async def test_delete_project(self, client: AsyncClient, auth_headers, test_project):
        response = await client.delete(f"/api/v1/projects/{test_project.id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deleted
        response = await client.get(f"/api/v1/projects/{test_project.id}", headers=auth_headers)
        assert response.status_code == 404

    async def test_create_project_invalid_key(self, client: AsyncClient, auth_headers):
        response = await client.post(
            "/api/v1/projects",
            json={"name": "Project", "key": "INVALIDKEYTOOLONG"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_unauthorized_project_access(self, client: AsyncClient, test_project):
        response = await client.get(f"/api/v1/projects/{test_project.id}")
        assert response.status_code == 401