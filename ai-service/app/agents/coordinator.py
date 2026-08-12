from typing import Optional
from ai_service.app.agents.base import BaseAgent
from ai_service.app.models.agent_base import CoordinatorInput, CoordinatorOutput, AgentOutput
from ai_service.app.llm.client import GroqClient
from ai_service.app.llm.fallback import RuleBasedFallback
from ai_service.app.prompts.coordinator import COORDINATOR_PROMPT
from ai_service.app.agents.planning import PlanningAgent
from ai_service.app.agents.progress import ProgressAgent
from ai_service.app.agents.meeting_intel import MeetingIntelligenceAgent
from ai_service.app.agents.comm_intel import CommunicationIntelligenceAgent
from ai_service.app.agents.workload_intel import WorkloadIntelligenceAgent
from ai_service.app.agents.risk import RiskPredictionAgent
from ai_service.app.agents.recommendation import RecommendationAgent
from ai_service.app.agents.frontend_review import FrontendAgent
from ai_service.app.agents.backend_review import BackendAgent
from ai_service.app.agents.ai_ml_review import AIMLAgent


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
        scope = input_data.scope or ["planning", "progress", "meetings", "communication", "workload"]
        run_review = "review" in scope
        
        specialist_outputs = {}
        
        import asyncio
        
        tasks = []
        if "planning" in scope:
            tasks.append(("planning", self.planning_agent.run(input_data)))
        if "progress" in scope:
            tasks.append(("progress", self.progress_agent.run(input_data)))
        if "meetings" in scope:
            tasks.append(("meetings", self.meeting_intel_agent.run(input_data)))
        if "communication" in scope:
            tasks.append(("communication", self.comm_intel_agent.run(input_data)))
        if "workload" in scope:
            tasks.append(("workload", self.workload_intel_agent.run(input_data)))
        
        if tasks:
            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
            for (name, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    specialist_outputs[name] = self._create_error_output(name, str(result))
                else:
                    specialist_outputs[name] = result
        
        # Run risk prediction
        from ai_service.app.models.agent_base import RiskInput
        risk_input = RiskInput(
            project_id=input_data.project_id,
            specialist_outputs={k: v.model_dump() if hasattr(v, 'model_dump') else v for k, v in specialist_outputs.items()}
        )
        risk_output = await self.risk_agent.run(risk_input)
        specialist_outputs["risk"] = risk_output
        
        # Run recommendation
        from ai_service.app.models.agent_base import RecommendationInput
        rec_input = RecommendationInput(
            project_id=input_data.project_id,
            risk_scores=risk_output.risk_scores if hasattr(risk_output, 'risk_scores') else {},
            specialist_outputs={k: v.model_dump() if hasattr(v, 'model_dump') else v for k, v in specialist_outputs.items()}
        )
        rec_output = await self.recommendation_agent.run(rec_input)
        specialist_outputs["recommendation"] = rec_output
        
        # Run review trio if requested
        if run_review and input_data.context.get("proposal"):
            proposal = input_data.context["proposal"]
            review_input = {"proposal": proposal, "project_id": str(input_data.project_id)}
            
            review_tasks = [
                ("frontend", self.frontend_agent.run(review_input)),
                ("backend", self.backend_agent.run(review_input)),
                ("ai_ml", self.ai_ml_agent.run(review_input)),
            ]
            review_results_raw = await asyncio.gather(*[t[1] for t in review_tasks], return_exceptions=True)
            for (name, _), result in zip(review_tasks, review_results_raw):
                if isinstance(result, Exception):
                    specialist_outputs[f"review_{name}"] = self._create_error_output(name, str(result))
                else:
                    specialist_outputs[f"review_{name}"] = result
        
        # Merge recommendations
        merged_recs = []
        if hasattr(rec_output, 'recommendations'):
            merged_recs = rec_output.recommendations
        
        # Determine overall risk level
        risk_levels = [o.risk_level for o in specialist_outputs.values() if hasattr(o, 'risk_level')]
        overall_risk = self._calculate_overall_risk(risk_levels)
        
        # Calculate overall confidence
        confidences = [o.confidence for o in specialist_outputs.values() if hasattr(o, 'confidence')]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        return CoordinatorOutput(
            project_id=input_data.project_id,
            overall_summary=f"Analysis complete for project {input_data.project_id}. Overall risk: {overall_risk}.",
            overall_risk_level=overall_risk,
            overall_confidence=overall_confidence,
            specialist_outputs={k: v.model_dump() if hasattr(v, 'model_dump') else v for k, v in specialist_outputs.items()},
            merged_recommendations=merged_recs,
            next_actions=["Review recommendations", "Assign owners", "Set deadlines"],
        )
    
    def _create_error_output(self, agent_name: str, error: str) -> AgentOutput:
        return AgentOutput(
            summary=f"{agent_name} agent failed: {error}",
            risk_level="low",
            confidence=0.0,
            signals=[],
            evidence=[],
            recommendations=[],
            next_action="Investigate agent failure",
            metadata={"error": error, "agent": agent_name}
        )
    
    def _calculate_overall_risk(self, risk_levels: list[str]) -> str:
        if not risk_levels:
            return "low"
        
        risk_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        max_risk = max(risk_levels, key=lambda x: risk_order.get(x, 0))
        return max_risk