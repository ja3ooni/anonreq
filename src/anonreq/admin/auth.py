"""Admin authentication for OIDC-backed identity verification."""

from __future__ import annotations

import hmac

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


def _get_oidc_verifier(request: Request):
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


async def get_admin_api_key() -> str | None:
    """Return the configured legacy admin API key, if any."""
    return settings.ADMIN_API_KEY
