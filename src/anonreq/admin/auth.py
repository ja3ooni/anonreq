"""Admin API key authentication middleware.

Per D-151:
- Admin API requires authentication via ANONREQ_ADMIN_API_KEY env var
- Separate from ANONREQ_API_KEY (gateway API key)
- If ANONREQ_ADMIN_API_KEY is unset, admin endpoints return 401
"""

from __future__ import annotations

from fastapi import Header, HTTPException

from anonreq.config import settings


async def verify_admin_api_key(
    authorization: str | None = Header(None),
) -> bool:
    """Verify the admin API key from the Authorization header.

    The admin API key is configured via the ANONREQ_ADMIN_API_KEY env var.
    If the env var is unset, all admin endpoints return 401.
    If the header is missing or the token doesn't match, return 401.

    Args:
        authorization: The Authorization header value
            (e.g. "Bearer <admin-key>").

    Returns:
        True if the key is valid.

    Raises:
        HTTPException: With 401 status if authentication fails.
    """
    if not settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Admin API not configured",
        )

    if authorization is None:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin API key",
        )

    return True


async def get_admin_api_key() -> str | None:
    """Return the configured admin API key or None.

    Returns:
        The admin API key string, or None if not configured.
    """
    return settings.ADMIN_API_KEY
