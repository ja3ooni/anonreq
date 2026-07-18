"""Hybrid exfiltration encoding detection (Plan 13-03, Task 2).

Combines heuristic pattern matching (Base64, hex, JWT, PEM) with
Shannon entropy analysis for unknown encoding detection.

Key design decisions:
- Pattern matching first, then entropy filtering for lower false positive rate
- Match text truncated to 50 chars for safety (avoids storing exfiltrated content)
- Min length filters (20-30 chars) to reduce false positives on short random strings
- Confidence scoring: JWT/PEM exact patterns = 0.85, Base64/hex = 0.75,
  entropy-only = 0.5+
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ExfiltrationResult:
    """Result of a single exfiltration detection match.

    Attributes:
        detected: Whether exfiltration content was detected.
        method: Detection method that matched (``"base64"`` | ``"hex"`` |
            ``"jwt"`` | ``"pem"`` | ``"high_entropy"``).
        confidence: Confidence score (0.0 to 1.0).
        shannon_entropy: Shannon entropy in bits/byte, or None.
        match_text: Truncated matched text (max 50 chars).
        start: Start position in original text.
        end: End position in original text.
    """

    detected: bool
    method: str | None
    confidence: float
    shannon_entropy: float | None
    match_text: str | None
    start: int
    end: int


@dataclass
class ExfiltrationSummary:
    """Summary of exfiltration detection across all methods.

    Attributes:
        detected: True if any exfiltration was detected.
        methods: List of detection methods that matched.
        max_confidence: Highest confidence score across all detections.
        detection_count: Total number of individual detections.
    """

    detected: bool
    methods: list[str]
    max_confidence: float
    detection_count: int


class ExfiltrationDetector:
    """Hybrid exfiltration encoding detector.

    Detects data exfiltration attempts through encoded channels using:
    1. Regex pattern matching for known encoding types (Base64, hex, JWT, PEM)
    2. Shannon entropy analysis for unknown or high-entropy encodings
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize with full DLP config dict (``config["dlp"]`` or similar).

        Args:
            config: DLP config containing the ``exfiltration`` section.
        """
        self._config = config.get("exfiltration", {}).get("detection", {})
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for each detection method."""
        self._patterns: dict[str, re.Pattern[str]] = {}
        for method, cfg in self._config.get("methods", {}).items():
            if cfg.get("enabled", False) and "pattern" in cfg:
                self._patterns[method] = re.compile(cfg["pattern"])

    def _shannon_entropy(self, data: str) -> float:
        """Compute Shannon entropy in bits per byte.

        Higher entropy = more random content.
        Normal English text: ~3.5-5.0 bits/byte
        Base64: ~5.5-6.0 bits/byte
        Random/encrypted: ~7.0-8.0 bits/byte

        Args:
            data: Input string to analyze.

        Returns:
            Shannon entropy in bits per byte (0.0 for empty input).
        """
        if not data:
            return 0.0
        byte_data = data.encode("utf-8")
        length = len(byte_data)
        entropy = 0.0
        # Count byte frequencies
        freq: dict[int, int] = {}
        for b in byte_data:
            freq[b] = freq.get(b, 0) + 1
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)
        return entropy

    async def detect(self, text: str) -> list[ExfiltrationResult]:
        """Run all exfiltration detection methods against text.

        1. Run regex pattern detection for each enabled method
        2. Check Shannon entropy for matched segments and standalone
           high-entropy strings
        3. Combine results, deduplicate overlapping matches
        4. Return ``ExfiltrationResult`` list

        Args:
            text: The text to inspect for exfiltration patterns.

        Returns:
            List of ``ExfiltrationResult`` objects, one per detection.
        """
        results: list[ExfiltrationResult] = []
        # Track (method, start, end) for dedup — only skip exact same-method overlaps
        method_ranges: dict[str, list[tuple[int, int]]] = {}

        for method, pattern in self._patterns.items():
            method_ranges.setdefault(method, [])
            for match in pattern.finditer(text):
                matched = match.group()
                start = match.start()
                end = match.end()

                # Check if this method already reported this exact range
                if (start, end) in method_ranges[method]:
                    continue

                # Check min_length filter for this method
                min_len = (
                    self._config.get("methods", {})
                    .get(method, {})
                    .get("min_length", 0)
                )
                if len(matched) < min_len:
                    continue

                entropy = self._shannon_entropy(matched)
                method_ranges[method].append((start, end))
                results.append(
                    ExfiltrationResult(
                        detected=True,
                        method=method,
                        confidence=0.85
                        if method in ("jwt", "pem")
                        else 0.75,
                        shannon_entropy=entropy,
                        match_text=matched[:50],  # Truncate for safety
                        start=start,
                        end=end,
                    )
                )

        # Build a set of covered positions for entropy dedup.
        # Only skip ranges that are EXACTLY equal to an existing pattern match,
        # not just overlapping — different methods may cover the same span.
        covered_spans: set[tuple[int, int]] = set()
        for _method, ranges in method_ranges.items():
            covered_spans.update(ranges)

        # Method 2: High-entropy detection for unknown encodings
        entropy_config = self._config.get("entropy", {})
        if entropy_config.get("enabled", True):
            threshold = entropy_config.get("threshold", 6.0)
            min_length = entropy_config.get("min_length", 30)
            for word in re.finditer(r"\S{30,}", text):
                word_text = word.group()
                word_start = word.start()
                word_end = word.end()

                # Skip exact duplicates of pattern matches
                if (word_start, word_end) in covered_spans:
                    continue

                entropy = self._shannon_entropy(word_text)
                if entropy > threshold and len(word_text) >= min_length:
                    confidence = min(
                        0.5 + (entropy - threshold) * 0.1, 0.95
                    )
                    covered_spans.add((word_start, word_end))
                    results.append(
                        ExfiltrationResult(
                            detected=True,
                            method="high_entropy",
                            confidence=confidence,
                            shannon_entropy=entropy,
                            match_text=word_text[:50],
                            start=word_start,
                            end=word_end,
                        )
                    )

        return results

    async def detect_in_text(self, text: str) -> ExfiltrationSummary:
        """Convenience: detect all exfiltration, return summary.

        Combines overlapping detections, returns highest confidence
        per segment.

        Args:
            text: The text to inspect.

        Returns:
            An ``ExfiltrationSummary`` with aggregate results.
        """
        results = await self.detect(text)
        return ExfiltrationSummary(
            detected=len(results) > 0,
            methods=list(set(r.method for r in results if r.method)),
            max_confidence=max(
                (r.confidence for r in results), default=0.0
            ),
            detection_count=len(results),
        )
