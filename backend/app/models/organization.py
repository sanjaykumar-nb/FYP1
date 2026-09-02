from sqlalchemy import String, Text, JSON
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Organization(BaseModel):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="organization", lazy="dynamic")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="organization", lazy="dynamic")
    teams: Mapped[list["Team"]] = relationship("Team", back_populates="organization", lazy="dynamic")
    roles: Mapped[list["Role"]] = relationship("Role", back_populates="organization", lazy="dynamic")
    memory_entries: Mapped[list["OrganizationMemory"]] = relationship("OrganizationMemory", back_populates="organization", lazy="dynamic")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="organization", lazy="dynamic")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="organization", lazy="dynamic")