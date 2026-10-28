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
    """FastAPI dependency; see ``_verify_admin_credential``."""
    return await _verify_admin_credential(request, authorization)


async def _verify_admin_credential(
    request: Request,
    authorization: str | None,
) -> bool:
    """Verify admin access using OIDC JWTs or the legacy admin API key.

    With OIDC configured only verified tokens are accepted, and the legacy
    admin key is refused (401). Otherwise the admin key is accepted and bound
    to ``ANONREQ_ADMIN_TENANT_ID``. Either way ``request.state.oidc_principal``
    is set to a tenant-bound principal (never ``"*"``).
    """
    if _oidc_configured():
        try:
            verifier = _get_oidc_verifier(request)
            principal = await verifier.verify_authorization(authorization)
        except OIDCVerificationError:
            # Do not echo verifier text (issuer, claim names, key ids).
            raise HTTPException(status_code=401, detail="Invalid token") from None
        request.state.oidc_principal = _oidc_role_principal(request, principal)
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
        request.state.oidc_principal = admin_key_principal(request)
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
    if settings.ADMIN_API_KEY and settings.API_KEY and hmac.compare_digest(
        settings.ADMIN_API_KEY, settings.API_KEY,
    ):
        raise RuntimeError(
            "ANONREQ_ADMIN_API_KEY must differ from ANONREQ_API_KEY; the "
            "gateway chat key must never be an admin credential."
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


async def _bind_admin_principal(
    request: Request,
    authorization: str | None,
    route_label: str,
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
        except OIDCVerificationError:
            # Do not echo verifier text (issuer, claim names, key ids). With
            # OIDC enabled the legacy admin key is refused: it is not a JWT,
            # so it fails verification here and gets 401.
            raise HTTPException(status_code=401, detail="Invalid token") from None
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
            detail=f"Gateway API key cannot access {route_label} routes",
        )
    raise HTTPException(status_code=401, detail="Invalid admin API key")


async def bind_governance_role(
    request: Request,
    authorization: str | None = Header(None),
) -> None:
    """Router dependency for ``/v1/governance``. See ``_bind_admin_principal``."""
    await _bind_admin_principal(request, authorization, "governance")


async def accept_gateway_or_admin_key(
    request: Request,
    authorization: str | None = Header(None),
) -> None:
    """Admin-key or OIDC auth for administrator routes (audit, events, preview).

    Same rules as governance: always verified, tenant bound on the server,
    chat key 403, missing or unknown credential 401.
    """
    await _bind_admin_principal(request, authorization, "admin")


def get_admin_api_key() -> str | None:
    """Return the configured legacy admin API key, if any."""
    return settings.ADMIN_API_KEY


async def require_administrator(
    request: Request,
    authorization: str | None = Header(None),
) -> None:
    """Require a verified admin credential and the administrator role.

    A missing or invalid credential is 401. The gateway chat key, a header
    for another tenant, or a principal below administrator is 403.
    """
    from anonreq.middleware.rbac import Role, require_role

    await accept_gateway_or_admin_key(request, authorization)
    await require_role(Role.ADMINISTRATOR)(request)
