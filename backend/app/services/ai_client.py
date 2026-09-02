import httpx
from typing import Optional
from uuid import UUID
from app.config import get_settings
from app.core.exceptions import AIServiceError

settings = get_settings()


class AIClient:
    def __init__(self):
        self.base_url = settings.AI_SERVICE_URL
        self.timeout = 60.0
    
    async def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    json=data,
                )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                raise AIServiceError("AI service timeout")
            except httpx.HTTPStatusError as e:
                raise AIServiceError(f"AI service error: {e.response.text}")
            except Exception as e:
                raise AIServiceError(f"AI service connection failed: {str(e)}")
    
    async def analyze_project(
        self,
        project_id: UUID,
        scope: list[str] = None,
        trigger_type: str = "manual",
        snapshot: dict = None,
    ) -> dict:
        """Runs synchronously and returns the full result (no Celery in the
        MVP — see plan Part B3). ``snapshot`` is the project-state payload
        from app.services.snapshot_builder.build_project_snapshot; the AI
        service is stateless and never queries Postgres itself."""
        return await self._request("POST", "/api/v1/analyze", {
            "project_id": str(project_id),
            "scope": scope or ["planning", "progress", "workload"],
            "trigger_type": trigger_type,
            "snapshot": snapshot,
        })
    
    async def run_agent(
        self,
        agent_name: str,
        project_id: UUID,
        input_data: dict,
    ) -> dict:
        return await self._request("POST", f"/api/v1/agents/{agent_name}", {
            "project_id": str(project_id),
            "input": input_data,
        })
    
    async def run_review_trio(
        self,
        project_id: UUID,
        proposal: dict,
        requested_by: UUID,
    ) -> dict:
        return await self._request("POST", "/api/v1/review", {
            "project_id": str(project_id),
            "proposal": proposal,
            "requested_by": str(requested_by),
        })
    
    async def health_check(self) -> dict:
        return await self._request("GET", "/health")


# Singleton instance
ai_client = AIClient()