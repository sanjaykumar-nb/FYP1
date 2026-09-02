import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.mvp

class TestHealth:
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data


class TestRoot:
    async def test_root_endpoint(self, client: AsyncClient):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "docs" in data
        assert "health" in data