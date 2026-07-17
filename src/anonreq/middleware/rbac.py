"""RBAC middleware with role hierarchy verification.

Provides:
- Role enum with 4 levels: ADMINISTRATOR, SECURITY_OFFICER, OPERATOR,
  READ_ONLY_AUDITOR
- Role hierarchy with numerical ordering for >= comparisons
- require_role() FastAPI dependency that verifies minimum role from auth context
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from fastapi import HTTPException, Request


class Role(StrEnum):
    ADMINISTRATOR = "administrator"
    SECURITY_OFFICER = "security_officer"
    OPERATOR = "operator"
    READ_ONLY_AUDITOR = "read_only_auditor"
    READ_ONLY = "read_only_auditor"


ROLE_HIERARCHY: dict[Role, int] = {
    Role.ADMINISTRATOR: 4,
    Role.SECURITY_OFFICER: 3,
    Role.OPERATOR: 2,
    Role.READ_ONLY_AUDITOR: 1,
}


def _normalize_role_value(role: str) -> str:
    if role == "read_only":
        return Role.READ_ONLY_AUDITOR.value
    return role


def require_role(minimum_role: Role) -> Callable:
    """Create a FastAPI dependency that enforces a minimum role requirement.

    The dependency extracts the authenticated principal from request state
    (set by auth middleware) and checks that their role is >= the minimum
    required role in the hierarchy.

    Args:
        minimum_role: The minimum role required for this endpoint.

    Returns:
        A FastAPI dependency callable that returns None on success and
        raises HTTPException(401) or HTTPException(403) on failure.
    """

    async def _role_checker(request: Request) -> None:
        principal = getattr(request.state, "role_principal", None)
        if principal is None:
            raise HTTPException(
                status_code=401,
                detail={"error": "unauthorized", "message": "Authentication required"},
            )

        user_role_str = _normalize_role_value(principal.get("role", ""))
        try:
            user_role = Role(user_role_str)
        except ValueError:
            raise HTTPException(  # noqa: B904
                status_code=403,
                detail={"error": "forbidden", "reason": "unknown_role", "role": user_role_str},
            )

        if ROLE_HIERARCHY.get(user_role, 0) < ROLE_HIERARCHY.get(minimum_role, 0):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "forbidden",
                    "reason": "insufficient_role",
                    "required_role": minimum_role.value,
                    "user_role": user_role.value,
                },
            )

    return _role_checker
