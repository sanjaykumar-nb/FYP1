from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from ai_service.app.models.agent_base import AnalyzeRequest, AnalyzeResponse, CoordinatorInput, ReviewTrioInput
from ai_service.app.agents.coordinator import CoordinatorAgent
from ai_service.app.agents.planning import PlanningAgent
from ai_service.app.agents.progress import ProgressAgent
from ai_service.app.agents.meeting_intel import MeetingIntelligenceAgent
from ai_service.app.agents.comm_intel import CommunicationIntelligenceAgent
from ai_service.app.agents.workload_intel import WorkloadIntelligenceAgent
from ai_service.app.agents.risk import RiskPredictionAgent
from ai_service.app.agents.recommendation import RecommendationAgent
from ai_service.app.agents.frontend_review import FrontendAgent
from ai_service.app.agents.backend_review import BackendAgent
from ai_service.app.agents.ai_ml_review import AIMLAgent
from ai_service.app.llm.client import GroqClient
from ai_service.app.llm.fallback import RuleBasedFallback
from ai_service.app.validators import validate_output
from ai_service.app.services.agent_runner import run_full_analysis, run_single_agent, run_review_trio

router = APIRouter()

# Initialize agents
llm_client = GroqClient()
fallback = RuleBasedFallback()

planning_agent = PlanningAgent(llm_client, fallback)
progress_agent = ProgressAgent(llm_client, fallback)
meeting_intel_agent = MeetingIntelligenceAgent(llm_client, fallback)
comm_intel_agent = CommunicationIntelligenceAgent(llm_client, fallback)
workload_intel_agent = WorkloadIntelligenceAgent(llm_client, fallback)
risk_agent = RiskPredictionAgent(llm_client, fallback)
recommendation_agent = RecommendationAgent(llm_client, fallback)
frontend_agent = FrontendAgent(llm_client, fallback)
backend_agent = BackendAgent(llm_client, fallback)
ai_ml_agent = AIMLAgent(llm_client, fallback)

coordinator_agent = CoordinatorAgent(
    llm_client=llm_client,
    fallback=fallback,
    planning_agent=planning_agent,
    progress_agent=progress_agent,
    meeting_intel_agent=meeting_intel_agent,
    comm_intel_agent=comm_intel_agent,
    workload_intel_agent=workload_intel_agent,
    risk_agent=risk_agent,
    recommendation_agent=recommendation_agent,
    frontend_agent=frontend_agent,
    backend_agent=backend_agent,
    ai_ml_agent=ai_ml_agent,
)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_project(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger full multi-agent analysis for a project"""
    try:
        # Run analysis in background
        background_tasks.add_task(
            run_full_analysis,
            coordinator_agent,
            request.project_id,
            request.scope,
            request.trigger_type,
        )
        
        return AnalyzeResponse(
            agent_run_id=UUID("00000000-0000-0000-0000-000000000000"),  # Will be generated in background
            status="started",
            message="Analysis started in background",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start analysis: {str(e)}",
        )


@router.post("/agents/{agent_name}")
async def run_agent(
    agent_name: str,
    project_id: UUID,
    input_data: dict,
):
    """Run a single specialist agent"""
    try:
        result = await run_single_agent(coordinator_agent, agent_name, project_id, input_data)
        
        # Validate output
        valid, errors = validate_output(agent_name, result)
        if not valid:
            return {"warning": "Output validation failed", "errors": errors, "data": result}
        
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}",
        )


@router.post("/review")
async def run_review(
    request: ReviewTrioInput,
):
    """Run the professional review trio (Frontend, Backend, AI/ML)"""
    try:
        result = await run_review_trio(coordinator_agent, request)
        
        valid, errors = validate_output("review_trio", result)
        if not valid:
            return {"warning": "Output validation failed", "errors": errors, "data": result}
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Review failed: {str(e)}",
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "TeamSync AI Service",
        "agents": [
            "planning", "progress", "meeting_intelligence",
            "communication_intelligence", "workload_intelligence",
            "risk_prediction", "recommendation",
            "frontend_review", "backend_review", "ai_ml_review",
        ],
    }