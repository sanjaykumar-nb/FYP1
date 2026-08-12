from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class WSEvent(BaseModel):
    event: str
    data: dict
    project_id: Optional[UUID] = None


class WSSubscribe(BaseModel):
    project_id: UUID


class WSUnsubscribe(BaseModel):
    project_id: UUID


class WSAuth(BaseModel):
    token: str


# Event types
class TaskUpdatedEvent(WSEvent):
    event: str = "task.updated"


class TaskCreatedEvent(WSEvent):
    event: str = "task.created"


class RiskUpdatedEvent(WSEvent):
    event: str = "risk.updated"


class RecommendationCreatedEvent(WSEvent):
    event: str = "recommendation.created"


class NotificationNewEvent(WSEvent):
    event: str = "notification.new"


class AnalysisStartedEvent(WSEvent):
    event: str = "analysis.started"


class AnalysisCompletedEvent(WSEvent):
    event: str = "analysis.completed"


class AnalysisFailedEvent(WSEvent):
    event: str = "analysis.failed"