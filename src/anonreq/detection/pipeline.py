"""MNPI pipeline integration for the detection engine.

Per Phase 15, D-001, D-002, D-003:
- Loads MNPI recognizer bundle at startup alongside core recognizers
- MNPI runs after core Presidio pipeline (as additional recognizer)
- Merged detection list includes MNPI entities alongside core entities

Per T-15-01-01: All detection happens in-memory; only hashed values stored in audit.
"""

from __future__ import annotations

import logging
from typing import Any

from anonreq.detection.recognizers.mnpi import MNPIRecognizer, create_mnpi_bundle

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
