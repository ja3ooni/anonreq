"""Admin API router with authentication and RBAC protection.

Aggregates policy management routes under a single router with:
- Router-level admin API key authentication
- Per-endpoint RBAC via require_role dependencies

Usage in main.py::

    from anonreq.admin import admin_router
    app.include_router(admin_router, dependencies=[Depends(auth_context)])
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from anonreq.admin.aml_webhook_routes import router as aml_webhook_router
from anonreq.admin.auth import verify_admin_api_key
from anonreq.admin.incident_routes import router as incident_router
from anonreq.admin.policy_routes import router as policy_router
from anonreq.admin.provider_routes import router as provider_router
from anonreq.admin.usage_routes import router as usage_router
from anonreq.config import settings
from anonreq.middleware.rbac import Role

# Re-export Role so admin routes and tests can reference it
__all__ = ["admin_router", "Role"]


async def require_auth(
    request: Request,
    authorized: bool = Depends(verify_admin_api_key),
) -> None:
    """Verify admin API key and populate principal for RBAC.

    This dependency:
    1. Verifies the Bearer token against ANONREQ_ADMIN_API_KEY
    2. Populates ``request.state.role_principal`` with the configured
       admin role, unless a principal has already been set (e.g., by
       test middleware or an upstream auth layer)

    Args:
        request: The incoming FastAPI request.
        authorized: Whether the admin API key is valid.
            Provided by verify_admin_api_key dependency.

    Raises:
        HTTPException: If the admin API key is invalid.
    """
    # Only set principal if not already present (allows test injection
    # or upstream auth to provide the role)
    if getattr(request.state, "role_principal", None) is None:
        role = settings.ADMIN_ROLE
        request.state.role_principal = {
            "principal_id": "admin",
            "role": role,
            "tenant_id": "*",
        }


admin_router = APIRouter(
    prefix="/v1/admin",
    dependencies=[Depends(require_auth)],
)
admin_router.include_router(policy_router)
admin_router.include_router(provider_router)
admin_router.include_router(usage_router)
admin_router.include_router(incident_router)
admin_router.include_router(aml_webhook_router)
