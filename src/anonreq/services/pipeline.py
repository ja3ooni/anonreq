from __future__ import annotations

from typing import Any

from anonreq.exceptions import OutboundDLPError, PipelineBlockedError
from anonreq.models.dlp import DLPAction
from anonreq.models.processing_context import ProcessingContext


class PipelineService:
    def __init__(self, dlp_engine: Any = None, pdp2_service: Any = None) -> None:
        self._dlp_engine = dlp_engine
        self._pdp2 = pdp2_service

    async def _run_inbound_dlp(self, ctx: ProcessingContext) -> None:
        if self._dlp_engine is None:
            return
        result = await self._dlp_engine.inspect_request(ctx)
        ctx.dlp_result = result
        if result.is_blocked:
            ctx.fail_secure(PipelineBlockedError(
                detail="Request blocked by DLP policy",
                request_id=ctx.request_id,
            ))

    async def _run_outbound_dlp(self, ctx: ProcessingContext) -> None:
        if self._dlp_engine is None:
            return
        text = self._extract_response_text(ctx)
        if not text:
            return
        result = await self._dlp_engine.inspect(text, ctx.tenant_id)
        ctx.outbound_dlp_result = result
        if result.is_blocked:
            ctx.fail_secure(OutboundDLPError(
                detail="Outbound DLP blocked response",
                request_id=ctx.request_id,
            ))

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

    async def _run_threat_detection(self, ctx: ProcessingContext) -> None:
        pass

    async def _run_extraction(self, ctx: ProcessingContext) -> None:
        pass

    async def _run_detection(self, ctx: ProcessingContext) -> None:
        pass

    async def _run_classification(self, ctx: ProcessingContext) -> None:
        pass

    async def _run_anonymization(self, ctx: ProcessingContext) -> None:
        pass

    async def _run_forward(self, ctx: ProcessingContext) -> None:
        pass

    async def _run_restoration(self, ctx: ProcessingContext) -> None:
        pass

    async def run(self, ctx: ProcessingContext) -> ProcessingContext:
        stages = [
            ("threat_detection", self._run_threat_detection),
            ("extraction", self._run_extraction),
            ("detection", self._run_detection),
            ("classification", self._run_classification),
            ("dlp_inbound", self._run_inbound_dlp),
        ]
        for _name, stage in stages:
            if ctx.has_errors():
                return ctx
            await stage(ctx)

        if not ctx.has_errors() and self._pdp2 is not None:
            decision = await self._pdp2.evaluate(ctx)
            ctx.policy_decision = decision
            if decision.action in ("BLOCK", "QUARANTINE"):
                ctx.fail_secure(PipelineBlockedError(
                    detail="Request blocked by policy",
                    request_id=ctx.request_id,
                ))

        post_pdp_stages = [
            ("anonymization", self._run_anonymization),
            ("forward", self._run_forward),
            ("restoration", self._run_restoration),
            ("dlp_outbound", self._run_outbound_dlp),
        ]
        for _name, stage in post_pdp_stages:
            if ctx.has_errors():
                return ctx
            await stage(ctx)

        return ctx
