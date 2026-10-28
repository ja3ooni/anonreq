"""Metadata-only HTTP access log.

Uvicorn's access logger records the raw request line, including the query
string, on a logger that does not pass through AnonReq's scrubbing filter.
Deployments run uvicorn with ``--no-access-log``. This middleware replaces
that line with method, route template, status, duration, and request_id.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from structlog import get_logger

logger = get_logger("anonreq.access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Emit one structured access event after each request."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        template = getattr(route, "path", None) or "unmatched"
        request_id = getattr(request.state, "request_id", None) or "unknown"
        logger.info(
            "http.access",
            method=request.method,
            route=str(template),
            status_code=response.status_code,
            duration_ms=int((time.perf_counter() - started) * 1000),
            request_id=str(request_id),
        )
        return response
