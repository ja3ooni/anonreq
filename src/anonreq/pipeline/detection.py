"""DetectionStage — runs regex + Presidio NER + span arbitration.

Per D-38 through D-41 and D-50:
- Runs RegexDetector on each text node's value (deterministic patterns)
- Runs PresidioClient.analyze_text_nodes() for NER detection, with the
  negotiated locale mapped to a Presidio language (``de-DE`` -> ``de``)
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

Phase 15 Financial Services Compliance — MNPI Integration:
- DetectionStage optionally accepts a list of MNPI recognizers
- MNPI recognizers run against each text node alongside regex and NER
- MNPI spans join the same SpanArbiter pass as every other detector

Phase 26 enterprise API-key and secret recognizers also join that pass.
Appending them after overlap resolution tokenizes one character range twice.
"""

from __future__ import annotations

import inspect
import re
import time
from typing import TYPE_CHECKING, Any

from structlog import get_logger

from anonreq.detection.presidio_client import PresidioUnsupportedLanguageError
from anonreq.detection.regex_patterns import IRREVERSIBLE_ENTITY_TYPES
from anonreq.exceptions import PipelineAbortError, PresidioLanguageUnsupportedError
from anonreq.locale.bundle import RecognizerTier
from anonreq.locale.checksum import ChecksumValidatorRegistry, validate_detection
from anonreq.locale.presidio_language import (
    DEFAULT_PRESIDIO_LANGUAGE,
    plan_presidio_languages,
)
from anonreq.models.processing_context import ProcessingContext
from anonreq.monitoring.metrics import (
    detection_latency,
    entities_detected,
    fail_secure_events,
    presidio_unsupported_locales,
)
from anonreq.pipeline.base import PipelineStage
from anonreq.pipeline.extraction import TextExtractor

if TYPE_CHECKING:
    from anonreq.admin.config import AtomicConfigRegistry
    from anonreq.detection.recognizers.mnpi import MNPIRecognizer

logger = get_logger("anonreq.pipeline.detection")

_PROTECTED_SOURCES = frozenset({"enterprise", "mnpi"})


def _exclusion_exempt(detection: dict[str, Any]) -> bool:
    """Return True when an exclusion must not drop this span.

    Enterprise secret detectors and MNPI recognizers stay masked even if
    their text matches an exclusion entry. A regex secret type that won
    an exact overlap (``API_KEY`` and the other irreversible types) is
    exempt for the same reason.
    """
    if detection.get("protected") or detection.get("source") in _PROTECTED_SOURCES:
        return True
    entity_type = str(detection.get("entity_type", ""))
    return entity_type in IRREVERSIBLE_ENTITY_TYPES or entity_type.startswith("MNPI_")


# Checksum failures on these types are still masked on format, at lower
# confidence, because a mistyped IBAN or tax ID is still personal data.
_MASK_ON_FORMAT = {
    "IBAN_DE": "IBAN_UNVERIFIED",
    "IBAN_CODE": "IBAN_UNVERIFIED",
    "TAX_ID_DE": "TAX_ID_DE_UNVERIFIED",
}
_UNVERIFIED_SCORE = 0.6


def _validate_or_downgrade(
    detection: dict[str, Any],
    registry: ChecksumValidatorRegistry,
    text: str,
) -> dict[str, Any] | None:
    """Validate a checksum; mask-on-format types are downgraded, not dropped."""
    validated = validate_detection(detection, registry, text)
    if validated is not None:
        return validated
    downgraded = _MASK_ON_FORMAT.get(str(detection.get("entity_type", "")))
    if downgraded is None:
        return None
    return {
        **detection,
        "entity_type": downgraded,
        "score": min(float(detection.get("score", 1.0)), _UNVERIFIED_SCORE),
    }


_PERSON_TYPES = frozenset({"PERSON", "PER"})
_WORD = re.compile(r"\S+")


