"""PipelineContentDispatcher — adapts Proxy dispatch() contract to PipelineManager.

The reverse proxy (ReverseProxy) and transparent proxy (TransparentProxy) both
call ``content_dispatcher.dispatch(content_type, body, ctx)`` expecting bytes
in and bytes out.  PipelineManager only has ``run(ctx)`` which takes a
``ProcessingContext``.

This adapter bridges the two contracts: it parses the request body, builds a
``ProcessingContext``, runs the pipeline, and returns the response bytes.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import structlog

from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.extraction import TextExtractor
from anonreq.pipeline.manager import PipelineManager

log = structlog.get_logger(__name__)

FAIL_CLOSED_ERROR = json.dumps(
    {
        "error": {
            "message": "Request blocked by AnonReq security gateway",
            "type": "fail_closed",
        }
    }
).encode("utf-8")

UNSUPPORTED_MEDIA_TYPE_ERROR = json.dumps(
    {
        "error": {
            "message": "Unsupported Content-Type",
            "type": "unsupported_media_type",
        }
    }
).encode("utf-8")


class PipelineContentDispatcher:
    """Adapts the dispatch(content_type, body, ctx) contract to PipelineManager.run(ctx).

    Usage::

        dispatcher = PipelineContentDispatcher(pipeline_manager, app_state=app.state)
        ctx = {"path": "/v1/chat/completions"}
        result = await dispatcher.dispatch("application/json", body, ctx=ctx)
    """

    def __init__(
        self,
        pipeline_manager: PipelineManager,
        app_state: Any | None = None,
    ) -> None:
        self._pipeline = pipeline_manager
        self._app_state = app_state

    async def dispatch(self, content_type: str, body: bytes, ctx: dict | None = None) -> bytes:
        if not content_type.startswith("application/json") or not body:
            return UNSUPPORTED_MEDIA_TYPE_ERROR

        try:
            body_dict = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return FAIL_CLOSED_ERROR

        if not isinstance(body_dict, dict):
            return FAIL_CLOSED_ERROR

        ctx = ctx or {}
        request_id = ctx.get("request_id", uuid4().hex)
        tenant_id = ctx.get("tenant_id", "default")

        proc_ctx = ProcessingContext(
            request_id=request_id,
            tenant_id=tenant_id,
            context_id=uuid4().hex,
        )
        proc_ctx.original_request = body_dict
        proc_ctx.text_nodes = TextExtractor.extract(body_dict)

        if self._app_state is not None:
            locale_header = getattr(self._app_state, "locale_header", None)
            if locale_header:
                proc_ctx.locale_header = locale_header

        proc_ctx = await self._pipeline.run(proc_ctx)

        if proc_ctx.has_errors():
            return FAIL_CLOSED_ERROR

        if proc_ctx.restored_response is not None:
            try:
                return json.dumps(proc_ctx.restored_response, default=str).encode("utf-8")
            except (TypeError, ValueError):
                return FAIL_CLOSED_ERROR

        if proc_ctx.provider_response is not None:
            try:
                return json.dumps(proc_ctx.provider_response, default=str).encode("utf-8")
            except (TypeError, ValueError):
                return FAIL_CLOSED_ERROR

        return FAIL_CLOSED_ERROR
