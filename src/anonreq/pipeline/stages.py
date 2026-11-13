"""Additional pipeline stages introduced after the core phase."""

from __future__ import annotations

from typing import Any

from structlog import get_logger

from anonreq.exceptions import LocaleNerNotClearedError, PipelineAbortError
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiationError, LocaleNegotiator
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage

logger = get_logger("anonreq.pipeline.locale")

STRUCTURED_ONLY = "structured_only"


class LocaleNegotiationStage(PipelineStage):
    """Resolve locale header and prepare merged recognizer configuration."""

    def __init__(
        self,
        negotiator: LocaleNegotiator,
        merger: RecognizerMerger,
        allow_structured_only: bool = False,
    ) -> None:
        super().__init__("LocaleNegotiationStage")
        self._negotiator = negotiator
        self._merger = merger
        # ANONREQ_BG_STRUCTURED_ONLY. Off: structured-only locales (bg-BG)
        # are refused with 422, because names and addresses would pass.
        self._allow_structured_only = allow_structured_only

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
            # A bundle without NER (bg-BG) masks structured IDs only; names
            # and addresses pass. Make that visible in audit and headers.
            if any(
                getattr(bundle, "ner_coverage", None) == STRUCTURED_ONLY for bundle in bundles
            ):
                ctx.audit_metadata["ner_coverage"] = STRUCTURED_ONLY
                ctx.audit_metadata["bg_structured_only"] = self._allow_structured_only
                if not self._allow_structured_only:
                    logger.warning(
                        "locale.ner_not_cleared",
                        stage=self.name,
                        request_id=ctx.request_id,
                        locale=ctx.audit_metadata["locale"],
                    )
                    ctx.fail_secure(LocaleNerNotClearedError(request_id=ctx.request_id))
        except LocaleNegotiationError as exc:
            logger.warning(
                "locale.negotiation_failed",
                stage=self.name,
                request_id=ctx.request_id,
                error=type(exc).__name__,
            )
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=exc.status_code,
                    message="Locale negotiation failed",
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

        # If it says block, fail-secure (unless Germany demo overlay sets
        # CLASSIFICATION_DEFAULT_ACTION=ANONYMIZE and no explicit client override
        # was sent, so non-reversible secrets like API_KEY are permanently masked).
        from anonreq.config import settings as _settings

        default_action = (getattr(_settings, "CLASSIFICATION_DEFAULT_ACTION", None) or "").upper()
        if result.handling_action == "block" and (
            ctx.client_classification is not None or default_action != "ANONYMIZE"
        ):
            entity_types = list({d["entity_type"] for d in (ctx.detections or [])})
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=451,
                    message="Request blocked due to data classification policy",
                    request_id=ctx.request_id,
                    block_detail={
                        "classification": result.highest.name,
                        "entities_detected": entity_types,
                        "entity_count": len(ctx.detections or []),
                        "highest_entity": result.highest_entity,
                        "action": "BLOCK",
                    },
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

        # Merge sensitivity fields into classification_result without dropping
        # pipeline action / matched_rule_ids. Replacing the dict used to wipe
        # ``action``, so ForwardingGuard defaulted to PASS and ProviderStage
        # forwarded cleartext after tokenization had already run.
        if ctx.classification_result_v2:
            base = dict(ctx.classification_result or {})
            base["classification_level"] = ctx.classification_result_v2.highest.name
            base["highest_entity"] = ctx.classification_result_v2.highest_entity or ""
            ctx.classification_result = base

        decision = await pdp.evaluate_all(ctx)
        ctx.policy_decision = decision

        result = await pep.enforce(decision, ctx)
        ctx.policy_enforcement = result

        if not result.should_forward:
            entity_types = list({d["entity_type"] for d in (ctx.detections or [])})
            enforcement_body = result.body or {}
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=result.status_code or 403,
                    message=enforcement_body.get("reason", "Request blocked by policy"),
                    request_id=ctx.request_id,
                    block_detail={
                        "classification": (ctx.classification_result_v2.highest.name if ctx.classification_result_v2 else "UNKNOWN"),  # noqa: E501
                        "entities_detected": entity_types,
                        "entity_count": len(ctx.detections or []),
                        "triggered_rule": (decision.matched_rule_ids[0] if decision.matched_rule_ids else "unknown"),  # noqa: E501
                        "action": "BLOCK",
                        "decision_id": enforcement_body.get("decision_id"),
                        "error_type": enforcement_body.get("error_type"),
                    },
                )
            )
        return ctx
