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


class AnalyzeRequest(BaseModel):
    project_id: UUID
    scope: list[str] = ["planning", "progress", "meetings", "communication", "workload"]
    trigger_type: str = "manual"


class AnalyzeResponse(BaseModel):
    agent_run_id: UUID
    status: str
    message: str