"""RegexDetector — runs pre-compiled patterns on text for deterministic PII detection.

Per D-38:
- Regex results always have score=1.0 (deterministic)
- Credit card patterns require Luhn checksum validation
- All detection results tagged with source="regex" for span arbitration
"""

from __future__ import annotations

import re
from typing import Any

from anonreq.detection.regex_patterns import PATTERNS, luhn_checksum
from anonreq.locale.bundle import EntityTypeConfig, RecognizerTier

# Entity types that require Luhn checksum validation
_LUHN_VALIDATED = {"CREDIT_CARD"}


class RegexDetector:
    """Runs pre-compiled regex patterns on text to detect structured PII.

    Usage::

        detector = RegexDetector()
        results = detector.detect("Email: user@example.com")
        # Returns: [{"entity_type": "EMAIL_ADDRESS", "start": 7, "end": 22, ...}]
    """

    def __init__(
        self,
        patterns: dict[str, re.Pattern] | None = None,
    ) -> None:
        """Initialize the detector with optional custom patterns.

        Args:
            patterns: Dict mapping entity_type to compiled regex pattern.
                Defaults to ``PATTERNS`` from ``regex_patterns``.
        """
        self._patterns = patterns if patterns is not None else PATTERNS

    @staticmethod
    def patterns_from_entity_configs(
        entity_configs: list[EntityTypeConfig],
    ) -> dict[str, re.Pattern]:
        """Compile regex patterns declared by locale bundle entity configs."""
        compiled: dict[str, re.Pattern] = {}
        for config in entity_configs:
            if config.tier not in (RecognizerTier.REGEX, RecognizerTier.BOTH):
                continue
            if not config.patterns:
                continue
            compiled[config.name] = re.compile("|".join(f"(?:{p})" for p in config.patterns))
        return compiled

    def detect(
        self,
        text: str,
        extra_patterns: dict[str, re.Pattern] | None = None,
    ) -> list[dict[str, Any]]:
        """Run all patterns on the given text and return detections.

        Args:
            text: The text to scan for PII.

        Returns:
            List of detection dicts, each with:
            - ``entity_type``: The type of detected entity.
            - ``start``: Character offset where the entity starts.
            - ``end``: Character offset where the entity ends.
            - ``score``: Always ``1.0`` for regex detections (D-38).
            - ``source``: Always ``"regex"`` (D-39).
        """
        if not text:
            return []

        results: list[dict[str, Any]] = []
        seen_spans: set[tuple[str, int, int]] = set()

        patterns = dict(self._patterns)
        if extra_patterns:
            patterns.update(extra_patterns)

        for entity_type, pattern in patterns.items():
            for match in pattern.finditer(text):
                start, end = match.start(), match.end()

                # De-duplicate overlapping matches for the same entity type
                span_key = (entity_type, start, end)
                if span_key in seen_spans:
                    continue
                seen_spans.add(span_key)

                # For credit cards, validate Luhn checksum
                if entity_type in _LUHN_VALIDATED:
                    card_text = text[start:end]
                    if not luhn_checksum(card_text):
                        continue

                results.append({
                    "entity_type": entity_type,
                    "start": start,
                    "end": end,
                    "score": 1.0,
                    "source": "regex",
                })

        # Sort by start position for consistent ordering
        results.sort(key=lambda r: r["start"])
        return results
