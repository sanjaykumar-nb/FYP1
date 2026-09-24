"""Every protected endpoint against every built-in role, derived from the code itself.

Each protected route declares the permission(s) it needs through
require_permission(...), on the route or on its router. This reads those
declarations off every route, then sends the request as each role: a role the
policy (core/permissions.py) does not grant must get 403, and one it does must get
past the check. The check runs before the request body is read, so an empty body
is enough — an allowed role then fails later (404/422), never with 403.

A second test fails if any state-changing route is added without a permission
check, unless it is listed below with the reason it needs none.
"""

import pytest
from uuid import uuid4

from fastapi.routing import APIRoute
from httpx import AsyncClient

from app.core.permissions import PERMISSIONS, has_permission
from app.main import app

pytestmark = pytest.mark.mvp

ROLES = ["viewer", "developer", "project_manager", "admin", "owner"]
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# State-changing routes that deliberately have no role check, and why.
UNGATED_BY_DESIGN = {
    ("POST", "/api/v1/auth/register"): "creates a new account and its own workspace",
    ("POST", "/api/v1/auth/login"): "sign-in",
    ("POST", "/api/v1/auth/refresh"): "token refresh for an existing session",
    ("POST", "/api/v1/auth/logout"): "ends the caller's own session",
    ("PATCH", "/api/v1/auth/me"): "edits the caller's own profile",
    ("POST", "/api/v1/organizations"): "creates a new, empty organization owned by the caller",
    ("POST", "/api/v1/projects/{project_id}/github/webhook"):
        "GitHub calls it; every request must carry a signature made with the project's own secret",
}


def _declared_permissions(route: APIRoute) -> list[str]:
    """Every permission a route's require_permission(...) dependencies were created with."""
    found = []
    for dependency in route.dependant.dependencies:
        check = dependency.call
        if getattr(check, "__qualname__", "").startswith("require_permission.") and check.__closure__:
            found += [cell.cell_contents for cell in check.__closure__ if isinstance(cell.cell_contents, str)]
    return found


def _gated_routes() -> list[tuple[str, str, tuple[str, ...]]]:
    found = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            permissions = tuple(sorted(set(_declared_permissions(route))))
            if permissions:
                found += [(method, route.path, permissions) for method in sorted(route.methods)]
    return sorted(found)


GATED = _gated_routes()


def _url(path: str, org_id) -> str:
    # The caller's own organization (another one is refused for a different reason);
    # a fresh id for everything else, since the check runs before any lookup.
    def fill(part: str) -> str:
        if part == "{org_id}":
            return str(org_id)
        return str(uuid4()) if part.startswith("{") else part

    return "/".join(fill(p) for p in path.split("/"))


def test_the_matrix_covers_the_routes_it_should():
    declared = {p for _, _, perms in GATED for p in perms}
    assert len(GATED) >= 30
    assert declared >= {
        "project:create", "project:update", "project:delete", "task:create", "task:update",
        "task:delete", "member:invite", "member:remove", "member:update_role", "analytics:run",
        "meeting:create", "meeting:update", "settings:read",
    }


def test_no_state_changing_route_is_unprotected_by_accident():
    ungated = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/v1/"):
            continue
        for method in route.methods & WRITE_METHODS:
            if not _declared_permissions(route) and (method, route.path) not in UNGATED_BY_DESIGN:
                ungated.append(f"{method} {route.path}")
    assert not sorted(ungated), f"routes that change state with no role check: {sorted(ungated)}"


@pytest.mark.parametrize("role", ROLES)
async def test_each_role_gets_exactly_what_the_policy_grants(client: AsyncClient, user_with_role, test_org, role):
    headers = await user_with_role(role)
    wrong = []
    for method, path, permissions in GATED:
        response = await client.request(method, _url(path, test_org.id), json={}, headers=headers)
        allowed = all(has_permission(PERMISSIONS[role], p) for p in permissions)
        if allowed and response.status_code == 403:
            wrong.append(f"{role} refused {method} {path} {permissions} though the policy grants it")
        if not allowed and response.status_code != 403:
            wrong.append(f"{role} got {response.status_code} on {method} {path} {permissions}, expected 403")
    assert not wrong, "\n".join(wrong)
