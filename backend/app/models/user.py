from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Their GitHub handle, so commits and pull requests can be credited to them.
    github_username: Mapped[str | None] = mapped_column(String(39), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="user", lazy="dynamic")
    team_memberships: Mapped[list["TeamMember"]] = relationship("TeamMember", back_populates="user", lazy="dynamic")
    project_memberships: Mapped[list["ProjectMember"]] = relationship("ProjectMember", back_populates="user", lazy="dynamic")
    assigned_tasks: Mapped[list["Task"]] = relationship("Task", foreign_keys="Task.assignee_id", back_populates="assignee", lazy="dynamic")
    reported_tasks: Mapped[list["Task"]] = relationship("Task", foreign_keys="Task.reporter_id", back_populates="reporter", lazy="dynamic")
    task_comments: Mapped[list["TaskComment"]] = relationship("TaskComment", back_populates="user", lazy="dynamic")
    organized_meetings: Mapped[list["Meeting"]] = relationship("Meeting", foreign_keys="Meeting.organizer_id", back_populates="organizer", lazy="dynamic")
    meeting_participations: Mapped[list["MeetingParticipant"]] = relationship("MeetingParticipant", back_populates="user", lazy="dynamic")
    action_items: Mapped[list["MeetingActionItem"]] = relationship("MeetingActionItem", foreign_keys="MeetingActionItem.assignee_id", back_populates="assignee", lazy="dynamic")
    communication_events: Mapped[list["CommunicationEvent"]] = relationship("CommunicationEvent", back_populates="user", lazy="dynamic")
    workload_snapshots: Mapped[list["WorkloadSnapshot"]] = relationship("WorkloadSnapshot", back_populates="user", lazy="dynamic")
    triggered_agent_runs: Mapped[list["AgentRun"]] = relationship("AgentRun", foreign_keys="AgentRun.triggered_by", back_populates="triggered_by_user", lazy="dynamic")
    memory_entries: Mapped[list["OrganizationMemory"]] = relationship("OrganizationMemory", foreign_keys="OrganizationMemory.created_by", back_populates="created_by_user", lazy="dynamic")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="user", lazy="dynamic")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user", lazy="dynamic")
    recommendations_assigned: Mapped[list["Recommendation"]] = relationship("Recommendation", foreign_keys="Recommendation.assigned_to", back_populates="assigned_to_user", lazy="dynamic")