"""DetectionProvider — integrates AtomicConfigRegistry custom recognizers.

Per the hot-reload scope (D-152):
- Hot-reloadable: custom recognizer patterns, confidence thresholds, exclusion list entries
- The DetectionProvider holds a reference to the AtomicConfigRegistry and checks
  it during each analyze() call for custom recognizers alongside built-in patterns.

Simplest MVP approach: provider supplies compiled custom patterns on each call
rather than maintaining a separate notification channel. This avoids explicit
hot-reload coupling between the admin API and detection pipeline.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anonreq.admin.config import AtomicConfigRegistry

logger = logging.getLogger(__name__)


def get_custom_recognizer_patterns(
    registry: AtomicConfigRegistry | None,
) -> dict[str, re.Pattern[str]]:
    """Compile custom recognizer patterns from the AtomicConfigRegistry.

    Called during each detection cycle to check for hot-reloaded custom
    recognizers. Returns an empty dict if the registry is None or contains
    no enabled custom recognizers.

    Args:
        registry: The AtomicConfigRegistry to pull custom rules from,
            or None if admin API is not configured.

    Returns:
        Dict mapping entity_type to compiled regex Pattern for each
        enabled custom recognizer with valid patterns.
    """
    if registry is None:
        return {}

    config = registry.get_active()
    if not config.custom_recognizers:
        return {}

    patterns: dict[str, re.Pattern[str]] = {}
    for recognizer in config.custom_recognizers:
        if not recognizer.enabled:
            continue
        if not recognizer.patterns:
            continue
        # Combine all patterns for this recognizer into one alternation
        combined = "|".join(f"(?:{p})" for p in recognizer.patterns)
        try:
            patterns[recognizer.entity_type] = re.compile(combined)
        except re.error:
            logger.warning(
                "Skipping invalid custom recognizer pattern",
                extra={"recognizer_id": recognizer.id, "entity_type": recognizer.entity_type},
            )
            continue

    return patterns
