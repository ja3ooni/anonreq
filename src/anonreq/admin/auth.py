"""Admin authentication for OIDC-backed identity verification."""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import Header, HTTPException, Request

from anonreq.auth.oidc import OIDCVerificationError, build_oidc_verifier
from anonreq.config import settings
from anonreq.services.tenant_scope import concrete_request_tenant, narrow_wildcard_principal
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
        request.state.oidc_principal = _api_key_principal(request, "admin")
        return True

    raise HTTPException(
        status_code=401,
        detail="Admin API not configured",
    )


def _api_key_principal(request: Request, principal_id: str) -> dict[str, str]:
    """Administrator principal bound to this request's tenant.

    The tenant comes from the validated request state or
    ``X-AnonReq-Tenant-ID``. It is never ``"*"``.
    """
    return {
        "principal_id": principal_id,
        "role": settings.ADMIN_ROLE,
        "tenant_id": concrete_request_tenant(request) or "",
    }


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return token


def _token_matches(token: str, expected: str | None) -> bool:
    if not expected:
        return False
    return hmac.compare_digest(token, expected)


async def accept_gateway_or_admin_key(
    request: Request,
    authorization: str | None = Header(None),
) -> None:
    """Accept the legacy admin API key for administrator routes.

    The admin key attaches an administrator role principal scoped to
    ``X-AnonReq-Tenant-ID``. The gateway (client) key is a known credential
    but is not an administrator: it gets no role principal and these routes
    reject it with 403. A missing or unknown key is 401. When a principal
    with a role is already on the request (tests or an upstream OIDC layer),
    the key is not checked again and a wildcard tenant is narrowed.
    """
    existing = getattr(request.state, "role_principal", None)
    if isinstance(existing, dict) and existing.get("role"):
        narrow_wildcard_principal(request)
        return

    token = _bearer_token(authorization)
    admin_key_ok = not _oidc_configured() and _token_matches(token, settings.ADMIN_API_KEY)
    if admin_key_ok:
        principal = _api_key_principal(request, "admin")
        request.state.oidc_principal = principal
        request.state.role_principal = dict(principal)
        return
    if _token_matches(token, settings.API_KEY):
        raise HTTPException(
            status_code=403,
            detail="Gateway API key cannot access admin routes",
        )
    if _oidc_configured():
        await verify_admin_api_key(request, authorization)
        if getattr(request.state, "role_principal", None) is None:
            oidc_principal = getattr(request.state, "oidc_principal", None)
            if isinstance(oidc_principal, dict):
                request.state.role_principal = dict(oidc_principal)
        narrow_wildcard_principal(request)
        return
    raise HTTPException(status_code=401, detail="Invalid API key")


def get_admin_api_key() -> str | None:
    """Return the configured legacy admin API key, if any."""
    return settings.ADMIN_API_KEY


async def require_administrator(
    request: Request,
    authorization: str | None = Header(None),
) -> None:
    """Require a valid admin credential and the administrator role.

    Checks the feature-independent admin dependency used by policy and
    provider routes (``verify_admin_api_key`` plus RBAC). A missing or
    invalid credential is 401. A known principal below administrator is 403.
    """
    from anonreq.middleware.rbac import Role, require_role

    await accept_gateway_or_admin_key(request, authorization)
    await require_role(Role.ADMINISTRATOR)(request)
