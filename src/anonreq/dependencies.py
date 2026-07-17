"""FastAPI dependency injection for authentication and request context.

Provides:
- ``verify_api_key``: Extracts and validates the Bearer token from the
  Authorization header against the configured API key.
- ``get_request_context``: Creates or retrieves a RequestContext from
  ``request.state``, binding request_id to structlog contextvars.
- ``auth_context``: Composite dependency that combines auth validation
  and context population — the single dependency to use on protected routes.

Per AUTH-MINIMAL-01, D-01, D-11, D-12:
- HTTPBearer auto_error=True ensures missing/invalid headers raise 401
  immediately, before any route handler runs.
- Invalid tokens raise ``AuthenticationError`` (not raw ``HTTPException``)
  so the global exception handler formats the response in the OpenAI-
  compatible envelope per RESEARCH Pitfall 3.
- RequestContext uses request.state populated by the middleware in main.py
  (request_id set before auth runs).
"""

import hmac

import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from anonreq.config import settings
from anonreq.exceptions import AuthenticationError
from anonreq.models.request_context import RequestContext

security = HTTPBearer(auto_error=True)
"""FastAPI HTTPBearer security scheme.

``auto_error=True`` raises ``HTTPException(401)`` when:
- The ``Authorization`` header is missing.
- The header uses a scheme other than ``Bearer``.

This ensures the fail-secure invariant: no request without a Bearer
token reaches any route handler or validation logic.
"""


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Extract and validate the Bearer token against the configured API key.

    Dependency chain:
    1. ``HTTPBearer(auto_error=True)`` extracts the credentials from the
       ``Authorization`` header. If missing or not using ``Bearer`` scheme,
       it raises ``HTTPException(401)`` immediately.
    2. This function compares the extracted token against
       ``settings.API_KEY``.
    3. On mismatch: raises ``AuthenticationError`` (caught by the global
       exception handler, which formats it in the OpenAI-compatible
       envelope with type ``authentication_error``).

    Args:
        credentials: The HTTP Bearer credentials extracted by FastAPI.

    Returns:
        The authenticated token string (a valid API key).

    Raises:
        AuthenticationError: If the token does not match the configured
            API key.
    """
    token = credentials.credentials
    if not hmac.compare_digest(token, settings.API_KEY or ""):
        raise AuthenticationError()
    return token


async def get_request_context(request: Request) -> RequestContext:
    """Create or retrieve the RequestContext for the current request.

    If the middleware (in main.py) has already set ``request.state.context``
    (which it does for every request), this function returns it and binds
    the request_id to structlog contextvars for log correlation.

    If called outside the middleware chain (e.g., in tests), it creates
    a new ``RequestContext()`` with a fresh request_id.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The RequestContext for the current request.
    """
    if not hasattr(request.state, "context"):
        request.state.context = RequestContext()

    ctx: RequestContext = request.state.context
    structlog.contextvars.bind_contextvars(request_id=ctx.request_id)
    return ctx


async def auth_context(
    _credentials: str = Depends(verify_api_key),
    ctx: RequestContext = Depends(get_request_context),
) -> RequestContext:
    """Composite dependency: validates auth AND populates request context.

    This is the single dependency to use on protected routes. It:
    1. Validates the Bearer token via ``verify_api_key``.
    2. Populates and returns the RequestContext via ``get_request_context``.

    Usage in route handlers::

        @router.get("/health")
        async def health(ctx: RequestContext = Depends(auth_context)):
            ...

    This keeps route handler signatures clean — one ``Depends(auth_context)``
    provides both authentication and context.

    Args:
        credentials: The validated API key (from ``verify_api_key``).
        ctx: The RequestContext for this request.

    Returns:
        The populated RequestContext.
    """
    return ctx
