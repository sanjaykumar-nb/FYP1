from app.agents.base import BaseAgent
from app.agents.graph_grounded import run_graph_grounded
from app.models.agent_base import WorkloadIntelInput, WorkloadIntelOutput
from app.llm.client import GroqClient
from app.llm.fallback import RuleBasedFallback
from app.prompts.workload_intel import WORKLOAD_INTEL_PROMPT


class WorkloadIntelligenceAgent(BaseAgent[WorkloadIntelInput, WorkloadIntelOutput]):
    def __init__(self, llm_client: GroqClient, fallback: RuleBasedFallback):
        super().__init__("workload_intelligence")
        self.llm = llm_client
        self.fallback = fallback

    def get_system_prompt(self) -> str:
        return WORKLOAD_INTEL_PROMPT

    async def run(self, input_data: WorkloadIntelInput) -> WorkloadIntelOutput:
        if input_data.finding_ids is not None:
            user_prompt = (
                "Explain these workload distribution findings, citing only the "
                f"node ids shown below as evidence:\n{input_data.graph_context}"
            )
        else:
            context = {
                "project_id": str(input_data.project_id),
                "assignments": input_data.assignments,
                "story_points": input_data.story_points,
            }
            user_prompt = f"Analyze workload distribution: {context}"

        return await run_graph_grounded(
            llm=self.llm,
            system_prompt=self.get_system_prompt(),
            user_prompt=user_prompt,
            output_model=WorkloadIntelOutput,
            finding_ids=input_data.finding_ids,
            fallback=lambda: self.fallback.workload_intel_analysis(input_data),
        )
