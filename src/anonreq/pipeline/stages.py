"""Additional pipeline stages introduced after the core phase."""

from __future__ import annotations

from typing import Any

from anonreq.exceptions import PipelineAbortError
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiationError, LocaleNegotiator
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


class SensitivityClassificationStage(PipelineStage):
    """Sensitivity-level classification stage (Phase 12)."""

    def __init__(self, service: Any = None) -> None:
        super().__init__("SensitivityClassificationStage")
        from anonreq.services.classification import ClassificationService
        self._service = service or ClassificationService()

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        entity_types = list(set(d["entity_type"] for d in (ctx.detections or [])))
        result = await self._service.classify(
            entity_types=entity_types,
            client_level=ctx.client_classification,
        )
        ctx.classification_result_v2 = result  # Phase 12 result field
        ctx.audit_metadata["classification_level"] = result.highest.name
        if result.highest_entity:
            ctx.audit_metadata["highest_entity"] = result.highest_entity

        # If it says block, fail-secure!
        if result.handling_action == "block":
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=451,
                    message="Request blocked due to data classification policy",
                    request_id=ctx.request_id,
                )
            )
        return ctx


class PolicyEnforcementStage(PipelineStage):
    """Integrates PDP/PEP policy enforcement into the pipeline (Phase 12)."""

    def __init__(self, app_state: Any = None) -> None:
        super().__init__("PolicyEnforcementStage")
        self._app_state = app_state

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        pdp = getattr(self._app_state, "pdp", None) if self._app_state else None
        pep = getattr(self._app_state, "pep", None) if self._app_state else None

        if pdp is None or pep is None:
            # Skip if not configured (e.g. in basic unit tests)
            return ctx

        # Inject classification_result representation for legacy check compatibility
        if ctx.classification_result_v2:
            ctx.classification_result = {
                "classification_level": ctx.classification_result_v2.highest.name,
                "highest_entity": ctx.classification_result_v2.highest_entity or "",
            }

        decision = await pdp.evaluate_all(ctx)
        ctx.policy_decision = decision

        result = await pep.enforce(decision, ctx)
        ctx.policy_enforcement = result

        if not result.should_forward:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=result.status_code or 403,
                    message=result.body.get("reason", "Request blocked by policy") if result.body else "Request blocked by policy",  # noqa: E501
                    request_id=ctx.request_id,
                )
            )
        return ctx
