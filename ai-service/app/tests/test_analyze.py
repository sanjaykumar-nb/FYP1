import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.main import app
from app.config import get_settings
from app.models.agent_base import (
    AgentOutput, AgentSignal, AgentEvidence, AgentRecommendation,
    CoordinatorInput, CoordinatorOutput, AnalyzeRequest, AnalyzeResponse,
    PlanningInput, PlanningOutput, ProgressInput, ProgressOutput,
    RiskInput, RiskOutput, RecommendationInput, RecommendationOutput,
)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_groq_client():
    with patch("app.llm.client.GroqClient") as mock:
        client_instance = AsyncMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def mock_fallback():
    with patch("app.llm.fallback.RuleBasedFallback") as mock:
        fallback_instance = MagicMock()
        mock.return_value = fallback_instance
        yield fallback_instance


@pytest.mark.mvp
class TestHealth:
    async def test_liveness_check(self, client: AsyncClient):
        """Plain /health is a liveness probe — it must stay cheap and static."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data

    async def test_api_health_lists_agents(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "agents" in data
        assert len(data["agents"]) == 10


@pytest.mark.mvp
class TestAnalyze:
    async def test_analyze_project_success(self, client: AsyncClient, mock_groq_client, mock_fallback):
        project_id = str(uuid4())

        # Mock the coordinator agent run
        mock_output = CoordinatorOutput(
            project_id=uuid4(),
            overall_summary="Analysis complete",
            overall_risk_level="low",
            overall_confidence=0.8,
            specialist_outputs={},
            merged_recommendations=[],
            next_actions=["Review recommendations"],
        )

        with patch("app.api.v1.analyze.run_full_analysis", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_output.model_dump()

            response = await client.post(
                "/api/v1/analyze",
                json={
                    "project_id": project_id,
                    "scope": ["planning", "progress"],
                    "trigger_type": "manual",
                },
            )
            assert response.status_code == 200
            data = response.json()
            # The MVP runs analysis synchronously (no Celery — see plan Part
            # B3) and returns the full result in the same response.
            assert data["status"] == "completed"
            assert "message" in data
            assert data["result"]["overall_summary"] == "Analysis complete"

    async def test_analyze_invalid_project_id(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/analyze",
            json={"project_id": "not-a-uuid", "scope": ["planning"]},
        )
        assert response.status_code == 422


@pytest.mark.mvp
class TestSingleAgent:
    async def test_run_planning_agent(self, client: AsyncClient, mock_groq_client, mock_fallback):
        project_id = str(uuid4())

        mock_output = PlanningOutput(
            summary="Planning analysis complete",
            risk_level="low",
            confidence=0.7,
            signals=[],
            evidence=[],
            recommendations=[],
            next_action="Review sprint planning",
            sprint_readiness=0.8,
            milestone_feasibility={},
            capacity_gaps=[],
        )

        with patch("app.api.v1.analyze.run_single_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_output.model_dump()

            response = await client.post(
                f"/api/v1/agents/planning",
                json={"project_id": project_id, "input": {}},
            )
            assert response.status_code == 200
            data = response.json()
            assert "sprint_readiness" in data

    async def test_run_unknown_agent(self, client: AsyncClient):
        project_id = str(uuid4())
        response = await client.post(
            "/api/v1/agents/unknown_agent",
            json={"project_id": project_id, "input": {}},
        )
        assert response.status_code == 404


@pytest.mark.deferred  # Review Trio: off the critical path of the MVP thesis
class TestReviewTrio:
    async def test_run_review(self, client: AsyncClient, mock_groq_client, mock_fallback):
        project_id = str(uuid4())
        user_id = str(uuid4())

        with patch("app.api.v1.analyze.run_review_trio", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "consensus": "approve",
                "confidence": 0.8,
                "individual_reviews": [],
                "conflicts_resolved": [],
                "final_recommendation": "Approved",
                "required_changes": [],
            }

            response = await client.post(
                "/api/v1/review",
                json={
                    "project_id": project_id,
                    "proposal": {"title": "New Feature", "description": "Add feature X"},
                    "requested_by": user_id,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["consensus"] == "approve"