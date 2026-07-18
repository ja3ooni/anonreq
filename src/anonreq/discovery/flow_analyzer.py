"""Flow analysis heuristics for AI API traffic detection.

Provides:
- ``FlowAnalyzer`` — analyses HTTP requests for AI API patterns even when
  hostname/IP matching fails (e.g. self-hosted proxies, custom domains).
- ``FlowResult`` — dataclass for analysis results with confidence scoring.

Per D-007, D-008, D-011:
- Path pattern matching: detects ``/chat/completions``, ``/v1/messages``, etc.
- Header pattern matching: detects OpenAI ``sk-*``, Anthropic ``sk-ant-*`` keys.
- Body content analysis: detects LLM request fields (``model``, ``messages``,
  ``prompt``, ``max_tokens``).
- Configurable confidence threshold to reduce false positives.
- Analysis is read-only — no request data is stored or forwarded.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Known AI API path patterns (case-insensitive substring match)
AI_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"/v\d/chat/completions", re.IGNORECASE),
    re.compile(r"/v\d/completions", re.IGNORECASE),
    re.compile(r"/v\d/messages", re.IGNORECASE),
    re.compile(r"/v\d/embeddings", re.IGNORECASE),
    re.compile(r"/v\d/models/?$", re.IGNORECASE),
    re.compile(r"/chat/completions", re.IGNORECASE),
    re.compile(r"/v\d/generate", re.IGNORECASE),
    re.compile(r"/api/chat", re.IGNORECASE),
    re.compile(r"/api/generate", re.IGNORECASE),
    re.compile(r"/v\d/rerank", re.IGNORECASE),
    re.compile(r"/inference", re.IGNORECASE),
]

# AI API key header patterns
AI_KEY_HEADER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("authorization", re.compile(r"Bearer\s+sk-[a-zA-Z0-9-]{10,}", re.IGNORECASE)),
    ("x-api-key", re.compile(r"sk-ant-[a-zA-Z0-9]{10,}", re.IGNORECASE)),
    ("x-api-key", re.compile(r"sk-[a-zA-Z0-9-]{10,}", re.IGNORECASE)),
]

# LLM request body fields that indicate AI API traffic
LLM_BODY_FIELDS: set[str] = {
    "messages",
    "prompt",
    "model",
    "max_tokens",
    "temperature",
    "top_p",
    "stop",
    "stream",
    "frequency_penalty",
    "presence_penalty",
    "tools",
    "tool_choice",
    "response_format",
}

# Minimum body size to trigger body analysis (bytes)
MIN_BODY_SIZE_FOR_ANALYSIS = 100


@dataclass
class FlowResult:
    """Result of flow analysis on a request.

    Attributes:
        provider: Provider name (always ``"unknown"`` for flow analysis —
            hostname matching is the authoritative identification).
        confidence: Weighted confidence score (0.0 to 1.0).
        indicators: List of human-readable indicator descriptions.
    """

    provider: str = "unknown"
    confidence: float = 0.0
    indicators: list[str] = field(default_factory=list)


class FlowAnalyzer:
    """Analyses HTTP requests for AI API traffic patterns.

    Uses a weighted scoring system based on path patterns, header patterns,
    and body content analysis to detect AI API traffic even when the
    destination hostname is not in the known provider allowlist.

    The analyzer is read-only — it inspects requests but does not modify
    or store any data.
    """

    def __init__(self, confidence_threshold: float = 0.6) -> None:
        self._threshold = confidence_threshold

    def get_confidence_threshold(self) -> float:
        """Return the current confidence threshold.

        Returns:
            The threshold value (default 0.6).
        """
        return self._threshold

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set the confidence threshold.

        Results below this threshold are filtered out.

        Args:
            threshold: New threshold value between 0.0 and 1.0.
        """
        self._threshold = max(0.0, min(1.0, threshold))

    def analyze_request(self, request: Any) -> FlowResult | None:
        """Analyse an HTTP request for AI API traffic patterns.

        Checks path patterns, header patterns, and body content. Returns
        a ``FlowResult`` with weighted confidence score if the total
        exceeds the threshold, ``None`` otherwise.

        Args:
            request: A request-like object with ``method``, ``url.path``,
                ``headers`` (dict-like), and optional ``_body`` (bytes).

        Returns:
            ``FlowResult`` if AI patterns detected, ``None`` otherwise.
        """
        indicators: list[str] = []
        score: float = 0.0
        path: str = getattr(request.url, "path", "")
        method: str = getattr(request, "method", "GET")
        headers: dict[str, str] = _get_headers(request)
        body: bytes = getattr(request, "_body", b"") or b""

        # -- Path analysis --
        # POST indicates AI API usage (most AI endpoints use POST)
        if method == "POST" and path:
            path_score = self._check_path_patterns(path)
            if path_score > 0:
                score += path_score
                indicators.append(f"path_match:{path}")

        # -- Header analysis --
        header_score = self._check_header_patterns(headers)
        if header_score > 0:
            score += header_score
            indicators.append("header_key_match")

        # -- Body analysis --
        if len(body) >= MIN_BODY_SIZE_FOR_ANALYSIS and headers.get("content-type", "").startswith("application/json"):  # noqa: E501
            body_score = self._check_body_patterns(body)
            if body_score > 0:
                score += body_score
                indicators.append("body_pattern_match")

        # Additional signals that boost confidence
        content_type = headers.get("content-type", "")
        if "application/json" in content_type and method == "POST":
            score += 0.05
            if "body_pattern_match" not in indicators:
                indicators.append("json_content_type")

        # Check if score exceeds threshold
        if score >= self._threshold:
            return FlowResult(
                provider="unknown",
                confidence=min(score, 1.0),
                indicators=indicators,
            )

        return None

    def _check_path_patterns(self, path: str) -> float:
        """Check URL path against known AI API patterns.

        A known AI API path is a strong signal — returns threshold-level
        confidence so even path-only detection triggers.

        Returns:
            Score contribution (0.6 for known AI API path match).
        """
        for pattern in AI_PATH_PATTERNS:
            if pattern.search(path):
                return 0.6
        return 0.0

    def _check_header_patterns(self, headers: dict[str, str]) -> float:
        """Check request headers for AI API key patterns.

        Returns:
            Score contribution (0.5 for API key match).
        """
        for header_name, pattern in AI_KEY_HEADER_PATTERNS:
            value = headers.get(header_name, "")
            if pattern.search(value):
                return 0.5
        return 0.0

    def _check_body_patterns(self, body: bytes) -> float:
        """Check request body for LLM API request patterns.

        Returns:
            Score contribution (0.4-0.6 depending on signal strength).
        """
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 0.0

        if not isinstance(data, dict):
            return 0.0

        # Count how many known LLM fields are present
        matched_fields = set(data.keys()) & LLM_BODY_FIELDS
        if not matched_fields:
            return 0.0

        # Check for required AI fields
        has_messages = "messages" in data and isinstance(data["messages"], list) and len(data["messages"]) > 0  # noqa: E501
        has_prompt = "prompt" in data and isinstance(data["prompt"], str) and len(data["prompt"]) > 0  # noqa: E501
        has_model = "model" in data

        # Strong signal: has messages + model (chat completion structure)
        if has_messages and has_model:
            return 0.6

        # Moderate signal: has messages or prompt, plus other LLM fields
        if has_messages or has_prompt:
            return 0.5

        # Weak signal: just LLM-related config fields
        return 0.4


def _get_headers(request: Any) -> dict[str, str]:
    """Extract headers from a request-like object.

    Handles both dict-like and object attribute access patterns.
    """
    headers = getattr(request, "headers", {})
    if hasattr(headers, "items"):
        # Convert to plain dict with lowercase keys
        return {k.lower(): v for k, v in headers.items()}
    if isinstance(headers, dict):
        return {k.lower(): v for k, v in headers.items()}
    return {}
