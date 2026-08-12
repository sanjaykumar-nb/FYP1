from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON, Boolean, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from app.models.base import BaseModel


class CommunicationEvent(BaseModel):
    __tablename__ = "communication_events"

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    response_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_question: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_blocker_mention: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="communication_events")
    user: Mapped["User"] = relationship("User", back_populates="communication_events")


class WorkloadSnapshot(BaseModel):
    __tablename__ = "workload_snapshots"

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    assigned_story_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_story_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    in_progress_story_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_story_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_task_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overdue_task_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    utilization_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="workload_snapshots")
    user: Mapped["User"] = relationship("User", back_populates="workload_snapshots")

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", "snapshot_date", name="uq_workload_snapshot"),
    )