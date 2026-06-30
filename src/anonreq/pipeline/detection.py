"""DetectionStage — runs regex + Presidio NER + span arbitration.

Per D-38 through D-41 and D-50:
- Runs RegexDetector on each text node's value (deterministic patterns)
- Runs PresidioClient.analyze_text_nodes() for NER detection
- Merges both result sets via SpanArbiter (regex wins on exact overlap)
- Applies ExclusionList to suppress false positives
- On any error: ctx.fail_secure() per D-50
"""

from __future__ import annotations

from typing import Any

import structlog
from structlog import get_logger

from anonreq.exceptions import PipelineAbortError
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.base import PipelineStage
from anonreq.pipeline.extraction import TextExtractor

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
    ) -> None:
        """Initialise with detection dependencies.

        Args:
            regex_detector: ``RegexDetector`` instance.
            presidio_client: ``PresidioClient`` for NER analysis.
            span_arbiter: ``SpanArbiter`` for merge/overlap resolution.
            exclusion_list: ``ExclusionList`` for false-positive suppression.
        """
        super().__init__("DetectionStage")
        self._regex_detector = regex_detector
        self._presidio_client = presidio_client
        self._span_arbiter = span_arbiter
        self._exclusion_list = exclusion_list

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
            # Run Presidio NER across all nodes concurrently
            ner_results_list = await self._presidio_client.analyze_text_nodes(
                ctx.text_nodes,
            )

            all_detections: list[dict[str, Any]] = []

            for i, node in enumerate(ctx.text_nodes):
                node_value = node.get("value", "")

                # Run regex detection on this node
                regex_results = self._regex_detector.detect(node_value)

                # Get NER results for this node
                ner_results = ner_results_list[i] if i < len(ner_results_list) else []

                # Merge via SpanArbiter
                merged = self._span_arbiter.merge(regex_results, ner_results)

                # Apply exclusion list
                final = self._exclusion_list.filter_detections(merged, node_value)

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

        except PipelineAbortError:
            raise
        except Exception as exc:
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=500,
                    message="Detection stage failed",
                    request_id=ctx.request_id,
                )
            )

        return ctx
