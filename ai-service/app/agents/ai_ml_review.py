from app.agents.base import BaseAgent
from app.models.agent_base import AgentOutput
from app.llm.client import GroqClient
from app.llm.fallback import RuleBasedFallback
from app.prompts.review_trio import AIML_REVIEW_PROMPT


class AIMLAgent(BaseAgent[dict, AgentOutput]):
    def __init__(self, llm_client: GroqClient, fallback: RuleBasedFallback):
        super().__init__("ai_ml_review")
        self.llm = llm_client
        self.fallback = fallback
    
    def get_system_prompt(self) -> str:
        return AIML_REVIEW_PROMPT
    
    async def run(self, input_data: dict) -> AgentOutput:
        context = {
            "proposal": input_data.get("proposal", {}),
            "project_id": input_data.get("project_id"),
        }
        
        try:
            response = await self.llm.generate_structured(
                system_prompt=self.get_system_prompt(),
                user_prompt=f"Review this proposal from an AI/ML perspective: {context}",
                output_schema=AgentOutput.model_json_schema(),
            )
            return AgentOutput(**response)
        except Exception as e:
            return self.fallback.ai_ml_review(input_data)