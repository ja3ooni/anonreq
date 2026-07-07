"""DLP pipeline stages for inbound and outbound enforcement."""
from __future__ import annotations

from typing import Any

from anonreq.exceptions import OutboundDLPError, PipelineBlockedError
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage


class InboundDLPStage(PipelineStage):
    """Inbound DLP stage that inspects request text before provider forwarding.

    Uses DLPEngine.inspect_request() to detect violations. If DLP is
    configured but unavailable, fails closed.
    """

    def __init__(self, app_state: Any | None = None) -> None:
        super().__init__("InboundDLPStage")
        self._app_state = app_state

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        dlp_engine = getattr(self._app_state, "dlp_engine", None) if self._app_state else None
        if dlp_engine is None:
            return ctx

        result = await dlp_engine.inspect_request(ctx)
        ctx.dlp_result = result
        if result.is_blocked:
            ctx.fail_secure(PipelineBlockedError(
                detail="Request blocked by DLP policy",
                request_id=ctx.request_id,
            ))
        return ctx


class OutboundDLPStage(PipelineStage):
    """Outbound DLP stage that inspects provider response before client delivery.

    Uses DLPEngine.inspect() to check response text. Fails closed on
    blocked outbound content.
    """

    def __init__(self, app_state: Any | None = None) -> None:
        super().__init__("OutboundDLPStage")
        self._app_state = app_state

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        dlp_engine = getattr(self._app_state, "dlp_engine", None) if self._app_state else None
        if dlp_engine is None:
            return ctx

        text = self._extract_response_text(ctx)
        if not text:
            return ctx

        result = await dlp_engine.inspect(text, ctx.tenant_id)
        ctx.outbound_dlp_result = result
        if result.is_blocked:
            ctx.fail_secure(OutboundDLPError(
                detail="Outbound DLP blocked response",
                request_id=ctx.request_id,
            ))
        return ctx

    def _extract_response_text(self, ctx: ProcessingContext) -> str:
        if not ctx.provider_response:
            return ""
        choices = ctx.provider_response.get("choices", [])
        texts: list[str] = []
        for choice in choices:
            msg = choice.get("message", {})
            content = msg.get("content", "")
            if content:
                texts.append(content)
        return "\n".join(texts)
