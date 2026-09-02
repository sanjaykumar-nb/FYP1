from app.agents.base import BaseAgent
from app.models.agent_base import RiskInput, RiskOutput
from app.llm.client import GroqClient
from app.llm.fallback import RuleBasedFallback
from app.prompts.risk import RISK_PROMPT


class RiskPredictionAgent(BaseAgent[RiskInput, RiskOutput]):
    def __init__(self, llm_client: GroqClient, fallback: RuleBasedFallback):
        super().__init__("risk_prediction")
        self.llm = llm_client
        self.fallback = fallback
    
    def get_system_prompt(self) -> str:
        return RISK_PROMPT
    
    async def run(self, input_data: RiskInput) -> RiskOutput:
        context = {
            "project_id": str(input_data.project_id),
            "specialist_outputs": input_data.specialist_outputs,
        }
        
        try:
            response = await self.llm.generate_structured(
                system_prompt=self.get_system_prompt(),
                user_prompt=f"Predict risks from specialist analyses: {context}",
                output_schema=RiskOutput.model_json_schema(),
            )
            return RiskOutput(**response)
        except Exception as e:
            return self.fallback.risk_prediction(input_data)