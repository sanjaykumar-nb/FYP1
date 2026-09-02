from app.agents.base import BaseAgent
from app.agents.graph_grounded import run_graph_grounded
from app.models.agent_base import ProgressInput, ProgressOutput
from app.llm.client import GroqClient
from app.llm.fallback import RuleBasedFallback
from app.prompts.progress import PROGRESS_PROMPT


class ProgressAgent(BaseAgent[ProgressInput, ProgressOutput]):
    def __init__(self, llm_client: GroqClient, fallback: RuleBasedFallback):
        super().__init__("progress")
        self.llm = llm_client
        self.fallback = fallback

    def get_system_prompt(self) -> str:
        return PROGRESS_PROMPT

    async def run(self, input_data: ProgressInput) -> ProgressOutput:
        if input_data.finding_ids is not None:
            user_prompt = (
                "Explain these project progress findings, citing only the node "
                f"ids shown below as evidence:\n{input_data.graph_context}"
            )
        else:
            context = {
                "project_id": str(input_data.project_id),
                "tasks": input_data.tasks,
                "velocity_history": input_data.velocity_history,
                "burndown_data": input_data.burndown_data,
            }
            user_prompt = f"Analyze this project progress data: {context}"

        return await run_graph_grounded(
            llm=self.llm,
            system_prompt=self.get_system_prompt(),
            user_prompt=user_prompt,
            output_model=ProgressOutput,
            finding_ids=input_data.finding_ids,
            fallback=lambda: self.fallback.progress_analysis(input_data),
        )
