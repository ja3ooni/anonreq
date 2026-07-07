from __future__ import annotations

import re
from re import Pattern

from anonreq.firewall.config import FirewallConfig


SYSTEM_PROMPT_SIGNALS: tuple[str, ...] = (
    r"(?i)(system\s*prompt|initial\s*instruction|base\s*persona|your\s*instructions)",
    r"(?i)(ignore\s*(all\s*)?previous|disregard|forget\s*(all\s*)?your)",
    r"(?i)(you\s*are\s*now|act\s*as\s*if|pretend\s*to\s*be|from\s*now\s*on)",
)


class OverrideDetector:
    """Detects system prompt extraction and role-manipulation attempts."""

    def __init__(self, config: FirewallConfig | None = None) -> None:
        self.config = config or FirewallConfig()
        self._patterns: tuple[Pattern[str], ...] = tuple(re.compile(p) for p in SYSTEM_PROMPT_SIGNALS)

    def score(self, text: str) -> float:
        if not text.strip():
            return 0.0
        matches = sum(1 for pattern in self._patterns if pattern.search(text))
        extraction_bonus = 0.0
        lowered = text.casefold()
        if "reveal" in lowered or "show me" in lowered or "print" in lowered:
            extraction_bonus = 0.12
        if matches == 0:
            return 0.0
        return min(0.99, 0.58 + matches * 0.15 + extraction_bonus)

    def classify(self, text: str, score: float | None = None) -> bool:
        final_score = self.score(text) if score is None else score
        return final_score >= self.config.override_threshold
