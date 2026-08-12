from ai_service.app.agents.base import BaseAgent
from ai_service.app.models.agent_base import CommIntelInput, CommIntelOutput
from ai_service.app.llm.client import GroqClient
from ai_service.app.llm.fallback import RuleBasedFallback
from ai_service.app.prompts.comm_intel import COMM_INTEL_PROMPT


class CommunicationIntelligenceAgent(BaseAgent[CommIntelInput, CommIntelOutput]):
    def __init__(self, llm_client: GroqClient, fallback: RuleBasedFallback):
        super().__init__("communication_intelligence")
        self.llm = llm_client
        self.fallback = fallback
    
    def get_system_prompt(self) -> str:
        return COMM_INTEL_PROMPT
    
    async def run(self, input_data: CommIntelInput) -> CommIntelOutput:
        context = {
            "project_id": str(input_data.project_id),
            "events": input_data.events,
            "timeframe_days": input_data.timeframe_days,
        }
        
        try:
            response = await self.llm.generate_structured(
                system_prompt=self.get_system_prompt(),
                user_prompt=f"Analyze team communication patterns: {context}",
                output_schema=CommIntelOutput.model_json_schema(),
            )
            return CommIntelOutput(**response)
        except Exception as e:
            return self.fallback.comm_intel_analysis(input_data)