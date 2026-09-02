from sqlalchemy import String, Text, JSON, ForeignKey, UniqueConstraint
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Role(BaseModel):
    __tablename__ = "roles"

    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # owner, admin, project_manager, developer, viewer
    permissions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="roles")
    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="role", lazy="dynamic")


class UserRole(BaseModel):
    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="user_roles")
    role: Mapped["Role"] = relationship("Role", back_populates="user_roles")
    organization: Mapped["Organization"] = relationship("Organization")
    project: Mapped["Project | None"] = relationship("Project")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "organization_id", "project_id", name="uq_user_role_org_project"),
    )