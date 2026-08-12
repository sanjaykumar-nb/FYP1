from typing import Optional
from ai_service.app.agents.base import BaseAgent
from ai_service.app.models.agent_base import PlanningInput, PlanningOutput, AgentSignal, AgentEvidence, AgentRecommendation
from ai_service.app.llm.client import GroqClient
from ai_service.app.llm.fallback import RuleBasedFallback
from ai_service.app.prompts.planning import PLANNING_PROMPT


class PlanningAgent(BaseAgent[PlanningInput, PlanningOutput]):
    def __init__(self, llm_client: GroqClient, fallback: RuleBasedFallback):
        super().__init__("planning")
        self.llm = llm_client
        self.fallback = fallback
    
    def get_system_prompt(self) -> str:
        return PLANNING_PROMPT
    
    async def run(self, input_data: PlanningInput) -> PlanningOutput:
        # Prepare context for LLM
        context = {
            "project_id": str(input_data.project_id),
            "milestones": input_data.milestones,
            "tasks": input_data.tasks,
            "team_capacity": input_data.team_capacity,
        }
        
        try:
            # Try LLM first
            response = await self.llm.generate_structured(
                system_prompt=self.get_system_prompt(),
                user_prompt=f"Analyze this project planning data: {context}",
                output_schema=PlanningOutput.model_json_schema(),
            )
            return PlanningOutput(**response)
        except Exception as e:
            # Fallback to rule-based
            return self.fallback.planning_analysis(input_data)