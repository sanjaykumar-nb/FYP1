import pytest
from httpx import AsyncClient
from uuid import uuid4


pytestmark = pytest.mark.mvp

class TestTasks:
    async def test_create_task(self, client: AsyncClient, auth_headers, test_project):
        response = await client.post(
            f"/api/v1/projects/{test_project.id}/tasks",
            json={
                "title": "New Task",
                "description": "Task description",
                "status": "backlog",
                "priority": "high",
                "story_points": 8,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Task"
        assert data["priority"] == "high"
        assert data["story_points"] == 8

    async def test_list_tasks(self, client: AsyncClient, auth_headers, test_project, test_task):
        response = await client.get(f"/api/v1/projects/{test_project.id}/tasks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1
        assert data["items"][0]["title"] == "Test Task"

    async def test_get_task(self, client: AsyncClient, auth_headers, test_project, test_task):
        response = await client.get(f"/api/v1/projects/{test_project.id}/tasks/{test_task.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_task.id)
        assert data["title"] == "Test Task"

    async def test_update_task(self, client: AsyncClient, auth_headers, test_project, test_task):
        response = await client.patch(
            f"/api/v1/projects/{test_project.id}/tasks/{test_task.id}",
            json={"status": "in_progress", "priority": "critical"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"
        assert data["priority"] == "critical"

    async def test_move_task(self, client: AsyncClient, auth_headers, test_project, test_task):
        response = await client.patch(
            f"/api/v1/projects/{test_project.id}/tasks/{test_task.id}/move",
            json={"status": "done", "position": 0},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "done"

    async def test_delete_task(self, client: AsyncClient, auth_headers, test_project, test_task):
        response = await client.delete(f"/api/v1/projects/{test_project.id}/tasks/{test_task.id}", headers=auth_headers)
        assert response.status_code == 204

    async def test_create_task_dependency(self, client: AsyncClient, auth_headers, test_project, test_task, test_user):
        # Create another task
        response2 = await client.post(
            f"/api/v1/projects/{test_project.id}/tasks",
            json={"title": "Blocking Task", "status": "backlog", "priority": "medium"},
            headers=auth_headers,
        )
        blocking_task = response2.json()

        response = await client.post(
            f"/api/v1/projects/{test_project.id}/tasks/{test_task.id}/dependencies",
            json={"blocking_task_id": blocking_task["id"], "dependency_type": "blocks"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["blocking_task_id"] == blocking_task["id"]
        assert data["blocked_task_id"] == str(test_task.id)

    async def test_add_task_comment(self, client: AsyncClient, auth_headers, test_project, test_task):
        response = await client.post(
            f"/api/v1/projects/{test_project.id}/tasks/{test_task.id}/comments",
            json={"content": "This is a comment"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "This is a comment"

    async def test_invalid_task_status(self, client: AsyncClient, auth_headers, test_project):
        response = await client.post(
            f"/api/v1/projects/{test_project.id}/tasks",
            json={"title": "Task", "status": "invalid_status", "priority": "medium"},
            headers=auth_headers,
        )
        assert response.status_code == 422