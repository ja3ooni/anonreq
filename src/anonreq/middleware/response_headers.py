"""ClassificationResponseMiddleware — conditionally returns classification result headers (Plan 12-03)."""

from __future__ import annotations

import json
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class ClassificationResponseMiddleware(BaseHTTPMiddleware):
    """Middleware that injects the X-AnonReq-Classification-Result header.

    Only injects the header if:
    1. X-AnonReq-Return-Classification header is exactly "true".
    2. ProcessingContext is available on request.state.ctx.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)

        # Skip non-API paths
        if not request.url.path.startswith("/v1/"):
            return response

        return_classification = request.headers.get("X-AnonReq-Return-Classification")
        if return_classification == "true":
            ctx = getattr(request.state, "ctx", None)
            if ctx and getattr(ctx, "classification_result_v2", None):
                res = ctx.classification_result_v2
                val = {
                    "highest": res.highest.name,
                    "labels": res.labels,
                    "client_override": res.client_override,
                }
                response.headers["X-AnonReq-Classification-Result"] = json.dumps(val)

        return response
