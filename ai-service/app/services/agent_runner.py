from typing import Optional
from uuid import UUID
from app.agents.coordinator import CoordinatorAgent
from app.models.agent_base import CoordinatorInput, ReviewTrioInput


async def run_full_analysis(
    coordinator: CoordinatorAgent,
    project_id: UUID,
    scope: list[str],
    trigger_type: str = "manual",
    snapshot: Optional[dict] = None,
    triggered_by: UUID = None,
) -> dict:
    """Run full multi-agent analysis pipeline"""

    input_data = CoordinatorInput(
        project_id=project_id,
        organization_id=UUID("00000000-0000-0000-0000-000000000000"),  # Would come from context
        triggered_by=triggered_by,
        trigger_type=trigger_type,
        scope=scope,
        context={"snapshot": snapshot} if snapshot else {},
    )
    
    result = await coordinator.run(input_data)
    
    # In production, store result in database via API call to core backend
    # For now, return the result
    return result.model_dump()


async def run_single_agent(
    coordinator: CoordinatorAgent,
    agent_name: str,
    project_id: UUID,
    input_data: dict,
) -> dict:
    """Run a single specialist agent"""
    
    agent_map = {
        "planning": coordinator.planning_agent,
        "progress": coordinator.progress_agent,
        "meeting_intelligence": coordinator.meeting_intel_agent,
        "communication_intelligence": coordinator.comm_intel_agent,
        "workload_intelligence": coordinator.workload_intel_agent,
        "risk_prediction": coordinator.risk_agent,
        "recommendation": coordinator.recommendation_agent,
        "frontend_review": coordinator.frontend_agent,
        "backend_review": coordinator.backend_agent,
        "ai_ml_review": coordinator.ai_ml_agent,
    }
    
    agent = agent_map.get(agent_name)
    if not agent:
        raise ValueError(f"Unknown agent: {agent_name}")
    
    # Create appropriate input based on agent
    from app.models.agent_base import (
        PlanningInput, ProgressInput, MeetingIntelInput,
        CommIntelInput, WorkloadIntelInput, RiskInput, RecommendationInput,
    )
    
    input_class_map = {
        "planning": PlanningInput,
        "progress": ProgressInput,
        "meeting_intelligence": MeetingIntelInput,
        "communication_intelligence": CommIntelInput,
        "workload_intelligence": WorkloadIntelInput,
        "risk_prediction": RiskInput,
        "recommendation": RecommendationInput,
    }
    
    input_class = input_class_map.get(agent_name)
    if input_class:
        typed_input = input_class(project_id=project_id, **input_data)
    else:
        typed_input = input_data
    
    result = await agent.run(typed_input)
    return result.model_dump()


async def run_review_trio(
    coordinator: CoordinatorAgent,
    request: ReviewTrioInput,
) -> dict:
    """Run the professional review trio"""
    
    # The coordinator handles review trio internally when scope includes "review"
    input_data = CoordinatorInput(
        project_id=request.project_id,
        organization_id=UUID("00000000-0000-0000-0000-000000000000"),
        triggered_by=request.requested_by,
        trigger_type="review",
        scope=["review"],
        context={"proposal": request.proposal},
    )
    
    result = await coordinator.run(input_data)
    
    # Extract review results
    review_results = {}
    for key, value in result.specialist_outputs.items():
        if key.startswith("review_"):
            review_results[key.replace("review_", "")] = value
    
    return {
        "consensus": "approve",  # Would be computed from individual reviews
        "confidence": 0.8,
        "individual_reviews": [
            {"agent": k, "verdict": v.get("risk_level", "unknown"), "concerns": [], "suggestions": []}
            for k, v in review_results.items()
        ],
        "conflicts_resolved": [],
        "final_recommendation": "Review completed",
        "required_changes": [],
    }