"""Additional pipeline stages introduced after the core phase."""

from __future__ import annotations

from anonreq.exceptions import PipelineAbortError
from anonreq.locale.negotiator import LocaleNegotiationError, LocaleNegotiator
from anonreq.locale.merger import RecognizerMerger
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage


class LocaleNegotiationStage(PipelineStage):
    """Resolve locale header and prepare merged recognizer configuration."""

    def __init__(
        self,
        negotiator: LocaleNegotiator,
        merger: RecognizerMerger,
    ) -> None:
        super().__init__("LocaleNegotiationStage")
        self._negotiator = negotiator
        self._merger = merger

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        try:
            bundles, parse_result = self._negotiator.negotiate(ctx.locale_header)
            ctx.locale_bundles = bundles
            ctx.merged_recognizers = self._merger.merge(bundles)

            if not ctx.locale_header:
                ctx.audit_metadata["locale"] = "universal"
            else:
                ctx.audit_metadata["locale"] = ",".join(bundle.code for bundle in bundles)
            if parse_result.was_fallback or parse_result.dropped_codes:
                ctx.audit_metadata["negotiation_fallback"] = True
        except LocaleNegotiationError as exc:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=exc.status_code,
                    message=str(exc),
                    request_id=ctx.request_id,
                )
            )
        return ctx
