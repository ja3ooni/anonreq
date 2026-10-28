"""Admin authentication for OIDC-backed identity verification."""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import Header, HTTPException, Request

from anonreq.auth.oidc import OIDCVerificationError, build_oidc_verifier
from anonreq.config import settings
from anonreq.state import get_app_state


def _oidc_configured() -> bool:
    return all(
        (
            settings.OIDC_ISSUER,
            settings.OIDC_AUDIENCE,
            settings.OIDC_JWKS_URL,
        )
    )


def _legacy_admin_auth_enabled() -> bool:
    return not _oidc_configured() and bool(settings.ADMIN_API_KEY)


def _get_oidc_verifier(request: Request) -> Any:
    state = get_app_state(request.app)
    verifier = state.oidc_verifier
    if verifier is None:
        verifier = build_oidc_verifier(
            issuer=settings.OIDC_ISSUER or "",
            audience=settings.OIDC_AUDIENCE or "",
            jwks_url=settings.OIDC_JWKS_URL or "",
            role_claim=settings.OIDC_ROLE_CLAIM,
            cache_ttl_seconds=settings.OIDC_JWKS_CACHE_SECONDS,
        )
        state.oidc_verifier = verifier
    return verifier


async def verify_admin_api_key(
    request: Request,
    authorization: str | None = Header(None),
) -> bool:
    """Verify admin access using OIDC JWTs or a legacy API-key fallback.

    The OIDC path is used whenever issuer, audience, and JWKS settings are
    present. In environments that have not been migrated yet, the legacy
    API-key path remains available as a compatibility fallback.
    """
    if _oidc_configured():
        try:
            verifier = _get_oidc_verifier(request)
            principal = await verifier.verify_authorization(authorization)
        except OIDCVerificationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        request.state.oidc_principal = principal
        return True

    if _legacy_admin_auth_enabled():
        if authorization is None:
            raise HTTPException(
                status_code=401,
                detail="Missing Authorization header",
            )

        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(
            token, settings.ADMIN_API_KEY or ""
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid admin API key",
            )
        # "*" is not a tenant. Audit reads then take the tenant from the
        # validated X-AnonReq-Tenant-ID header. The key is not bound to a
        # tenant; that binding is https://github.com/ja3ooni/anonreq/issues/7.
        principal = {
            "principal_id": "admin",
            "role": settings.ADMIN_ROLE,
            "tenant_id": "*",
        }
        request.state.oidc_principal = principal
        return True

    raise HTTPException(
        status_code=401,
        detail="Admin API not configured",
    )


def _header_tenant(request: Request) -> str:
    """Tenant from ``X-AnonReq-Tenant-ID``. Never ``*`` or blank.

    The legacy admin key is not stored against a tenant. Governance reads
    copy this header onto the principal instead of keeping the wildcard.
    See https://github.com/ja3ooni/anonreq/issues/7.
    """
    raw = request.headers.get("X-AnonReq-Tenant-ID", "")
    tenant = raw.strip() if isinstance(raw, str) else ""
    if not tenant:
        state_tenant = getattr(request.state, "tenant_id", None)
        if isinstance(state_tenant, str):
            tenant = state_tenant.strip()
    if not tenant or tenant == "*":
        raise HTTPException(
            status_code=403,
            detail="X-AnonReq-Tenant-ID header required",
        )
    return tenant


def _without_wildcard_tenant(request: Request, principal: dict[str, Any]) -> dict[str, Any]:
    tenant = principal.get("tenant_id")
    if isinstance(tenant, str) and tenant.strip() and tenant.strip() != "*":
        return principal
    scoped = dict(principal)
    scoped["tenant_id"] = _header_tenant(request)
    return scoped


async def bind_governance_role(
    request: Request,
    authorization: str | None = Header(None),
) -> None:
    """Set ``role_principal`` for governance routes.

    Accepts an OIDC admin token or the legacy admin API key. The admin key's
    tenant is ``X-AnonReq-Tenant-ID`` and is never ``"*"``. The gateway chat
    key is a different credential and is rejected with 403. Missing or
    unknown credentials are 401.

    A principal already on the request (tests, or an upstream auth layer)
    is left unchanged.
    """
    existing = getattr(request.state, "role_principal", None)
    if isinstance(existing, dict) and existing.get("role"):
        return

    if _oidc_configured():
        try:
            verifier = _get_oidc_verifier(request)
            principal = await verifier.verify_authorization(authorization)
        except OIDCVerificationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        request.state.oidc_principal = principal
        request.state.role_principal = _without_wildcard_tenant(request, principal)
        return

    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    admin_key = settings.ADMIN_API_KEY or ""
    gateway_key = settings.API_KEY or ""
    if admin_key and hmac.compare_digest(token, admin_key):
        request.state.role_principal = {
            "principal_id": "admin",
            "role": settings.ADMIN_ROLE,
            "tenant_id": _header_tenant(request),
        }
        return
    if gateway_key and hmac.compare_digest(token, gateway_key):
        raise HTTPException(
            status_code=403,
            detail="Gateway API key cannot access governance routes",
        )
    raise HTTPException(status_code=401, detail="Invalid admin API key")


def get_admin_api_key() -> str | None:
    """Return the configured legacy admin API key, if any."""
    return settings.ADMIN_API_KEY
