from ai_service.app.agents.base import BaseAgent
from ai_service.app.models.agent_base import WorkloadIntelInput, WorkloadIntelOutput
from ai_service.app.llm.client import GroqClient
from ai_service.app.llm.fallback import RuleBasedFallback
from ai_service.app.prompts.workload_intel import WORKLOAD_INTEL_PROMPT


class WorkloadIntelligenceAgent(BaseAgent[WorkloadIntelInput, WorkloadIntelOutput]):
    def __init__(self, llm_client: GroqClient, fallback: RuleBasedFallback):
        super().__init__("workload_intelligence")
        self.llm = llm_client
        self.fallback = fallback
    
    def get_system_prompt(self) -> str:
        return WORKLOAD_INTEL_PROMPT
    
    async def run(self, input_data: WorkloadIntelInput) -> WorkloadIntelOutput:
        context = {
            "project_id": str(input_data.project_id),
            "assignments": input_data.assignments,
            "story_points": input_data.story_points,
        }
        
        try:
            response = await self.llm.generate_structured(
                system_prompt=self.get_system_prompt(),
                user_prompt=f"Analyze workload distribution: {context}",
                output_schema=WorkloadIntelOutput.model_json_schema(),
            )
            return WorkloadIntelOutput(**response)
        except Exception as e:
            return self.fallback.workload_intel_analysis(input_data)