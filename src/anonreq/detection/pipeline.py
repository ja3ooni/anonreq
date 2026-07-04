"""MNPI pipeline integration and context boosting for the detection engine.

Per Phase 15, D-001, D-002, D-003:
- Loads MNPI recognizer bundle at startup alongside core recognizers
- MNPI runs after core Presidio pipeline (as additional recognizer)
- Merged detection list includes MNPI entities alongside core entities

Per D-013:
- Context-word boosting applies +0.15 within 50 chars of high-risk words
- Only financial crime entity types boosted, capped at 1.0

Per T-15-01-01: All detection happens in-memory; only hashed values stored in audit.
Per T-15-03-01: Boost capped at 1.0; only financial entity types; single boost per entity.
"""

from __future__ import annotations

import logging
from typing import Any

from anonreq.detection.boost import ContextBooster
from anonreq.detection.recognizers.mnpi import MNPIRecognizer, create_mnpi_bundle
from anonreq.models.detection import DetectionResult

logger = logging.getLogger(__name__)


def load_mnpi_recognizers(
    config_path: str = "config/mnpi_recognizers.yaml",
    restricted_names_mgr: Any | None = None,
) -> list[MNPIRecognizer]:
    """Load and return the MNPI recognizer bundle.

    Called during pipeline construction to register MNPI recognizers
    alongside the core Presidio pipeline. Returns an empty list if the
    config file is not found (graceful degradation to avoid blocking
    startup when MNPI compliance is not yet configured).

    Args:
        config_path: Path to the MNPI recognizer YAML config.
        restricted_names_mgr: Optional ``RestrictedNamesManager`` for
            tenant restricted-name detection.

    Returns:
        A list of ``MNPIRecognizer`` instances (typically one).
    """
    try:
        return create_mnpi_bundle(
            config_path=config_path,
            restricted_names_mgr=restricted_names_mgr,
        )
    except FileNotFoundError:
        logger.warning(
            "MNPI config not found; MNPI detection disabled",
            extra={"config_path": config_path},
        )
        return []
    except Exception:
        logger.exception("Failed to load MNPI recognizers")
        return []


def boost_detections(
    detections: list[dict[str, Any]],
    text: str,
    booster: ContextBooster | None = None,
) -> list[dict[str, Any]]:
    """Apply context-word confidence boosting to financial crime detections.

    Runs the ``ContextBooster`` on each dict-based detection, converting
    between pipeline dicts and ``DetectionResult`` objects as needed.

    Only financial crime entity types (IBAN, PAYMENT_REF, CUSTOMER_ID,
    AML_CASE_REF) within 50 chars of high-risk words receive the +0.15
    boost. The boost is capped at 1.0 (T-15-03-01).

    Args:
        detections: List of detection dicts from the pipeline (must have
            keys ``entity_type``, ``start``, ``end``, ``score``, ``source``).
        text: The original text containing the detected entities.
        booster: Optional ``ContextBooster`` instance. A default one is
            created if not provided.

    Returns:
        The modified detection list with boosted scores where applicable.
    """
    if not detections:
        return detections

    if booster is None:
        booster = ContextBooster()

    word_positions = booster.find_high_risk_word_positions(
        text, booster.high_risk_words
    )

    if not word_positions:
        return detections

    boosted: list[dict[str, Any]] = []
    for det in detections:
        entity = DetectionResult(
            entity_type=det.get("entity_type", ""),
            start=det.get("start", 0),
            end=det.get("end", 0),
            score=det.get("score", 0.0),
            source=det.get("source", "regex"),
        )
        result = booster.apply_boost(entity, text, word_positions)
        # Preserve all other dict keys (node_index, locale, etc.)
        det["entity_type"] = result.entity_type
        det["start"] = result.start
        det["end"] = result.end
        det["score"] = result.score
        det["source"] = result.source
        boosted.append(det)

    return boosted


def merge_mnpi_detections(
    core_detections: list[dict[str, Any]],
    mnpi_detections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge MNPI detections into the core detection list.

    MNPI detections are appended to the core list. No overlap resolution
    is needed since MNPI entity types (MNPI_TICKER, MNPI_DEAL,
    MNPI_RESTRICTED_NAME) do not overlap with core entity types.

    Args:
        core_detections: Detection results from the core pipeline.
        mnpi_detections: Additional MNPI detection results.

    Returns:
        Combined detection list.
    """
    return list(core_detections) + list(mnpi_detections)
