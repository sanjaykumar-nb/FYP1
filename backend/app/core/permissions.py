"""Role-based permission policy.

The built-in roles and what each may do are defined here, once: registration
seeds an organization's roles from PERMISSIONS, and app.api.deps.require_permission
checks requests against it. A custom role (created per organization) falls back to
the permission list stored on its Role row.

Roles are organization-wide — a person's role applies to every project in the
organization. Reads are gated by organization membership; every endpoint that
changes state names the permission it needs.
"""

from uuid import UUID

from app.models.role import Role

PERMISSIONS: dict[str, list[str]] = {
    "owner": ["*"],
    "admin": [
        "organization:read", "organization:update", "organization:delete",
        "project:create", "project:read", "project:update", "project:delete",
        "task:create", "task:read", "task:update", "task:delete",
        "member:invite", "member:remove", "member:update_role",
        "analytics:read", "analytics:run", "settings:read", "settings:update",
        "meeting:create", "meeting:read", "meeting:update",
    ],
    "project_manager": [
        "project:read", "project:update",
        "task:create", "task:read", "task:update", "task:delete",
        "member:invite", "member:update_role",
        "analytics:read", "analytics:run",
        "meeting:create", "meeting:read", "meeting:update",
    ],
    "developer": [
        "project:read",
        "task:create", "task:read", "task:update",
        "analytics:read", "meeting:read",
    ],
    "viewer": [
        "project:read", "task:read", "analytics:read", "meeting:read",
    ],
}

# Nobody may grant a role ranked above their own.
ROLE_RANK = {"viewer": 0, "developer": 1, "project_manager": 2, "admin": 3, "owner": 4}

# Someone with no role assignment gets the least privilege.
DEFAULT_ROLE = "viewer"


def default_roles(organization_id: UUID) -> list[Role]:
    return [
        Role(organization_id=organization_id, name=name, permissions=list(granted))
        for name, granted in PERMISSIONS.items()
    ]


def permissions_for(role_name: str, stored: list[str] | None = None) -> list[str]:
    return PERMISSIONS.get(role_name, stored or [])


def has_permission(granted: list[str], permission: str) -> bool:
    return "*" in granted or permission in granted


def can_grant(actor_role: str, role_name: str) -> bool:
    """Custom roles have no rank: only an owner may grant them, and they grant nothing."""
    return ROLE_RANK.get(actor_role, -1) >= ROLE_RANK.get(role_name, ROLE_RANK["owner"])
