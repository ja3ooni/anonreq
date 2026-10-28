"""Tenant context middleware for multi-tenant request validation.

Provides:
- ``TenantContextMiddleware`` — validates ``X-AnonReq-Tenant-ID`` header,
  rejects missing/invalid/disabled tenants, and populates
  ``request.state.tenant_id`` for downstream middleware and pipeline.

Per D-01 through D-04:
- Hard reject HTTP 400 for missing/invalid tenant header
- HTTP 403 for disabled tenants
- Middleware runs after auth, before classification
"""

from __future__ import annotations

import structlog
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from anonreq.tenant.registry import TenantRegistry

logger = structlog.get_logger("anonreq.middleware.tenant")

_SKIP_PATHS = {"/health", "/health/ready", "/metrics", "/"}


def _single_tenant_default(request: Request) -> str:
    """Tenant for a header-less admin-key request in single-tenant mode.

    Only the admin API key gets a default (``ANONREQ_ADMIN_TENANT_ID``). Any
    other request without ``X-AnonReq-Tenant-ID`` still gets 400
    ``missing_tenant``. The key itself is verified later by the route.
    """
    import hmac

    from anonreq.config import settings

    if not settings.SINGLE_TENANT:
        return ""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    admin_key = settings.ADMIN_API_KEY or ""
    if (
        scheme.lower() == "bearer"
        and admin_key
        and settings.ADMIN_TENANT_ID
        and hmac.compare_digest(token, admin_key)
    ):
        return settings.ADMIN_TENANT_ID.strip()
    return ""


def validate_single_tenant(registry: TenantRegistry) -> None:
    """Fail startup when single-tenant mode meets a multi-tenant config.

    Counts every tenant loaded from ``ANONREQ_TENANTS_CONFIG_PATH`` (enabled
    or not). Single-tenant mode defaults a missing header, which is only
    safe when there is exactly one tenant.
    """
    from anonreq.config import settings

    if not settings.SINGLE_TENANT:
        return
    tenants = sorted(profile.tenant_id for profile in registry.list_all())
    if len(tenants) > 1:
        raise RuntimeError(
            "ANONREQ_SINGLE_TENANT=true but "
            f"{len(tenants)} tenants are configured in "
            f"{settings.TENANTS_CONFIG_PATH} ({', '.join(tenants)}). "
            "Configure exactly one tenant or set ANONREQ_SINGLE_TENANT=false."
        )


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Middleware that validates tenant context from the request header.

    Per D-01, requests missing X-AnonReq-Tenant-ID are rejected with HTTP 400.
    Per D-04, requests with disabled tenants are rejected with HTTP 403.
    Per D-03, validated tenant_id is placed on request.state for downstream use.
    """

    def __init__(self, app: ASGIApp, tenant_registry: TenantRegistry) -> None:
        super().__init__(app)
        self._registry = tenant_registry

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Skip health, metrics, and root paths
        if request.url.path in _SKIP_PATHS or not request.url.path.startswith("/v1/"):
            return await call_next(request)

        # Extract tenant_id from header
        tenant_id = request.headers.get("X-AnonReq-Tenant-ID", "").strip()

        # Single-tenant mode: a missing header defaults to the configured
        # tenant. A header that is present is still validated, and the admin
        # routes still reject one that does not match the credential (403).
        if not tenant_id:
            tenant_id = _single_tenant_default(request)

        # D-01: Hard reject for missing tenant header
        if not tenant_id:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "missing_tenant",
                    "message": "X-AnonReq-Tenant-ID header required",
                },
            )

        # Look up tenant in registry
        profile = self._registry.get(tenant_id)

        # Reject unknown tenant
        if profile is None:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_tenant",
                    "message": f"Unknown tenant: {tenant_id}",
                },
            )

        # D-04: Reject disabled tenant
        if not profile.enabled:
            return JSONResponse(
                status_code=403,
                content={"error": "tenant_disabled"},
            )

        # D-03: Populate request.state for downstream middleware/pipeline
        request.state.tenant_id = tenant_id
        request.state.tenant_profile = profile

        # D-10: Bind tenant_id to structlog contextvars
        structlog.contextvars.bind_contextvars(tenant_id=tenant_id)

        try:
            response = await call_next(request)
            return response
        finally:
            structlog.contextvars.unbind_contextvars("tenant_id")
