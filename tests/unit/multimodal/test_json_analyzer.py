"""Unit tests for JsonAnalyzer."""

from __future__ import annotations

from typing import Any

import pytest

from anonreq.multimodal.json_analyzer import SENSITIVE_KEY_PATTERNS, JsonAnalyzer


class StubDetectionEngine:
    """Stub that returns controlled detections."""

    def __init__(self, detections: list[dict[str, Any]] | None = None) -> None:
        self._detections = detections or []
        self.calls: list[str] = []

    async def analyze_text(self, value: str) -> list[dict[str, Any]]:
        self.calls.append(value)
        return self._detections


@pytest.mark.unit
class TestSensitiveKeyPatterns:
    def test_ssn_pattern_matches(self) -> None:
        import re

        combined = "|".join(p.pattern for p in SENSITIVE_KEY_PATTERNS)
        assert re.search(combined, "ssn", re.IGNORECASE)
        assert re.search(combined, "social_security", re.IGNORECASE)

    def test_password_pattern_matches(self) -> None:
        import re

        combined = "|".join(p.pattern for p in SENSITIVE_KEY_PATTERNS)
        assert re.search(combined, "password", re.IGNORECASE)

    def test_credit_card_pattern_matches(self) -> None:
        import re

        combined = "|".join(p.pattern for p in SENSITIVE_KEY_PATTERNS)
        assert re.search(combined, "credit_card", re.IGNORECASE)


@pytest.mark.unit
class TestJsonAnalyzer:
    @pytest.mark.anyio
    async def test_analyze_returns_result(self) -> None:
        analyzer = JsonAnalyzer(detection_engine=None)
        result = await analyzer.analyze('{"name": "Alice"}')
        assert result is not None
        assert hasattr(result, "entities")

    @pytest.mark.anyio
    async def test_invalid_json_returns_error_metadata(self) -> None:
        analyzer = JsonAnalyzer(detection_engine=None)
        result = await analyzer.analyze("not json at all")
        assert result.analyzer_metadata.get("error") is not None

    @pytest.mark.anyio
    async def test_sensitive_key_detection_with_engine(self) -> None:
        engine = StubDetectionEngine(
            detections=[{"entity_type": "SSN", "start": 0, "end": 11, "score": 0.95}]
        )
        analyzer = JsonAnalyzer(detection_engine=engine)
        result = await analyzer.analyze('{"ssn": "123-45-6789"}')
        assert len(result.entities) >= 1
        assert engine.calls  # engine was called

    @pytest.mark.anyio
    async def test_depth_limit(self) -> None:
        analyzer = JsonAnalyzer(detection_engine=None, max_depth=2)
        deep = {"a": {"b": {"c": "value"}}}
        result = await analyzer.analyze(deep)
        assert result is not None

    @pytest.mark.anyio
    async def test_list_traversal(self) -> None:
        analyzer = JsonAnalyzer(detection_engine=None)
        data = {"items": ["a", "b", "c"]}
        result = await analyzer.analyze(data)
        assert result is not None

    @pytest.mark.anyio
    async def test_bytes_input(self) -> None:
        analyzer = JsonAnalyzer(detection_engine=None)
        result = await analyzer.analyze(b'{"key": "value"}')
        assert result is not None

    def test_is_sensitive_key(self) -> None:
        analyzer = JsonAnalyzer(detection_engine=None)
        assert analyzer._is_sensitive_key("ssn") is True
        assert analyzer._is_sensitive_key("password") is True
        assert analyzer._is_sensitive_key("name") is False
        assert analyzer._is_sensitive_key("credit_card_number") is True
