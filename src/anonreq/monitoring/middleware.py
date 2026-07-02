"""MetricsMiddleware — records request timing and increments request counters.

Per D-140 and D-141:
- Captures ``request.state.request_receipt_time`` (``time.monotonic()``)
  before the route handler executes.
- After the response is sent, increments ``requests_total`` with labels
  for ``endpoint``, ``status_code``, ``provider``, and ``classification``.
- Provider and classification values are read from ``request.state``,
  which pipeline stages populate during request processing.
- No PII or raw request content is ever passed to metric labels (AG-15).
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from anonreq.monitoring.metrics import requests_total


class MetricsMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that records request timing and increments counters.

    Sets ``request.state.request_receipt_time`` on every incoming request.
    On response, increments ``requests_total`` with endpoint, status code,
    provider, and classification labels.

    Uses ``BaseHTTPMiddleware`` for proper integration with FastAPI's
    routing and ``Request`` parameter injection.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process a request: record timing, call next, increment counter.

        Args:
            request: The incoming Starlette request.
            call_next: The next middleware or route handler.

        Returns:
            The response from the downstream handler.
        """
        # Record receipt time before processing
        request.state.request_receipt_time = time.monotonic()

        response: Response = await call_next(request)

        # Read labels from request state (set by pipeline stages)
        endpoint: str = request.url.path
        status_code: str = str(response.status_code)
        provider: str = getattr(request.state, "provider", "unknown")
        classification: str = getattr(request.state, "classification", "unknown")

        requests_total.labels(
            endpoint=endpoint,
            status_code=status_code,
            provider=provider,
            classification=classification,
        ).inc()

        return response
