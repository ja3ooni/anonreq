from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from anonreq.firewall.engine import FirewallRuleEngine
from anonreq.firewall.gates import InboundFirewallGate
from anonreq.firewall.ml_model import MLModel
from anonreq.models.processing_context import ProcessingContext

_SKIP_PATHS = {"/health", "/health/ready", "/metrics", "/", "/v1/config/rules"}


class InboundFirewallMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        engine: FirewallRuleEngine | None = None,
        ml_model: MLModel | None = None,
    ) -> None:
        super().__init__(app)
        self._gate = InboundFirewallGate(engine) if engine else None
        self._ml_model = ml_model

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path in _SKIP_PATHS or not request.url.path.startswith("/v1/"):
            return await call_next(request)

        if self._gate is None:
            return await call_next(request)

        body_bytes = await request.body()
        request._body = body_bytes

        import json

        body_str = body_bytes.decode("utf-8", errors="replace")
        try:
            body_data: dict[str, Any] = json.loads(body_str)
        except (json.JSONDecodeError, ValueError):
            body_data = {}

        text = ""
        messages = body_data.get("messages", [])
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                text += content + "\n"

        ctx = ProcessingContext(
            request_id=getattr(request.state, "request_id", "unknown"),
            tenant_id="default",
        )

        pre_results = await self._gate.check_pre_anon(text, ctx)
        if self._gate._should_block(pre_results):
            result = pre_results[0]
            self._gate._emit_audit(result, ctx)
            status, body = self._gate._get_block_response(result)
            return JSONResponse(status_code=status, content=body)

        response = await call_next(request)

        post_results = await self._gate.check_post_anon(text, ctx)
        if self._gate._should_block(post_results):
            result = post_results[0]
            self._gate._emit_audit(result, ctx)
            status, body = self._gate._get_block_response(result)
            return JSONResponse(status_code=status, content=body)

        return response
