from typing import Optional
from ai_service.app.agents.base import BaseAgent
from ai_service.app.models.agent_base import ProgressInput, ProgressOutput
from ai_service.app.llm.client import GroqClient
from ai_service.app.llm.fallback import RuleBasedFallback
from ai_service.app.prompts.progress import PROGRESS_PROMPT


class ProgressAgent(BaseAgent[ProgressInput, ProgressOutput]):
    def __init__(self, llm_client: GroqClient, fallback: RuleBasedFallback):
        super().__init__("progress")
        self.llm = llm_client
        self.fallback = fallback
    
    def get_system_prompt(self) -> str:
        return PROGRESS_PROMPT
    
    async def run(self, input_data: ProgressInput) -> ProgressOutput:
        context = {
            "project_id": str(input_data.project_id),
            "tasks": input_data.tasks,
            "velocity_history": input_data.velocity_history,
            "burndown_data": input_data.burndown_data,
        }
        
        try:
            response = await self.llm.generate_structured(
                system_prompt=self.get_system_prompt(),
                user_prompt=f"Analyze this project progress data: {context}",
                output_schema=ProgressOutput.model_json_schema(),
            )
            return ProgressOutput(**response)
        except Exception as e:
            return self.fallback.progress_analysis(input_data)