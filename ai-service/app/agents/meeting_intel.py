from app.agents.base import BaseAgent
from app.models.agent_base import MeetingIntelInput, MeetingIntelOutput
from app.llm.client import GroqClient
from app.llm.fallback import RuleBasedFallback
from app.prompts.meeting_intel import MEETING_INTEL_PROMPT


class MeetingIntelligenceAgent(BaseAgent[MeetingIntelInput, MeetingIntelOutput]):
    def __init__(self, llm_client: GroqClient, fallback: RuleBasedFallback):
        super().__init__("meeting_intelligence")
        self.llm = llm_client
        self.fallback = fallback
    
    def get_system_prompt(self) -> str:
        return MEETING_INTEL_PROMPT
    
    async def run(self, input_data: MeetingIntelInput) -> MeetingIntelOutput:
        context = {
            "meeting_id": str(input_data.meeting_id),
            "transcript": input_data.transcript,
            "participants": input_data.participants,
        }
        
        try:
            response = await self.llm.generate_structured(
                system_prompt=self.get_system_prompt(),
                user_prompt=f"Extract insights from this meeting: {context}",
                output_schema=MeetingIntelOutput.model_json_schema(),
            )
            return MeetingIntelOutput(**response)
        except Exception as e:
            return self.fallback.meeting_intel_analysis(input_data)