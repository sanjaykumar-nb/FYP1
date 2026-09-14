import asyncio

from app.agents.base import BaseAgent
from app.models.agent_base import AgentOutput, CoordinatorInput, CoordinatorOutput
from app.llm.client import GroqClient
from app.llm.fallback import RuleBasedFallback
from app.prompts.coordinator import COORDINATOR_PROMPT
from app.agents.planning import PlanningAgent
from app.agents.progress import ProgressAgent
from app.agents.meeting_intel import MeetingIntelligenceAgent
from app.agents.comm_intel import CommunicationIntelligenceAgent
from app.agents.workload_intel import WorkloadIntelligenceAgent
from app.agents.risk import RiskPredictionAgent
from app.agents.recommendation import RecommendationAgent
from app.agents.frontend_review import FrontendAgent
from app.agents.backend_review import BackendAgent
from app.agents.ai_ml_review import AIMLAgent
from app.graph import ProjectSnapshot, max_level
from app.services.graph_pipeline import (
    build_graph,
    build_planning_input,
    build_progress_input,
    build_workload_input,
    recommendation_output_from_graph,
    risk_output_from_graph,
)

# Meeting Intelligence and Communication Intelligence are deferred: they need
# a transcript / comm-event data source that does not exist in the product
# yet (see plan Part B3), so they never receive a wrong-shaped input — they
# are just skipped with an explicit "no data source" output.
_GRAPH_BACKED_SPECIALISTS = ("planning", "progress", "workload")
_DEFERRED_SPECIALISTS = ("meetings", "communication")

DEFAULT_SCOPE = list(_GRAPH_BACKED_SPECIALISTS)


class CoordinatorAgent(BaseAgent[CoordinatorInput, CoordinatorOutput]):
    def __init__(
        self,
        llm_client: GroqClient,
        fallback: RuleBasedFallback,
        planning_agent: PlanningAgent,
        progress_agent: ProgressAgent,
        meeting_intel_agent: MeetingIntelligenceAgent,
        comm_intel_agent: CommunicationIntelligenceAgent,
        workload_intel_agent: WorkloadIntelligenceAgent,
        risk_agent: RiskPredictionAgent,
        recommendation_agent: RecommendationAgent,
        frontend_agent: FrontendAgent,
        backend_agent: BackendAgent,
        ai_ml_agent: AIMLAgent,
    ):
        super().__init__("coordinator")
        self.llm = llm_client
        self.fallback = fallback

        self.planning_agent = planning_agent
        self.progress_agent = progress_agent
        self.meeting_intel_agent = meeting_intel_agent
        self.comm_intel_agent = comm_intel_agent
        self.workload_intel_agent = workload_intel_agent
        self.risk_agent = risk_agent
        self.recommendation_agent = recommendation_agent

        self.frontend_agent = frontend_agent
        self.backend_agent = backend_agent
        self.ai_ml_agent = ai_ml_agent

    def get_system_prompt(self) -> str:
        return COORDINATOR_PROMPT

    async def run(self, input_data: CoordinatorInput) -> CoordinatorOutput:
        scope = input_data.scope or DEFAULT_SCOPE
        run_review = "review" in scope

        snapshot = self._load_snapshot(input_data)
        graph, analysis = build_graph(snapshot)

        specialist_outputs: dict[str, AgentOutput] = {}

        tasks: list[tuple[str, "asyncio.Future"]] = []
        if "planning" in scope:
            planning_input = build_planning_input(input_data.project_id, snapshot, graph, analysis)
            tasks.append(("planning", self.planning_agent.run(planning_input)))
        if "progress" in scope:
            progress_input = build_progress_input(input_data.project_id, snapshot, graph, analysis)
            tasks.append(("progress", self.progress_agent.run(progress_input)))
        if "workload" in scope:
            workload_input = build_workload_input(input_data.project_id, snapshot, graph, analysis)
            tasks.append(("workload", self.workload_intel_agent.run(workload_input)))

        if tasks:
            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
            for (name, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    specialist_outputs[name] = self._create_error_output(name, str(result))
                else:
                    specialist_outputs[name] = result

        for name in _DEFERRED_SPECIALISTS:
            if name in scope:
                specialist_outputs[name] = self._create_deferred_output(name)

        # Risk scores are always graph-computed (deterministic, zero tokens) —
        # never guessed from the specialists' prose. See app.graph.metrics.
        risk_output = risk_output_from_graph(analysis)
        specialist_outputs["risk"] = risk_output

        rec_output = recommendation_output_from_graph(analysis, graph)
        specialist_outputs["recommendation"] = rec_output

        if run_review and input_data.context.get("proposal"):
            proposal = input_data.context["proposal"]
            review_input = {"proposal": proposal, "project_id": str(input_data.project_id)}

            review_tasks = [
                ("review_frontend", self.frontend_agent.run(review_input)),
                ("review_backend", self.backend_agent.run(review_input)),
                ("review_ai_ml", self.ai_ml_agent.run(review_input)),
            ]
            review_results = await asyncio.gather(*[t[1] for t in review_tasks], return_exceptions=True)
            for (name, _), result in zip(review_tasks, review_results):
                if isinstance(result, Exception):
                    specialist_outputs[name] = self._create_error_output(name, str(result))
                else:
                    specialist_outputs[name] = result

        confidences = [o.confidence for o in specialist_outputs.values() if hasattr(o, "confidence")]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        return CoordinatorOutput(
            project_id=input_data.project_id,
            overall_summary=(
                f"Analysis complete for project {input_data.project_id}. "
                f"Overall risk: {analysis.overall_risk_level}. "
                f"{len(analysis.findings)} graph finding(s)."
            ),
            overall_risk_level=analysis.overall_risk_level,
            overall_confidence=overall_confidence,
            specialist_outputs={
                k: v.model_dump() if hasattr(v, "model_dump") else v
                for k, v in specialist_outputs.items()
            },
            merged_recommendations=rec_output.recommendations,
            next_actions=["Review recommendations", "Assign owners", "Set deadlines"],
        )

    @staticmethod
    def _load_snapshot(input_data: CoordinatorInput) -> ProjectSnapshot:
        raw = input_data.context.get("snapshot") if input_data.context else None
        if raw:
            return ProjectSnapshot.model_validate(raw)
        # No snapshot supplied — an empty graph yields "low" risk everywhere
        # with zero findings rather than crashing (see test_graph.py::
        # test_empty_snapshot_builds), which is the honest answer to "we were
        # given nothing to analyze".
        return ProjectSnapshot(project_id=input_data.project_id)

    def _create_error_output(self, agent_name: str, error: str) -> AgentOutput:
        return AgentOutput(
            summary=f"{agent_name} agent failed: {error}",
            risk_level="low",
            confidence=0.0,
            signals=[],
            evidence=[],
            recommendations=[],
            next_action="Investigate agent failure",
            metadata={"error": error, "agent": agent_name},
        )

    def _create_deferred_output(self, agent_name: str) -> AgentOutput:
        return AgentOutput(
            summary=f"{agent_name} is not available: no data source is connected yet",
            risk_level="low",
            confidence=0.0,
            signals=[],
            evidence=[],
            recommendations=[],
            next_action="Not applicable",
            metadata={"deferred": True, "agent": agent_name},
        )

    def _calculate_overall_risk(self, risk_levels: list[str]) -> str:
        return max_level(risk_levels)
