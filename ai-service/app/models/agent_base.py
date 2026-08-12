from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class AgentSignal(BaseModel):
    name: str
    value: float | str
    weight: float = Field(..., ge=0, le=1)


class AgentEvidence(BaseModel):
    source: str
    reference_id: UUID
    excerpt: str
    relevance: float = Field(..., ge=0, le=1)


class AgentRecommendation(BaseModel):
    type: str
    title: str
    description: str
    reasoning: str
    priority: str
    confidence: float = Field(..., ge=0, le=1)


class AgentOutput(BaseModel):
    summary: str = Field(..., max_length=500)
    risk_level: str = Field(..., pattern="^(low|medium|high|critical)$")
    confidence: float = Field(..., ge=0, le=1)
    signals: list[AgentSignal] = []
    evidence: list[AgentEvidence] = []
    recommendations: list[AgentRecommendation] = []
    next_action: str = Field(..., max_length=500)
    metadata: dict = {}


class CoordinatorInput(BaseModel):
    project_id: UUID
    organization_id: UUID
    triggered_by: Optional[UUID] = None
    trigger_type: str = "manual"
    scope: list[str] = []
    context: dict = {}


class CoordinatorOutput(BaseModel):
    project_id: UUID
    overall_summary: str
    overall_risk_level: str = Field(..., pattern="^(low|medium|high|critical)$")
    overall_confidence: float = Field(..., ge=0, le=1)
    specialist_outputs: dict[str, AgentOutput] = {}
    merged_recommendations: list[AgentRecommendation] = []
    next_actions: list[str] = []


class ReviewTrioInput(BaseModel):
    proposal: dict
    project_id: UUID
    requested_by: UUID


class ReviewTrioOutput(BaseModel):
    consensus: str = Field(..., pattern="^(approve|approve_with_changes|request_revision|reject)$")
    confidence: float = Field(..., ge=0, le=1)
    individual_reviews: list[dict] = []
    conflicts_resolved: list[dict] = []
    final_recommendation: str
    required_changes: list[str] = []


class PlanningInput(BaseModel):
    project_id: UUID
    milestones: list[dict] = []
    tasks: list[dict] = []
    team_capacity: dict = {}


class PlanningOutput(AgentOutput):
    sprint_readiness: float = 0.0
    milestone_feasibility: dict = {}
    capacity_gaps: list[str] = []


class ProgressInput(BaseModel):
    project_id: UUID
    tasks: list[dict] = []
    velocity_history: list[float] = []
    burndown_data: list[dict] = []


class ProgressOutput(AgentOutput):
    velocity_trend: str = "stable"
    completion_forecast: str = ""
    stalled_work: list[dict] = []


class MeetingIntelInput(BaseModel):
    meeting_id: UUID
    transcript: str
    participants: list[dict] = []


class MeetingIntelOutput(AgentOutput):
    decisions: list[dict] = []
    action_items: list[dict] = []
    blockers: list[dict] = []
    owners: list[dict] = []
    deadlines: list[dict] = []
    unresolved_issues: list[dict] = []


class CommIntelInput(BaseModel):
    project_id: UUID
    events: list[dict] = []
    timeframe_days: int = 14


class CommIntelOutput(AgentOutput):
    response_delays: list[dict] = []
    unanswered_questions: list[dict] = []
    participation_gaps: list[dict] = []
    friction_points: list[dict] = []


class WorkloadIntelInput(BaseModel):
    project_id: UUID
    assignments: list[dict] = []
    story_points: dict = {}


class WorkloadIntelOutput(AgentOutput):
    overloaded_members: list[dict] = []
    underutilized_members: list[dict] = []
    dependency_concentration: list[dict] = []
    single_points_of_failure: list[dict] = []


class RiskInput(BaseModel):
    project_id: UUID
    specialist_outputs: dict = {}


class RiskOutput(AgentOutput):
    risk_scores: dict = {}


class RecommendationInput(BaseModel):
    project_id: UUID
    risk_scores: dict = {}
    specialist_outputs: dict = {}


class RecommendationOutput(AgentOutput):
    prioritized_actions: list[dict] = []


class AnalyzeRequest(BaseModel):
    project_id: UUID
    scope: list[str] = ["planning", "progress", "meetings", "communication", "workload"]
    trigger_type: str = "manual"


class AnalyzeResponse(BaseModel):
    agent_run_id: UUID
    status: str
    message: str