from sqlalchemy import String, Text, DateTime, ForeignKey, Numeric, JSON, Integer
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.models.base import BaseModel


class RiskScore(BaseModel):
    __tablename__ = "risk_scores"

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    risk_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    factors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    trend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    agent_run_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="risk_scores")
    agent_run: Mapped["AgentRun | None"] = relationship("AgentRun")


class Recommendation(BaseModel):
    __tablename__ = "recommendations"

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    risk_score_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_scores.id", ondelete="SET NULL"),
        nullable=True,
    )
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    assigned_to: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    implemented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="recommendations")
    risk_score: Mapped["RiskScore | None"] = relationship("RiskScore")
    assigned_to_user: Mapped["User | None"] = relationship("User", foreign_keys=[assigned_to], back_populates="recommendations_assigned")


class AgentRun(BaseModel):
    __tablename__ = "agent_runs"

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggered_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    trigger_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)
    coordinator_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    specialist_outputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    final_recommendations: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="agent_runs")
    triggered_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[triggered_by], back_populates="triggered_agent_runs")
    risk_scores: Mapped[list["RiskScore"]] = relationship("RiskScore", back_populates="agent_run")