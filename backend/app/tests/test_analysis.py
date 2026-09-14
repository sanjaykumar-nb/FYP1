"""M5: analysis persistence & readback (PERSIST-1).

POST /analyze must create a real AgentRun and persist the AI service's
result; GET /agent-runs must then return it. The AI service call itself is
mocked so these tests stay hermetic — no network, no live LLM.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.exceptions import AIServiceError

pytestmark = pytest.mark.mvp

_FAKE_AI_RESULT = {
    "agent_run_id": "00000000-0000-0000-0000-000000000000",
    "status": "completed",
    "message": "Analysis complete",
    "result": {
        "project_id": "00000000-0000-0000-0000-000000000000",
        "overall_summary": "Analysis complete for project. Overall risk: medium. 1 graph finding(s).",
        "overall_risk_level": "medium",
        "overall_confidence": 0.75,
        "specialist_outputs": {
            "planning": {
                "summary": "Planning looks reasonable",
                "risk_level": "low",
                "confidence": 0.7,
                "signals": [],
                "evidence": [],
                "recommendations": [],
                "next_action": "None",
                "metadata": {},
                "sprint_readiness": 0.8,
                "milestone_feasibility": {},
                "capacity_gaps": [],
            },
            "risk": {
                "summary": "Overall risk: medium",
                "risk_level": "medium",
                "confidence": 0.9,
                "signals": [],
                "evidence": [],
                "recommendations": [],
                "next_action": "Review risk findings",
                "metadata": {},
                "risk_scores": {"workload": "medium"},
            },
        },
        "merged_recommendations": [
            {
                "type": "redistribute",
                "title": "Redistribute workload",
                "description": "One member is overloaded",
                "reasoning": "Uneven workload increases delay risk",
                "priority": "high",
                "confidence": 0.75,
            }
        ],
        "next_actions": ["Review recommendations", "Assign owners", "Set deadlines"],
    },
}


class TestAnalysisPersistence:
    async def test_analyze_creates_a_real_agent_run(
        self, client: AsyncClient, auth_headers, test_project, test_task
    ):
        with patch(
            "app.api.v1.analytics.ai_client.analyze_project", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = _FAKE_AI_RESULT

            response = await client.post(
                f"/api/v1/analytics/projects/{test_project.id}/analyze",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # Not the old all-zero placeholder — a real generated run id.
        assert data["id"] != "00000000-0000-0000-0000-000000000000"
        assert data["coordinator_output"]["overall_risk_level"] == "medium"
        assert data["specialist_outputs"]["planning"]["sprint_readiness"] == 0.8
        assert data["final_recommendations"]["items"][0]["type"] == "redistribute"

        # The snapshot handed to the AI service must reflect real project data.
        sent_snapshot = mock_analyze.call_args.kwargs["snapshot"]
        assert sent_snapshot["project_id"] == str(test_project.id)
        assert any(t["title"] == "Test Task" for t in sent_snapshot["tasks"])

    async def test_agent_run_is_readable_after_creation(
        self, client: AsyncClient, auth_headers, test_project, test_task
    ):
        with patch(
            "app.api.v1.analytics.ai_client.analyze_project", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = _FAKE_AI_RESULT
            create_response = await client.post(
                f"/api/v1/analytics/projects/{test_project.id}/analyze",
                headers=auth_headers,
            )
        run_id = create_response.json()["id"]

        list_response = await client.get(
            f"/api/v1/analytics/projects/{test_project.id}/agent-runs",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        runs = list_response.json()
        assert any(r["id"] == run_id for r in runs)
        matched = next(r for r in runs if r["id"] == run_id)
        assert matched["status"] == "completed"
        assert matched["coordinator_output"]["overall_risk_level"] == "medium"

    async def test_analysis_updates_project_risk_and_health(
        self, client: AsyncClient, auth_headers, test_project, test_task
    ):
        with patch(
            "app.api.v1.analytics.ai_client.analyze_project", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = _FAKE_AI_RESULT
            await client.post(
                f"/api/v1/analytics/projects/{test_project.id}/analyze",
                headers=auth_headers,
            )

        project = (await client.get(f"/api/v1/projects/{test_project.id}", headers=auth_headers)).json()
        assert project["risk_score"] == 0.45
        assert project["health_score"] == 0.55

    async def test_ai_service_failure_is_persisted_not_swallowed(
        self, client: AsyncClient, auth_headers, test_project
    ):
        with patch(
            "app.api.v1.analytics.ai_client.analyze_project", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.side_effect = AIServiceError("AI service unreachable")

            response = await client.post(
                f"/api/v1/analytics/projects/{test_project.id}/analyze",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "unreachable" in data["error_message"]

        list_response = await client.get(
            f"/api/v1/analytics/projects/{test_project.id}/agent-runs",
            headers=auth_headers,
        )
        runs = list_response.json()
        assert any(r["id"] == data["id"] and r["status"] == "failed" for r in runs)

    async def test_unauthorized_cannot_trigger_analysis(self, client: AsyncClient, test_project):
        response = await client.post(f"/api/v1/analytics/projects/{test_project.id}/analyze")
        assert response.status_code == 401
