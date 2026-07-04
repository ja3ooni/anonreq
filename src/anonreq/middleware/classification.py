"""ClassificationMiddleware — parses X-AnonReq-Classification header, blocks HIGHLY_RESTRICTED.

Integration with pipeline:
- BEFORE pipeline: parses X-AnonReq-Classification header, stores on request.state
- AFTER pipeline (in route handler): classification headers added to response

Per-level handling (Plan 12-02):
- HIGHLY_RESTRICTED → blocked at middleware with HTTP 451
- Lower levels → pass through, handled by pipeline/route handler
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from anonreq.models.classification import ClassificationLevel
from anonreq.services.classification import ClassificationService

_SKIP_PATHS = {"/health", "/health/ready", "/metrics", "/"}


class ClassificationMiddleware(BaseHTTPMiddleware):
    """Parses X-AnonReq-Classification and applies per-level handling policy.

    On request:
    1. Skips non-API paths (health, metrics, etc.)
    2. Parses ``X-AnonReq-Classification`` header
    3. Stores parsed ``ClassificationLevel`` on ``request.state.client_classification``
    4. If client asserts HIGHLY_RESTRICTED → returns HTTP 451 immediately

    On response:
    - Classification response headers are set by the route handler from
      the ``ProcessingContext`` (see chat.py)
    """

    def __init__(
        self,
        app: ASGIApp,
        service: ClassificationService | None = None,
    ) -> None:
        super().__init__(app)
        self._service = service or ClassificationService()

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path in _SKIP_PATHS or not request.url.path.startswith("/v1/"):
            return await call_next(request)

        client_header = request.headers.get("X-AnonReq-Classification")
        client_level = ClassificationService.parse_client_header(client_header)

        request.state.client_classification = client_level

        if client_level is not None and client_level >= ClassificationLevel.HIGHLY_RESTRICTED:
            body = {
                "error": {
                    "message": "Request blocked due to data classification policy",
                    "type": "classification_block",
                    "code": "highly_restricted",
                },
                "classification": {
                    "highest": "HIGHLY_RESTRICTED",
                    "labels": [],
                    "reason": "Request blocked due to data classification policy",
                },
            }
            return JSONResponse(
                status_code=451,
                content=body,
                headers={
                    "X-AnonReq-Classification": "HIGHLY_RESTRICTED",
                    "X-AnonReq-Blocked": "true",
                    "X-AnonReq-Highest-Entity": "",
                },
            )

        response = await call_next(request)

        return response
