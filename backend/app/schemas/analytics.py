from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class RiskScoreResponse(BaseModel):
    id: UUID
    project_id: UUID
    risk_type: Optional[str] = None
    score: float
    level: Optional[str] = None
    factors: list
    evidence: list
    trend: Optional[str] = None
    computed_at: datetime

    class Config:
        from_attributes = True


class RecommendationResponse(BaseModel):
    id: UUID
    project_id: UUID
    risk_score_id: Optional[UUID] = None
    type: Optional[str] = None
    title: str
    description: Optional[str] = None
    reasoning: str
    confidence: Optional[float] = None
    priority: str
    status: str
    assigned_to: Optional[UUID] = None
    due_date: Optional[datetime] = None
    evidence: list
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectHealthResponse(BaseModel):
    health_score: float
    risk_score: float
    completion_rate: float
    overdue_tasks: int
    blocked_tasks: int
    active_milestones: int
    team_size: int
    workload_balance: float


class WorkloadDistributionResponse(BaseModel):
    user_id: UUID
    user_name: str
    assigned_points: int
    completed_points: int
    in_progress_points: int
    blocked_points: int
    active_tasks: int
    overdue_tasks: int
    utilization_score: Optional[float] = None


class BottleneckResponse(BaseModel):
    task_id: UUID
    task_title: str
    blocked_count: int
    blocking_tasks: list[UUID]
    assignee_id: Optional[UUID] = None


class CommunicationAnalysisResponse(BaseModel):
    total_messages: int
    avg_response_time_hours: float
    unanswered_questions: int
    participation_rate: float
    blocker_mentions: int
    low_participation_users: list[UUID]


class TeamIntelligenceIndexResponse(BaseModel):
    score: float
    tier: str
    health_score: float
    risk_score: float
    communication_score: float
    workload_balance: float
    memory_utilization: float
    computed_at: datetime


class AgentRunResponse(BaseModel):
    id: UUID
    project_id: UUID
    triggered_by: Optional[UUID] = None
    trigger_type: Optional[str] = None
    status: str
    coordinator_output: Optional[dict] = None
    specialist_outputs: Optional[dict] = None
    final_recommendations: Optional[dict] = None
    execution_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrganizationMemoryResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    memory_type: Optional[str] = None
    title: str
    content: str
    context: dict
    source: Optional[str] = None
    source_id: Optional[UUID] = None
    confidence: Optional[float] = None
    created_by: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: Optional[UUID] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    metadata: dict
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    type: Optional[str] = None
    title: str
    message: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    priority: str
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True