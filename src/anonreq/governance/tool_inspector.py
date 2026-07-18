"""ToolResultInspector — validates tool call results for PII and reconstruction attempts.

Per D-011, D-012:
- PII detection via Phase 2 PresidioClient
- Reconstruction attempt detection using CacheManager (token mappings)
- Action determination: allow | suppress | alert
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from anonreq.cache.manager import CacheManager
from anonreq.detection.presidio_client import PresidioClient

# Regex patterns for reconstruction attempt detection
TOKEN_PATTERN = re.compile(r"\[([A-Z][A-Z_]{0,49})_(\d+)\]")
RECONSTRUCTION_PROMPT_PATTERNS = [
    re.compile(r"regenerate\s+(the\s+)?(email|phone|ssn|address|name|token)", re.IGNORECASE),
    re.compile(r"fill\s+(in|out)\s+(the\s+)?(\[.*?\]|placeholder)", re.IGNORECASE),
    re.compile(r"reconstruct\s+(the\s+)?(original|pii|data)", re.IGNORECASE),
    re.compile(r"reverse\s+(the\s+)?(anonymization|tokenization)", re.IGNORECASE),
    re.compile(r"undo\s+(the\s+)?(anonymization|replacement)", re.IGNORECASE),
    re.compile(r"put\s+(back|the\s+original)", re.IGNORECASE),
    re.compile(r"restore\s+(the\s+)?(original|values|data)", re.IGNORECASE),
    re.compile(r"give\s+me\s+the\s+(real|actual|original)", re.IGNORECASE),
]


class InspectionResult:
    """Result of a tool result inspection.

    Attributes:
        tool_name: Name of the tool that produced the result.
        tool_id: ID of the tool call.
        pii_detected: Whether PII was found in the result.
        pii_entity_count: Number of PII entities detected.
        pii_entity_types: Entity types detected (e.g. [\"EMAIL_ADDRESS\", \"PHONE\"]).
        reconstruction_attempt: Whether a reconstruction attempt was detected.
        reconstruction_confidence: Confidence score 0.0-1.0.
        reconstruction_indicators: List of indicator descriptions.
        action: \"allow\" | \"suppress\" | \"alert\".
    """

    __slots__ = (
        "action",
        "pii_detected",
        "pii_entity_count",
        "pii_entity_types",
        "reconstruction_attempt",
        "reconstruction_confidence",
        "reconstruction_indicators",
        "tool_id",
        "tool_name",
    )

    def __init__(
        self,
        tool_name: str = "",
        tool_id: str = "",
        pii_detected: bool = False,
        pii_entity_count: int = 0,
        pii_entity_types: list[str] | None = None,
        reconstruction_attempt: bool = False,
        reconstruction_confidence: float = 0.0,
        reconstruction_indicators: list[str] | None = None,
        action: str = "allow",
    ) -> None:
        self.tool_name = tool_name
        self.tool_id = tool_id
        self.pii_detected = pii_detected
        self.pii_entity_count = pii_entity_count
        self.pii_entity_types = pii_entity_types or []
        self.reconstruction_attempt = reconstruction_attempt
        self.reconstruction_confidence = reconstruction_confidence
        self.reconstruction_indicators = reconstruction_indicators or []
        self.action = action

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for audit metadata."""
        return {
            "tool_name": self.tool_name,
            "tool_id": self.tool_id,
            "pii_detected": self.pii_detected,
            "pii_entity_count": self.pii_entity_count,
            "pii_entity_types": list(self.pii_entity_types),
            "reconstruction_attempt": self.reconstruction_attempt,
            "reconstruction_confidence": round(self.reconstruction_confidence, 4),
            "reconstruction_indicators": list(self.reconstruction_indicators),
            "action": self.action,
            "inspected_at": datetime.now(UTC).isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"InspectionResult(tool={self.tool_name}, "
            f"pii={self.pii_detected}, "
            f"recon={self.reconstruction_attempt}, "
            f"action={self.action})"
        )


def _extract_text_content(result: Any) -> str:
    """Extract text content from a ToolResult for analysis."""
    content = result.content
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return json.dumps(content, default=str)
    return str(content)


async def _detect_reconstruction_attempts(
    text_content: str,
    session_id: str | None,
    cache_manager: CacheManager | None,
) -> tuple[bool, float, list[str]]:
    """Detect reconstruction attempts in tool result content.

    Checks 4 indicator types:
    1. Token pattern matches (e.g. ``[EMAIL_0]``)
    2. Reconstructed values matching known token mappings
    3. Reconstruction prompt language
    4. Suspicious bracket patterns

    Returns:
        Tuple of (attempt_detected, confidence, list_of_indicators).
    """
    indicators: list[str] = []
    confidence: float = 0.0

    # Indicator 1: Token pattern matches
    token_matches = list(TOKEN_PATTERN.finditer(text_content))
    if token_matches:
        token_types = set(m.group(1) for m in token_matches)
        indicators.append(
            f"Token patterns found: {len(token_matches)} matches "
            f"({', '.join(sorted(token_types))})"
        )
        confidence = max(confidence, 0.5 + min(len(token_matches) * 0.1, 0.4))

    # Indicator 2: Reconstructed values matching token mappings
    if session_id and cache_manager:
        try:
            mapping_key = f"anonreq:{session_id}:*"
            cursor = 0
            found_original = False
            while not found_original:
                cursor, keys = await cache_manager._redis.scan(
                    cursor=cursor, match=mapping_key, count=50
                )
                if not keys:
                    break

                for key_bytes in keys:
                    key = key_bytes.decode() if isinstance(key_bytes, bytes) else key_bytes
                    if not key.startswith(f"anonreq:{session_id}:"):
                        continue
                    original = await cache_manager._redis.get(key)
                    if original is not None:
                        original_str = original.decode() if isinstance(original, bytes) else str(original)  # noqa: E501
                        if original_str in text_content:
                            indicators.append(
                                "Reconstructed value found in content matching token mapping"
                            )
                            found_original = True
                            confidence = max(confidence, 0.8)
                            break

                if cursor == 0:
                    break
        except Exception:
            pass

    # Indicator 3: Reconstruction prompt patterns
    for pattern in RECONSTRUCTION_PROMPT_PATTERNS:
        match = pattern.search(text_content)
        if match:
            indicators.append(f"Reconstruction prompt language detected: '{match.group()}'")
            confidence = max(confidence, 0.75)
            break

    # Indicator 4: Suspicious bracket patterns
    bracket_pattern = re.compile(r"\[([A-Za-z\s_]{2,})\]")
    bracket_matches = bracket_pattern.findall(text_content)
    new_brackets = [
        b for b in bracket_matches
        if not TOKEN_PATTERN.fullmatch(f"[{b}]")
    ]
    if len(new_brackets) >= 3:
        indicators.append(
            f"Suspicious bracket patterns: {len(new_brackets)} instances "
            f"suggest token-like formatting"
        )
        confidence = max(confidence, 0.4 + min(len(new_brackets) * 0.05, 0.3))

    attempt_detected = confidence >= 0.7
    return attempt_detected, min(confidence, 1.0), indicators


def _determine_action(
    pii_detected: bool,
    _pii_entity_count: int,
    reconstruction_attempt: bool,
    reconstruction_confidence: float,
) -> str:
    """Determine the action based on inspection results.

    - reconstruction_attempt AND confidence >= 0.9 -> \"suppress\"
    - pii_detected -> \"alert\"
    - otherwise -> \"allow\"
    """
    if reconstruction_attempt and reconstruction_confidence >= 0.9:
        return "suppress"
    if pii_detected:
        return "alert"
    return "allow"


class ToolResultInspector:
    """Validates tool call results for PII and reconstruction attempts.

    Uses Phase 2 PresidioClient for PII detection and CacheManager
    for reconstruction attempt detection via token mapping lookups.
    """

    def __init__(
        self,
        detection_engine: PresidioClient,
        cache_manager: CacheManager,
    ) -> None:
        self._detection_engine = detection_engine
        self._cache_manager = cache_manager

    async def inspect(
        self,
        tool_result: Any,
        session_id: str | None = None,
    ) -> InspectionResult:
        """Inspect a tool result for PII and reconstruction attempts.

        Args:
            tool_result: The ToolResult to inspect.
            session_id: Session ID for token mapping lookups.

        Returns:
            InspectionResult with findings and recommended action.
        """
        text_content = _extract_text_content(tool_result)
        result = InspectionResult(
            tool_name=tool_result.name,
            tool_id=tool_result.id,
        )

        if not text_content:
            return result

        # 1. PII detection via PresidioClient
        try:
            pii_results = await self._detection_engine.analyze(text_content)
            if pii_results:
                result.pii_detected = True
                result.pii_entity_count = len(pii_results)
                entity_types = list(
                    dict.fromkeys(r.get("entity_type", "UNKNOWN") for r in pii_results)
                )
                result.pii_entity_types = entity_types
        except Exception:
            pass

        # 2. Reconstruction attempt detection
        attempt_detected, confidence, indicators = await _detect_reconstruction_attempts(
            text_content=text_content,
            session_id=session_id,
            cache_manager=self._cache_manager if result.pii_detected else None,
        )
        result.reconstruction_attempt = attempt_detected
        result.reconstruction_confidence = confidence
        result.reconstruction_indicators = indicators

        # 3. Action determination
        result.action = _determine_action(
            pii_detected=result.pii_detected,
            _pii_entity_count=result.pii_entity_count,
            reconstruction_attempt=result.reconstruction_attempt,
            reconstruction_confidence=result.reconstruction_confidence,
        )

        return result