def _trim_person_spans(spans: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    """Trim leading and trailing lowercase words from NER person spans.

    Names are capitalised. An English model run on German text returns
    spans such as "Anna prüfen"; the trailing verb is not part of the name
    and masking it breaks exact boundaries. Spans are only ever trimmed,
    never dropped: if no capitalised word remains (all-lowercase input such
    as "bitte anna müller anrufen") the original span is kept.
    """
    trimmed: list[dict[str, Any]] = []
    for span in spans:
        if str(span.get("entity_type", "")) not in _PERSON_TYPES:
            trimmed.append(span)
            continue
        start, end = int(span["start"]), int(span["end"])
        words = [
            (start + m.start(), start + m.end()) for m in _WORD.finditer(text[start:end])
        ]
        while words and not text[words[0][0]].isupper():
            words.pop(0)
        while words and not text[words[-1][0]].isupper():
            words.pop()
        if not words:
            trimmed.append(span)
            continue
        new_start, new_end = words[0][0], words[-1][1]
        while new_end > new_start and not text[new_end - 1].isalnum():
            new_end -= 1
        trimmed.append({**span, "start": new_start, "end": new_end})
    return trimmed


class DetectionStage(PipelineStage):
    """Runs regex and NER PII detection against request text nodes.

    Processes each text node independently:
    1. Runs RegexDetector on the node's value
    2. Runs Presidio NER (via analyze_text_nodes) concurrently across all nodes
    3. Runs MNPI and enterprise API-key/secret recognizers on the same node
    4. Merges every detector's spans in one SpanArbiter pass
    5. Filters through ExclusionList per node
    6. Collects all detections into ``ctx.detections``
    """

    def __init__(
        self,
        regex_detector: Any,
        presidio_client: Any,
        span_arbiter: Any,
        exclusion_list: Any,
        checksum_registry: ChecksumValidatorRegistry | None = None,
        config_registry: AtomicConfigRegistry | None = None,
        mnpi_recognizers: list[MNPIRecognizer] | None = None,
        enterprise_recognizers: dict[str, Any] | None = None,
        presidio_languages: tuple[str, ...] | list[str] | None = None,
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
            mnpi_recognizers: Optional list of ``MNPIRecognizer`` instances
                for MNPI detection (Phase 15, D-001).
            enterprise_recognizers: Optional dict of enabled enterprise
                recognizers (Phase 26, GUARD-01).
            presidio_languages: ISO 639-1 codes this deployment's analyzer
                supports (``ANONREQ_PRESIDIO_LANGUAGES``). Defaults to English.
        """
        super().__init__("DetectionStage")
        self._regex_detector = regex_detector
        self._presidio_client = presidio_client
        self._span_arbiter = span_arbiter
        self._exclusion_list = exclusion_list
        self._checksum_registry = checksum_registry or ChecksumValidatorRegistry()
        self._config_registry = config_registry
        self._mnpi_recognizers = mnpi_recognizers or []
        self._enterprise_recognizers = enterprise_recognizers or {}
        self._presidio_languages = tuple(presidio_languages or ("en",))

    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        """Detect PII in request text nodes.

        Skips detection if classification action is PASS or BLOCK
        (those requests do not need analysis).

        Returns:
            The mutated ``ProcessingContext`` with ``ctx.detections`` set.
        """
        # Skip only for BLOCK: detection and tokenization always run otherwise
        if ctx.classification_result:
            action = ctx.classification_result.get("action")
            if action == "BLOCK":
                return ctx

        # Ensure text nodes are extracted
        if ctx.text_nodes is None:
            ctx.text_nodes = TextExtractor.extract(ctx.original_request or {})

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
            # Every negotiated bundle is considered. Languages outside
            # ANONREQ_PRESIDIO_LANGUAGES are analyzed as English. A configured
            # language the sidecar rejects is not retried as English.
            plan = plan_presidio_languages(
                getattr(ctx, "locale_bundles", None),
                self._presidio_languages,
            )
            presidio_language = ",".join(plan.languages)
            for locale_code in plan.unsupported_locales:
                presidio_unsupported_locales.labels(locale=locale_code).inc()
                logger.warning(
                    "detection.presidio_locale_not_configured",
                    stage=self.name,
                    request_id=ctx.request_id,
                    locale=locale_code,
                    presidio_language=DEFAULT_PRESIDIO_LANGUAGE,
                    error_type="presidio_locale_not_configured",
                )

            # Run Presidio once per selected language and merge the spans.
            ner_results_list: list[list[dict[str, Any]]] = [
                [] for _ in ctx.text_nodes
            ]
            for language in plan.languages:
                ner_call = self._presidio_client.analyze_text_nodes(
                    ctx.text_nodes,
                    language=language,
                    entities=ner_entities,
                    score_threshold=score_threshold,
                )
                # iscoroutine, not isawaitable: MagicMock is awaitable and hangs.
                batch = await ner_call if inspect.iscoroutine(ner_call) else ner_call
                for index, hits in enumerate(batch):
                    if index < len(ner_results_list):
                        ner_results_list[index].extend(hits or [])

            all_detections: list[dict[str, Any]] = []
            irreversible_names = {
                config.name for config in entity_configs if not config.reversible
            } | set(IRREVERSIBLE_ENTITY_TYPES)

            for i, node in enumerate(ctx.text_nodes):
                node_value = node.get("value", "")

                # Run regex detection on this node
                regex_results = self._regex_detector.detect(
                    node_value,
                    extra_patterns=regex_patterns,
                )

                # Get NER results for this node
                ner_results = ner_results_list[i] if i < len(ner_results_list) else []
                ner_results = _trim_person_spans(ner_results, node_value)

                # Secret, API-key, and MNPI detectors contribute spans to the
                # same resolution as regex and NER. Resolving them afterwards
                # leaves overlapping ranges, and tokenization then replaces
                # the same characters twice.
                mnpi_results: list[dict[str, Any]] = []
                for recognizer in self._mnpi_recognizers:
                    mnpi_results.extend(recognizer.analyze(node_value))

                enterprise_results: list[dict[str, Any]] = []
                for name, recognizer in self._enterprise_recognizers.items():
                    error_type: str | None = None
                    try:
                        per_node = recognizer.analyze(node_value)
                    except Exception as exc:
                        # The exception text can contain the span that crashed
                        # the recognizer. Remember only the type, then log
                        # after this handler exits so the traceback is not active.
                        error_type = type(exc).__name__
                        per_node = []
                    if error_type is not None:
                        logger.warning(
                            "Enterprise recognizer failed",
                            recognizer_name=name,
                            node_index=i,
                            error_type=error_type,
                        )
                        fail_secure_events.labels(
                            tenant_id=ctx.tenant_id,
                            failure_type="detection_error",
                        ).inc()
                        ctx.fail_secure(
                            PipelineAbortError(
                                status_code=500,
                                message=f"Detection stage failed: {error_type}",
                                request_id=ctx.request_id,
                            )
                        )
                        return ctx
                    for detection in per_node:
                        detection.setdefault("source", "enterprise")
                    enterprise_results.extend(per_node)

                # Config-irreversible types are flagged before the merge so
                # the flag survives when an ordinary type wins the overlap.
                for results in (regex_results, ner_results):
                    for detection in results:
                        if str(detection.get("entity_type", "")) in irreversible_names:
                            detection["irreversible"] = True

                merged = self._span_arbiter.merge(
                    regex_results,
                    ner_results,
                    mnpi_results,
                    enterprise_results,
                )

                # Exclusions suppress false positives. Secret and MNPI spans
                # are exempt: an exclusion must not unmask them.
                exempt = [d for d in merged if _exclusion_exempt(d)]
                eligible = [d for d in merged if not _exclusion_exempt(d)]
                final = exempt + self._exclusion_list.filter_detections(eligible, node_value)
                final = [
                    validated
                    for detection in final
                    if (
                        validated := detection
                        if detection.get("protected")
                        else _validate_or_downgrade(
                            detection,
                            self._checksum_registry,
                            node_value,
                        )
                    )
                    is not None
                ]

                # Tag each detection with its node index for tokenization
                for d in final:
                    d["node_index"] = i
                    entity_type = str(d.get("entity_type", ""))
                    d["reversible"] = (
                        entity_type not in irreversible_names
                        and d.get("source") != "enterprise"
                        and not d.get("irreversible")
                        and not d.get("protected")
                    )

                all_detections.extend(final)

            ctx.detections = all_detections

            # Phase 15, D-013: Apply context-word boosting to financial crime
            # entities using the bridge from the detection pipeline module.
            # Boost runs per text node so word-position detection uses the
            # correct source text for each node's detections. Only boosts
            # financial crime entity types (IBAN, PAYMENT_REF, CUSTOMER_ID,
            # AML_CASE_REF), capped at 1.0. Per T-15-03-01: single boost per
            # entity, no stacking.
            if ctx.detections and ctx.text_nodes:
                from anonreq.detection.pipeline import boost_detections

                boosted_detections: list[dict[str, Any]] = []
                for i, node in enumerate(ctx.text_nodes):
                    node_value = node.get("value", "")
                    node_detections: list[dict[str, Any]] = [
                        d for d in ctx.detections if d.get("node_index") == i
                    ]
                    if node_detections:
                        boosted_detections.extend(
                            boost_detections(node_detections, node_value),
                        )
                ctx.detections = boosted_detections

            # Log entity counts grouped by type
            entity_counts: dict[str, int] = {}
            for d in ctx.detections:
                etype = d.get("entity_type", "UNKNOWN")
                entity_counts[etype] = entity_counts.get(etype, 0) + 1

            logger.info(
                "detection.complete",
                stage=self.name,
                request_id=ctx.request_id,
                total_detections=len(all_detections),
                entity_counts=entity_counts,
                presidio_language=presidio_language,
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
            fail_secure_events.labels(
                tenant_id=ctx.tenant_id,
                failure_type="detection_error",
            ).inc()
            raise
        except PresidioUnsupportedLanguageError as exc:
            # Do not retry with language=en. The English model misses German
            # names and street addresses, so a fallback would forward PII.
            logger.warning(
                "detection.presidio_language_unsupported",
                stage=self.name,
                request_id=ctx.request_id,
                presidio_language=exc.language,
                error_type="presidio_unsupported_language",
                status_code=503,
            )
            fail_secure_events.labels(
                tenant_id=ctx.tenant_id,
                failure_type="presidio_unsupported_language",
            ).inc()
            ctx.fail_secure(
                PresidioLanguageUnsupportedError(
                    exc.language,
                    request_id=ctx.request_id,
                )
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            fail_secure_events.labels(
                tenant_id=ctx.tenant_id,
                failure_type="detection_error",
            ).inc()
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=500,
                    message=f"Detection stage failed: {type(exc).__name__}: {exc}",
                    request_id=ctx.request_id,
                )
            )
        except Exception as exc:
            fail_secure_events.labels(
                tenant_id=ctx.tenant_id,
                failure_type="detection_error",
            ).inc()
            ctx.fail_secure(
                PipelineAbortError(
                    status_code=500,
                    message=f"Detection stage failed: {type(exc).__name__}",
                    request_id=ctx.request_id,
                )
            )

        return ctx
