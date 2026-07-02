"""DetectionStage — runs regex + Presidio NER + span arbitration.

Per D-38 through D-41 and D-50:
- Runs RegexDetector on each text node's value (deterministic patterns)
- Runs PresidioClient.analyze_text_nodes() for NER detection
- Merges both result sets via SpanArbiter (regex wins on exact overlap)
- Applies ExclusionList to suppress false positives
- On any error: ctx.fail_secure() per D-50

Hot-reload integration (D-152, D-154):
- DetectionStage accepts an optional AtomicConfigRegistry reference
- During each execute(), custom recognizer patterns from the registry
  are merged with locale-based patterns for detection
- Custom patterns are checked on every detection call (no notification
  channel needed for MVP)

Instrumentation (D-160, D-161):
- Records ``detection_latency_ms`` histogram after detection completes
- Increments ``entities_detected`` counter per entity type and locale
- Increments ``fail_secure_events_total`` on fail-secure path
"""

from __future__ import annotations

import inspect
import time
from typing import TYPE_CHECKING, Any

import structlog
from structlog import get_logger

from anonreq.exceptions import PipelineAbortError
from anonreq.locale.checksum import ChecksumValidatorRegistry, validate_detection
from anonreq.locale.bundle import RecognizerTier
from anonreq.models.processing_context import ProcessingContext
from anonreq.monitoring.metrics import detection_latency, entities_detected, fail_secure_events
from anonreq.pipeline.base import PipelineStage
from anonreq.pipeline.extraction import TextExtractor

if TYPE_CHECKING:
    from anonreq.admin.config import AtomicConfigRegistry

logger = get_logger("anonreq.pipeline.detection")


class DetectionStage(PipelineStage):
    """Runs regex and NER PII detection against request text nodes.

    Processes each text node independently:
    1. Runs RegexDetector on the node's value
    2. Runs Presidio NER (via analyze_text_nodes) concurrently across all nodes
    3. Merges regex + NER results per node via SpanArbiter
    4. Filters through ExclusionList per node
    5. Collects all detections into ``ctx.detections``
    """

    def __init__(
        self,
        regex_detector: Any,
        presidio_client: Any,
        span_arbiter: Any,
        exclusion_list: Any,
        checksum_registry: ChecksumValidatorRegistry | None = None,
        config_registry: AtomicConfigRegistry | None = None,
    ) -> None:
        """Initialise with detection dependencies.

        Args:
            regex_detector: ``RegexDetector`` instance.
            presidio_client: ``PresidioClient`` for NER analysis.
            span_arbiter: ``SpanArbiter`` for merge/overlap resolution.
            exclusion_list: ``ExclusionList`` for false-positive suppression.
            checksum_registry: Optional registry for checksum validation.
            config_registry: Optional ``AtomicConfigRegistry`` for hot-reloaded
                custom recognizer patterns (D-152, D-154).
        """
        super().__init__("DetectionStage")
        self._regex_detector = regex_detector
        self._presidio_client = presidio_client
        self._span_arbiter = span_arbiter
        self._exclusion_list = exclusion_list
        self._checksum_registry = checksum_registry or ChecksumValidatorRegistry()
        self._config_registry = config_registry

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        """Detect PII in request text nodes.

        Skips detection if classification action is PASS or BLOCK
        (those requests do not need analysis).

        Returns:
            The mutated ``ProcessingContext`` with ``ctx.detections`` set.
        """
        # Skip if classification says PASS or BLOCK
        if ctx.classification_result:
            action = ctx.classification_result.get("action")
            if action in ("PASS", "BLOCK"):
                return ctx

        # Ensure text nodes are extracted
        if ctx.text_nodes is None:
            ctx.text_nodes = TextExtractor.extract(ctx.original_request)

        if not ctx.text_nodes:
            ctx.detections = []
            return ctx

        try:
            merged_recognizers = getattr(ctx, "merged_recognizers", None)
            entity_configs = (
                list(merged_recognizers.entity_configs.values())
                if merged_recognizers is not None
                else []
            )
            regex_patterns = self._regex_detector.patterns_from_entity_configs(entity_configs)

            # Hot-reload integration: merge custom recognizer patterns from
            # AtomicConfigRegistry (D-152). These are checked on every detection
            # call — no notification channel needed for MVP.
            if self._config_registry is not None:
                from anonreq.detection.provider import get_custom_recognizer_patterns as get_custom

                custom = get_custom(self._config_registry)
                if custom:
                    regex_patterns = dict(regex_patterns or {})
                    regex_patterns.update(custom)

            ner_entities = sorted({
                entity
                for config in entity_configs
                if config.tier in (RecognizerTier.NER, RecognizerTier.BOTH)
                for entity in config.presidio_entities
            }) or None
            score_threshold = min(
                [config.confidence_threshold for config in entity_configs],
                default=0.7,
            )

            # Run Presidio NER across all nodes concurrently
            ner_call = self._presidio_client.analyze_text_nodes(
                ctx.text_nodes,
                entities=ner_entities,
                score_threshold=score_threshold,
            )
            ner_results_list = await ner_call if inspect.isawaitable(ner_call) else ner_call

            all_detections: list[dict[str, Any]] = []

            for i, node in enumerate(ctx.text_nodes):
                node_value = node.get("value", "")

                # Run regex detection on this node
                regex_results = self._regex_detector.detect(
                    node_value,
                    extra_patterns=regex_patterns,
                )

                # Get NER results for this node
                ner_results = ner_results_list[i] if i < len(ner_results_list) else []

                # Merge via SpanArbiter
                merged = self._span_arbiter.merge(regex_results, ner_results)

                # Apply exclusion list
                final = self._exclusion_list.filter_detections(merged, node_value)
                final = [
                    validated
                    for detection in final
                    if (validated := validate_detection(
                        detection,
                        self._checksum_registry,
                        node_value,
                    )) is not None
                ]

                # Tag each detection with its node index for tokenization
                for d in final:
                    d["node_index"] = i

                all_detections.extend(final)

            ctx.detections = all_detections

            # Log entity counts grouped by type
            entity_counts: dict[str, int] = {}
            for d in all_detections:
                etype = d.get("entity_type", "UNKNOWN")
                entity_counts[etype] = entity_counts.get(etype, 0) + 1

            logger.info(
                "detection.complete",
                stage=self.name,
                request_id=ctx.request_id,
                total_detections=len(all_detections),
                entity_counts=entity_counts,
            )

            # Record detection latency (D-160)
            if ctx.request_receipt_time is not None:
                elapsed_ms = (time.monotonic() - ctx.request_receipt_time) * 1000.0
                detection_latency.observe(elapsed_ms)

            # Increment entities_detected per entity type and locale (D-161)
            for d in all_detections:
                entity_type = d.get("entity_type", "UNKNOWN")
                locale = d.get("locale", "unknown")
                entities_detected.labels(
                    entity_type=entity_type,
                    locale=locale,
                ).inc()

        except PipelineAbortError:
            # Count fail-secure events from detection errors (D-161)
            fail_secure_events.labels(failure_type="detection_error").inc()
            raise
        except Exception as exc:
            fail_secure_events.labels(failure_type="detection_error").inc()
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=500,
                    message="Detection stage failed",
                    request_id=ctx.request_id,
                )
            )

        return ctx
