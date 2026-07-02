from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from anonreq.firewall.engine import FirewallRuleEngine
from anonreq.firewall.gates import OutboundFirewallGate
from anonreq.firewall.ml_model import MLModel
from anonreq.firewall.models import SeverityActionMapping
from anonreq.models.processing_context import ProcessingContext

_SKIP_PATHS = {"/health", "/health/ready", "/metrics", "/"}


class OutboundFirewallMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        engine: FirewallRuleEngine | None = None,
        severity_mapping: SeverityActionMapping | None = None,
        ml_model: MLModel | None = None,
    ) -> None:
        super().__init__(app)
        self._gate = (
            OutboundFirewallGate(
                engine,
                severity_mapping or SeverityActionMapping(),
                ml_model=ml_model,
            )
            if engine
            else None
        )

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path in _SKIP_PATHS or not request.url.path.startswith("/v1/"):
            return await call_next(request)

        if self._gate is None:
            return await call_next(request)

        response = await call_next(request)

        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk

        import json

        body_str = body_bytes.decode("utf-8", errors="replace")
        try:
            body_data: dict[str, Any] = json.loads(body_str)
        except (json.JSONDecodeError, ValueError):
            body_data = {}

        text = ""
        choices = body_data.get("choices", [])
        for choice in choices:
            msg = choice.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str):
                text += content + "\n"

        ctx = ProcessingContext(
            request_id=getattr(request.state, "request_id", "unknown"),
            tenant_id="default",
        )

        pre_results = await self._gate.check_pre_restore(text, ctx)
        if any(r.action.value == "BLOCK" for r in pre_results):
            result = pre_results[0]
            self._gate._emit_audit(result, ctx)
            status, body = self._gate._get_block_response(result)
            return JSONResponse(status_code=status, content=body)

        post_results = await self._gate.check_post_restore(text, ctx)
        if any(r.action.value == "BLOCK" for r in post_results):
            result = post_results[0]
            self._gate._emit_audit(result, ctx)
            status, body = self._gate._get_block_response(result)
            return JSONResponse(status_code=status, content=body)

        from starlette.responses import Response as StarletteResponse

        return StarletteResponse(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
