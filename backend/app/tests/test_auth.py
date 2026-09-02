import pytest
from httpx import AsyncClient
from uuid import uuid4


pytestmark = pytest.mark.mvp

class TestAuth:
    async def test_register_user(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "full_name": "New User",
                "organization_name": "New Org",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_user(self, client: AsyncClient, test_user):
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "test@example.com", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_invalid_credentials(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "test@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    async def test_refresh_token(self, client: AsyncClient, test_user):
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "test@example.com", "password": "password123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    async def test_get_current_user(self, client: AsyncClient, auth_headers):
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"

    async def test_unauthorized_access(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "full_name": "Another User",
                "organization_name": "Another Org",
            },
        )
        assert response.status_code == 409