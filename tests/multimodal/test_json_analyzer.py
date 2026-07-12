from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from anonreq.multimodal.models import ContentType


@pytest.fixture
def mock_detection_engine():
    m = AsyncMock()

    async def side_effect(value, **_kwargs):
        if "John" in value:
            return [
                {
                    "entity_type": "PERSON",
                    "start": 0,
                    "end": len(value),
                    "score": 0.95,
                    "value": value,
                }
            ]
        if "example.com" in value:
            return [
                {
                    "entity_type": "EMAIL_ADDRESS",
                    "start": 0,
                    "end": len(value),
                    "score": 0.98,
                    "value": value,
                }
            ]
        return []

    m.analyze_text = AsyncMock(side_effect=side_effect)
    return m


class TestJsonAnalyzer:
    @pytest.mark.asyncio
    async def test_flat_json_scans_string_leaves(self, mock_detection_engine):
        from anonreq.multimodal.json_analyzer import JsonAnalyzer

        analyzer = JsonAnalyzer(detection_engine=mock_detection_engine)
        data = {"name": "John Doe", "email": "john@example.com"}
        result = await analyzer.analyze(data)
        assert result.content_type == ContentType.APPLICATION_JSON
        assert len(result.entities) >= 1
        entity_types = {e["entity_type"] for e in result.entities}
        assert "PERSON" in entity_types or "EMAIL_ADDRESS" in entity_types

    @pytest.mark.asyncio
    async def test_nested_json_walks_recursively(self, mock_detection_engine):
        from anonreq.multimodal.json_analyzer import JsonAnalyzer

        analyzer = JsonAnalyzer(detection_engine=mock_detection_engine)
        data = {"user": {"profile": {"ssn": "123-45-6789"}}}
        result = await analyzer.analyze(data)
        assert result.content_type == ContentType.APPLICATION_JSON

    @pytest.mark.asyncio
    async def test_json_with_arrays_walks_elements(self, mock_detection_engine):
        from anonreq.multimodal.json_analyzer import JsonAnalyzer

        analyzer = JsonAnalyzer(detection_engine=mock_detection_engine)
        data = {"users": [{"email": "a@b.com"}, {"email": "c@d.com"}]}
        result = await analyzer.analyze(data)
        assert result.content_type == ContentType.APPLICATION_JSON

    @pytest.mark.asyncio
    async def test_non_string_values_skipped(self):
        from anonreq.multimodal.json_analyzer import JsonAnalyzer

        engine = AsyncMock()
        engine.analyze_text = AsyncMock(return_value=[])

        analyzer = JsonAnalyzer(detection_engine=engine)
        data = {"count": 42, "active": True, "data": None, "price": 19.99}
        result = await analyzer.analyze(data)
        assert len(result.entities) == 0
        engine.analyze_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_depth_stops_recursion(self, mock_detection_engine):
        from anonreq.multimodal.json_analyzer import JsonAnalyzer

        analyzer = JsonAnalyzer(detection_engine=mock_detection_engine, max_depth=2)
        data = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        result = await analyzer.analyze(data)
        assert result.content_type == ContentType.APPLICATION_JSON

    @pytest.mark.asyncio
    async def test_malformed_json_returns_error_result(self):
        from anonreq.multimodal.json_analyzer import JsonAnalyzer

        analyzer = JsonAnalyzer()
        result = await analyzer.analyze("{invalid json}")
        assert result.content_type == ContentType.APPLICATION_JSON
        assert "error" in result.analyzer_metadata

    @pytest.mark.asyncio
    async def test_empty_json_object(self):
        from anonreq.multimodal.json_analyzer import JsonAnalyzer

        analyzer = JsonAnalyzer()
        result = await analyzer.analyze({})
        assert result.content_type == ContentType.APPLICATION_JSON
        assert result.entities == []

    @pytest.mark.asyncio
    async def test_sensitive_key_boosts_confidence(self, mock_detection_engine):
        from anonreq.multimodal.json_analyzer import JsonAnalyzer

        analyzer = JsonAnalyzer(detection_engine=mock_detection_engine)
        data = {"ssn": "123-45-6789", "password": "supersecret"}
        result = await analyzer.analyze(data)
        assert result.content_type == ContentType.APPLICATION_JSON

    @pytest.mark.asyncio
    async def test_preserves_input_after_scan(self):
        from anonreq.multimodal.json_analyzer import JsonAnalyzer

        analyzer = JsonAnalyzer()
        data = {"name": "John", "items": [1, 2, 3]}
        original = json.dumps(data, sort_keys=True)
        await analyzer.analyze(data)
        assert json.dumps(data, sort_keys=True) == original

    @pytest.mark.asyncio
    async def test_analyze_with_json_string(self, mock_detection_engine):
        from anonreq.multimodal.json_analyzer import JsonAnalyzer

        analyzer = JsonAnalyzer(detection_engine=mock_detection_engine)
        result = await analyzer.analyze('{"name": "John Doe"}')
        assert result.content_type == ContentType.APPLICATION_JSON
        assert len(result.entities) >= 1

    @pytest.mark.asyncio
    async def test_analyze_with_json_bytes(self, mock_detection_engine):
        from anonreq.multimodal.json_analyzer import JsonAnalyzer

        analyzer = JsonAnalyzer(detection_engine=mock_detection_engine)
        result = await analyzer.analyze(b'{"email": "john@example.com"}')
        assert result.content_type == ContentType.APPLICATION_JSON
        assert len(result.entities) >= 1
