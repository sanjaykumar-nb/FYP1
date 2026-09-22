"""End-to-end coordinator pipeline tests (E2E-1..3, INPUT-1, REL-1, REL-3).

These exercise app.agents.coordinator.CoordinatorAgent directly rather than
through HTTP, since that's where the graph-grounded pipeline actually lives.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.ai_ml_review import AIMLAgent
from app.agents.backend_review import BackendAgent
from app.agents.comm_intel import CommunicationIntelligenceAgent
from app.agents.coordinator import CoordinatorAgent
from app.agents.frontend_review import FrontendAgent
from app.agents.meeting_intel import MeetingIntelligenceAgent
from app.agents.planning import PlanningAgent
from app.agents.progress import ProgressAgent
from app.agents.recommendation import RecommendationAgent
from app.agents.risk import RiskPredictionAgent
from app.agents.workload_intel import WorkloadIntelligenceAgent
from app.llm.client import GroqClient
from app.llm.fallback import RuleBasedFallback
from app.models.agent_base import CoordinatorInput
from app.tests.factories import healthy_project, uid

pytestmark = pytest.mark.mvp


@pytest.fixture
def coordinator():
    llm = GroqClient()
    fallback = RuleBasedFallback()
    return CoordinatorAgent(
        llm_client=llm,
        fallback=fallback,
        planning_agent=PlanningAgent(llm, fallback),
        progress_agent=ProgressAgent(llm, fallback),
        meeting_intel_agent=MeetingIntelligenceAgent(llm, fallback),
        comm_intel_agent=CommunicationIntelligenceAgent(llm, fallback),
        workload_intel_agent=WorkloadIntelligenceAgent(llm, fallback),
        risk_agent=RiskPredictionAgent(llm, fallback),
        recommendation_agent=RecommendationAgent(llm, fallback),
        frontend_agent=FrontendAgent(llm, fallback),
        backend_agent=BackendAgent(llm, fallback),
        ai_ml_agent=AIMLAgent(llm, fallback),
    )


def _coordinator_input(snapshot_dict: dict | None = None, scope=None) -> CoordinatorInput:
    return CoordinatorInput(
        project_id=uid("project"),
        organization_id=uid("org"),
        trigger_type="manual",
        scope=scope or ["planning", "progress", "workload"],
        context={"snapshot": snapshot_dict} if snapshot_dict else {},
    )


class TestFallbackOnlyRun:
    """E2E-1: the pipeline must never surface an internal crash as success."""

    async def test_no_specialist_reports_agent_failed(self, coordinator):
        """Simulates GROQ_API_KEY unset: the LLM call always fails, so every
        specialist must land on its rule-based fallback, never an error stub."""
        snapshot = healthy_project(12).model_dump()

        with patch.object(GroqClient, "generate_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("no GROQ_API_KEY configured")
            result = await coordinator.run(_coordinator_input(snapshot))

        for name, output in result.specialist_outputs.items():
            assert "agent failed" not in output["summary"].lower(), (
                f"{name} produced an internal-error stub instead of falling back: {output}"
            )
            assert output["confidence"] > 0, f"{name} has zero confidence: {output}"

        assert result.overall_risk_level in ("low", "medium", "high", "critical")

    async def test_empty_project_is_low_risk_not_a_crash(self, coordinator):
        with patch.object(GroqClient, "generate_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("no key")
            result = await coordinator.run(_coordinator_input(snapshot_dict=None))

        assert result.overall_risk_level == "low"
        assert result.specialist_outputs["risk"]["risk_level"] == "low"


class TestLLMPath:
    """E2E-2: when the LLM succeeds, its (schema-valid) output is used."""

    async def test_successful_llm_response_is_used(self, coordinator):
        snapshot = healthy_project(6).model_dump()

        llm_response = {
            "summary": "LLM-authored planning summary",
            "risk_level": "medium",
            "confidence": 0.85,
            "signals": [],
            "evidence": [],
            "recommendations": [],
            "next_action": "Review with the team",
            "sprint_readiness": 0.7,
            "milestone_feasibility": {},
            "capacity_gaps": [],
        }

        with patch.object(GroqClient, "generate_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_response
            result = await coordinator.run(_coordinator_input(snapshot))

        assert result.specialist_outputs["planning"]["summary"] == "LLM-authored planning summary"
        assert result.specialist_outputs["planning"]["confidence"] == 0.85


class TestPartialFailure:
    """E2E-3: the LLM raising on some calls must not take down the whole run."""

    async def test_intermittent_llm_failure_still_yields_a_full_run(self, coordinator):
        snapshot = healthy_project(10).model_dump()
        calls = {"n": 0}

        async def flaky(*args, **kwargs):
            calls["n"] += 1
            raise TimeoutError("simulated network flake")

        with patch.object(GroqClient, "generate_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = flaky
            result = await coordinator.run(_coordinator_input(snapshot))

        assert calls["n"] >= 3  # planning, progress, workload each tried the LLM
        assert set(result.specialist_outputs.keys()) >= {"planning", "progress", "workload", "risk", "recommendation"}
        for name in ("planning", "progress", "workload"):
            assert "agent failed" not in result.specialist_outputs[name]["summary"].lower()


class TestInputTyping:
    """INPUT-1: each specialist must receive its own typed input, not the raw
    CoordinatorInput — guards the original AttributeError crash (C2.1)."""

    async def test_planning_progress_workload_receive_distinct_typed_inputs(self, coordinator):
        from app.models.agent_base import PlanningInput, ProgressInput, WorkloadIntelInput

        snapshot = healthy_project(8).model_dump()
        received = {}

        def make_spy(name, real_run):
            async def spy(self, input_data):
                received[name] = input_data
                return await real_run(self, input_data)
            return spy

        with patch.object(PlanningAgent, "run", make_spy("planning", PlanningAgent.run)), \
             patch.object(ProgressAgent, "run", make_spy("progress", ProgressAgent.run)), \
             patch.object(WorkloadIntelligenceAgent, "run", make_spy("workload", WorkloadIntelligenceAgent.run)), \
             patch.object(GroqClient, "generate_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("no key — fall back")
            await coordinator.run(_coordinator_input(snapshot))

        assert isinstance(received["planning"], PlanningInput)
        assert isinstance(received["progress"], ProgressInput)
        assert isinstance(received["workload"], WorkloadIntelInput)
        # Each specialist's input carries only what it needs — not a dump of
        # the entire CoordinatorInput.
        assert hasattr(received["planning"], "milestones")
        assert not hasattr(received["planning"], "velocity_history")


class TestEvidenceGrounding:
    """REL-1: a fabricated evidence reference must never survive to the caller."""

    async def test_fabricated_reference_id_is_stripped(self, coordinator):
        snapshot = healthy_project(6).model_dump()

        llm_response = {
            "summary": "Planning looks fine",
            "risk_level": "low",
            "confidence": 0.8,
            "signals": [],
            "evidence": [
                {"source": "graph", "reference_id": "task:not-a-real-node", "excerpt": "made up", "relevance": 0.9},
            ],
            "recommendations": [],
            "next_action": "None",
            "sprint_readiness": 0.9,
            "milestone_feasibility": {},
            "capacity_gaps": [],
        }

        with patch.object(GroqClient, "generate_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_response
            result = await coordinator.run(_coordinator_input(snapshot))

        assert result.specialist_outputs["planning"]["evidence"] == []


class TestRawResponseValidation:
    """REL-3: a malformed LLM response is caught before it reaches a Pydantic
    model, not after — see GroqClient.generate_structured's raw-response
    validation via app.llm.structured.validate_against_schema."""

    async def test_missing_required_field_falls_back_cleanly(self, coordinator):
        snapshot = healthy_project(6).model_dump()

        # "risk_level" is required by PlanningOutput's schema but absent here.
        malformed = {
            "summary": "incomplete",
            "confidence": 0.5,
            "next_action": "none",
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.raise_for_status = lambda: None
            mock_post.return_value.json = lambda: {
                "choices": [{"message": {"content": __import__("json").dumps(malformed)}}]
            }
            result = await coordinator.run(_coordinator_input(snapshot))

        # Falls back to the deterministic rule-based path rather than
        # propagating a half-built AgentOutput.
        assert "agent failed" not in result.specialist_outputs["planning"]["summary"].lower()
        assert result.specialist_outputs["planning"]["confidence"] > 0


class TestTeamCapacity:
    """Where the planning agent's capacity comes from (graph_pipeline.team_capacity)."""

    def test_the_teams_own_figure_wins(self):
        from app.services.graph_pipeline import team_capacity

        snapshot = healthy_project(4).model_copy(update={"team_capacity_points": 30, "velocity_history": [10.0, 12.0]})
        assert team_capacity(snapshot) == {"total_points": 30, "source": "set by the team"}

    def test_otherwise_the_average_of_the_last_three_sprints(self):
        from app.services.graph_pipeline import team_capacity

        snapshot = healthy_project(4).model_copy(update={"velocity_history": [50.0, 10.0, 20.0, 30.0]})
        assert team_capacity(snapshot) == {"total_points": 20.0, "source": "average completed in the last 3 sprints"}

    def test_unknown_without_a_finished_sprint(self):
        from app.services.graph_pipeline import team_capacity

        assert team_capacity(healthy_project(4)) == {}
        assert team_capacity(healthy_project(4).model_copy(update={"velocity_history": [0.0, 0.0]})) == {}
