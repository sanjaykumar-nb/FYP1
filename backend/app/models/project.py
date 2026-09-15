from sqlalchemy import String, Text, Date, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from app.models.base import BaseModel


class Project(BaseModel):
    __tablename__ = "projects"

    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    key: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    health_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")
    team: Mapped["Team | None"] = relationship("Team", back_populates="projects")
    members: Mapped[list["ProjectMember"]] = relationship("ProjectMember", back_populates="project", lazy="dynamic")
    milestones: Mapped[list["Milestone"]] = relationship("Milestone", back_populates="project", lazy="dynamic")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="project", lazy="dynamic")
    meetings: Mapped[list["Meeting"]] = relationship("Meeting", back_populates="project", lazy="dynamic")
    communication_events: Mapped[list["CommunicationEvent"]] = relationship("CommunicationEvent", back_populates="project", lazy="dynamic")
    workload_snapshots: Mapped[list["WorkloadSnapshot"]] = relationship("WorkloadSnapshot", back_populates="project", lazy="dynamic")
    risk_scores: Mapped[list["RiskScore"]] = relationship("RiskScore", back_populates="project", lazy="dynamic")
    recommendations: Mapped[list["Recommendation"]] = relationship("Recommendation", back_populates="project", lazy="dynamic")
    agent_runs: Mapped[list["AgentRun"]] = relationship("AgentRun", back_populates="project", lazy="dynamic")
    memory_entries: Mapped[list["OrganizationMemory"]] = relationship("OrganizationMemory", back_populates="project", lazy="dynamic")
    task_dependencies: Mapped[list["TaskDependency"]] = relationship("TaskDependency", back_populates="project", lazy="dynamic")

    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_project_org_key"),
    )


class ProjectMember(BaseModel):
    __tablename__ = "project_members"

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
    role: Mapped[str] = mapped_column(String(50), default="developer", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="project_memberships")

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )


class Milestone(BaseModel):
    __tablename__ = "milestones"

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # With target_date, the schedule window the AI service's pace (burn-down) warning uses.
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="upcoming", nullable=False)
    progress: Mapped[float] = mapped_column(Numeric(3, 2), default=0.00, nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="milestones")