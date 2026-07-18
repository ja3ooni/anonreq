"""ExclusionList — exact-match and wildcard suppression of false positives.

Per DET-05:
- Exact match: literal string comparison
- Wildcard match: ``*`` character matches any sequence of characters
- Applied after span arbitration, before tokenization
- Loaded from YAML at startup
"""

from __future__ import annotations

import re
from fnmatch import translate
from pathlib import Path
from re import compile as re_compile
from typing import Any


class ExclusionList:
    """List of exclusion patterns for suppressing false positive detections.

    Supports exact matches and wildcard patterns (``*`` matches any sequence).

    Usage::

        ex = ExclusionList(exclusions=["safe@example.com", "test-*"])
        ex.is_excluded("test-123")  # True (wildcard)
        ex.is_excluded("safe@example.com")  # True (exact)
    """

    def __init__(self, exclusions: list[str] | None = None) -> None:
        self._exact: set[str] = set()
        self._wildcard_patterns: list[re.Pattern[str]] = []

        if exclusions:
            for pattern in exclusions:
                if "*" in pattern:
                    # Convert fnmatch pattern to regex
                    regex_str = translate(pattern)
                    self._wildcard_patterns.append(re_compile(regex_str))
                else:
                    self._exact.add(pattern)

    @classmethod
    def from_yaml(cls, path: str | Path) -> ExclusionList:
        """Load exclusion patterns from a YAML file.

        Expected format::

            exclusions:
              - value: "user@example.com"
              - value: "test-*"

        Args:
            path: Path to the YAML file.

        Returns:
            A new ``ExclusionList`` instance.
        """
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict) or "exclusions" not in data:
            return cls(exclusions=[])

        raw = data["exclusions"]
        if not isinstance(raw, list):
            return cls(exclusions=[])

        exclusions: list[str] = []
        for item in raw:
            if isinstance(item, dict) and "value" in item:
                exclusions.append(item["value"])

        return cls(exclusions=exclusions)

    def is_excluded(self, value: str) -> bool:
        """Check if a value is excluded.

        Args:
            value: The detected text value to check.

        Returns:
            ``True`` if the value matches any exclusion pattern.
        """
        # Check exact match
        if value in self._exact:
            return True

        # Check wildcard patterns
        return any(pattern.fullmatch(value) for pattern in self._wildcard_patterns)

    def filter_detections(
        self,
        detections: list[dict[str, Any]],
        original_text: str,
    ) -> list[dict[str, Any]]:
        """Remove detections whose text value matches an exclusion.

        Args:
            detections: List of detection dicts with ``start``, ``end``.
            original_text: The original text that was scanned. Detection
                values are extracted from this text using start/end offsets.

        Returns:
            Filtered detection list with excluded entries removed.
        """
        filtered: list[dict[str, Any]] = []
        for det in detections:
            if "start" not in det or "end" not in det:
                filtered.append(det)
                continue
            value = original_text[det["start"] : det["end"]]
            if not self.is_excluded(value):
                filtered.append(det)
        return filtered
