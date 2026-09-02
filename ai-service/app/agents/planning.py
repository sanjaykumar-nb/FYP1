from app.agents.base import BaseAgent
from app.agents.graph_grounded import run_graph_grounded
from app.models.agent_base import PlanningInput, PlanningOutput
from app.llm.client import GroqClient
from app.llm.fallback import RuleBasedFallback
from app.prompts.planning import PLANNING_PROMPT


class PlanningAgent(BaseAgent[PlanningInput, PlanningOutput]):
    def __init__(self, llm_client: GroqClient, fallback: RuleBasedFallback):
        super().__init__("planning")
        self.llm = llm_client
        self.fallback = fallback

    def get_system_prompt(self) -> str:
        return PLANNING_PROMPT

    async def run(self, input_data: PlanningInput) -> PlanningOutput:
        if input_data.finding_ids is not None:
            # Graph-grounded path: the LLM sees only the computed findings and
            # their witness subgraph, never the raw task/milestone dump.
            user_prompt = (
                "Explain these project planning findings, citing only the node "
                f"ids shown below as evidence:\n{input_data.graph_context}"
            )
        else:
            # Legacy path (e.g. the single-agent diagnostic endpoint called
            # directly without a project snapshot).
            context = {
                "project_id": str(input_data.project_id),
                "milestones": input_data.milestones,
                "tasks": input_data.tasks,
                "team_capacity": input_data.team_capacity,
            }
            user_prompt = f"Analyze this project planning data: {context}"

        return await run_graph_grounded(
            llm=self.llm,
            system_prompt=self.get_system_prompt(),
            user_prompt=user_prompt,
            output_model=PlanningOutput,
            finding_ids=input_data.finding_ids,
            fallback=lambda: self.fallback.planning_analysis(input_data),
        )
