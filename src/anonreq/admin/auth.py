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


_MAX_TENANT_LEN = 64


def _clean_tenant(value: object) -> str | None:
    """A concrete tenant id, or None for missing, blank, ``*`` or malformed."""
    if not isinstance(value, str):
        return None
    tenant = value.strip()
    if not tenant or tenant == "*" or len(tenant) > _MAX_TENANT_LEN:
        return None
    if any(ord(char) < 32 or char == "\x7f" for char in tenant):
        return None
    return tenant


def validate_admin_settings() -> None:
    """Fail startup when the admin key is not bound to a tenant.

    ``ANONREQ_ADMIN_API_KEY`` without ``ANONREQ_ADMIN_TENANT_ID`` would leave
    the key unscoped, so the app refuses to start instead.
    """
    if settings.ADMIN_API_KEY and _clean_tenant(settings.ADMIN_TENANT_ID) is None:
        raise RuntimeError(
            "ANONREQ_ADMIN_API_KEY is set but ANONREQ_ADMIN_TENANT_ID is missing "
            "or invalid; set the tenant the admin key is bound to."
        )


def _reject_header_mismatch(request: Request, tenant: str) -> None:
    """403 when ``X-AnonReq-Tenant-ID`` is present and names another tenant."""
    raw = request.headers.get("X-AnonReq-Tenant-ID")
    if raw is None:
        return
    if raw.strip() != tenant:
        raise HTTPException(
            status_code=403,
            detail="X-AnonReq-Tenant-ID does not match the credential tenant",
        )


def admin_key_principal(request: Request) -> dict[str, Any]:
    """Role principal for the legacy admin key, bound to ANONREQ_ADMIN_TENANT_ID.

    The tenant comes from server configuration, never from the request. A
    present but different ``X-AnonReq-Tenant-ID`` is rejected with 403.
    """
    tenant = _clean_tenant(settings.ADMIN_TENANT_ID)
    if tenant is None:
        raise HTTPException(status_code=403, detail="Admin API key is not bound to a tenant")
    _reject_header_mismatch(request, tenant)
    return {
        "principal_id": "admin",
        "role": settings.ADMIN_ROLE,
        "tenant_id": tenant,
    }


def _oidc_role_principal(request: Request, principal: dict[str, Any]) -> dict[str, Any]:
    tenant = _clean_tenant(principal.get("tenant_id"))
    if tenant is None:
        raise HTTPException(status_code=403, detail="Token is not bound to a tenant")
    _reject_header_mismatch(request, tenant)
    scoped = dict(principal)
    scoped["tenant_id"] = tenant
    return scoped


async def bind_governance_role(
    request: Request,
    authorization: str | None = Header(None),
) -> None:
    """Verify the credential and set ``role_principal`` for governance routes.

    Accepts an OIDC admin token or the legacy admin API key. The admin key's
    tenant is ``ANONREQ_ADMIN_TENANT_ID``; an OIDC token's tenant is its
    claim. Neither is ever ``"*"``, and a present but different
    ``X-AnonReq-Tenant-ID`` is 403. The gateway chat key is a different
    credential and is rejected with 403. Missing or unknown credentials
    are 401.

    The credential is always verified. A principal already on
    ``request.state`` is overwritten, never trusted.
    """
    request.state.role_principal = None

    if _oidc_configured():
        try:
            verifier = _get_oidc_verifier(request)
            principal = await verifier.verify_authorization(authorization)
        except OIDCVerificationError as exc:
            raise HTTPException(status_code=401, detail="Invalid token") from exc
        request.state.oidc_principal = principal
        request.state.role_principal = _oidc_role_principal(request, principal)
        return

    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    admin_key = settings.ADMIN_API_KEY or ""
    gateway_key = settings.API_KEY or ""
    if admin_key and hmac.compare_digest(token, admin_key):
        request.state.role_principal = admin_key_principal(request)
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
