from ai_service.app.agents.base import BaseAgent
from ai_service.app.models.agent_base import RecommendationInput, RecommendationOutput
from ai_service.app.llm.client import GroqClient
from ai_service.app.llm.fallback import RuleBasedFallback
from ai_service.app.prompts.recommendation import RECOMMENDATION_PROMPT


class RecommendationAgent(BaseAgent[RecommendationInput, RecommendationOutput]):
    def __init__(self, llm_client: GroqClient, fallback: RuleBasedFallback):
        super().__init__("recommendation")
        self.llm = llm_client
        self.fallback = fallback
    
    def get_system_prompt(self) -> str:
        return RECOMMENDATION_PROMPT
    
    async def run(self, input_data: RecommendationInput) -> RecommendationOutput:
        context = {
            "project_id": str(input_data.project_id),
            "risk_scores": input_data.risk_scores,
            "specialist_outputs": input_data.specialist_outputs,
        }
        
        try:
            response = await self.llm.generate_structured(
                system_prompt=self.get_system_prompt(),
                user_prompt=f"Generate recommendations from risk analysis: {context}",
                output_schema=RecommendationOutput.model_json_schema(),
            )
            return RecommendationOutput(**response)
        except Exception as e:
            return self.fallback.recommendation_generation(input_data)