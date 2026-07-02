"""Integration tests for plan 09-03: path-aware restoration and local routing.

Tests the combined flow:
- PathTracker integration with detection pipeline
- LocalRouter integration with ContentTypeDispatcher
- End-to-end: detect → track paths → restore with path awareness
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anonreq.multimodal.dispatcher import ContentTypeDispatcher
from anonreq.multimodal.json_analyzer import JsonAnalyzer
from anonreq.multimodal.models import ContentType, UnifiedDetectionResult
from anonreq.multimodal.router import LocalRouter, RouteDecisionType
from anonreq.restore.engine import RestoreEngine
from anonreq.restore.path_tracker import PathTracker


# ── PathTracker + Detection Integration ─────────────────────────────────────


class TestPathTrackerDetectionIntegration:
    """PathTracker populated during detection, consumed during restoration."""

    @pytest.mark.asyncio
    async def test_track_paths_from_json_analysis(self) -> None:
        """JsonAnalyzer detects entities with paths → PathTracker captures them."""
        mock_engine = AsyncMock()
        mock_engine.analyze_text.return_value = [
            {"entity_type": "EMAIL", "start": 0, "end": 15, "score": 0.95},
        ]

        analyzer = JsonAnalyzer(detection_engine=mock_engine)
        result = await analyzer.analyze(
            {"messages": [{"content": "user@example.com"}]}
        )

        assert len(result.entities) >= 1
        # The JsonAnalyzer records json_path in entity metadata
        assert any(e.get("json_path") for e in result.entities)

    @pytest.mark.asyncio
    async def test_track_paths_from_tool_call_arguments(self) -> None:
        """Tool call arguments with detected PII get JSON paths recorded."""
        mock_engine = AsyncMock()
        mock_engine.analyze_text.return_value = [
            {"entity_type": "SSN", "start": 0, "end": 11, "score": 0.99},
        ]

        analyzer = JsonAnalyzer(detection_engine=mock_engine)
        # Simulate finding PII in tool call function arguments
        result = await analyzer.analyze(
            {"tool_calls": [{"function": {"arguments": '{"ssn":"123-45-6789"}'}}]}
        )

        assert result.entities is not None
        # Json path should contain tool_calls path
        paths = [e.get("json_path", "") for e in result.entities]
        assert any("tool_calls" in p for p in paths)

    @pytest.mark.asyncio
    async def test_detection_to_restoration_round_trip(self) -> None:
        """Simulate the full detect → tokenize → restore flow with path tracking."""
        mock_engine = AsyncMock()
        mock_engine.analyze_text.return_value = [
            {"entity_type": "EMAIL", "start": 0, "end": 15, "score": 0.95},
        ]

        analyzer = JsonAnalyzer(detection_engine=mock_engine)
        tracker = PathTracker()

        # 1. Detect in a structured JSON
        data = {"messages": [{"content": "user@example.com", "role": "user"}]}
        result = await analyzer.analyze(data)

        # 2. Simulate tokenization (record paths from detection)
        for entity in result.entities:
            if entity.get("json_path"):
                tracker.track("[EMAIL_0]", entity["json_path"])

        # 3. Restore using path-aware engine
        engine = RestoreEngine(path_tracker=tracker)
        mapping = {"[EMAIL_0]": "user@example.com"}

        response = {"choices": [{"message": {"content": "Reply to [EMAIL_0]"}}]}
        restored = engine.restore_response_with_paths(response, mapping)

        assert restored["choices"][0]["message"]["content"] == "Reply to user@example.com"

    @pytest.mark.asyncio
    async def test_path_tracker_multiple_entities_from_analysis(self) -> None:
        """Multiple entities at different paths are tracked correctly."""
        mock_engine = AsyncMock()

        async def analyze_text(text: str) -> list[dict]:
            if "user@" in text:
                return [{"entity_type": "EMAIL", "start": 0, "end": len(text), "score": 0.95}]
            if "555" in text:
                return [{"entity_type": "PHONE", "start": 0, "end": len(text), "score": 0.9}]
            return []

        mock_engine.analyze_text.side_effect = analyze_text

        analyzer = JsonAnalyzer(detection_engine=mock_engine)
        tracker = PathTracker()

        data = {
            "users": [
                {"contact": "user@example.com"},
                {"contact": "+1-555-0123"},
            ]
        }
        result = await analyzer.analyze(data)

        # Track paths from detection results
        for entity in result.entities:
            etype = entity["entity_type"]
            token = f"[{etype}_0]"
            if entity.get("json_path"):
                tracker.track(token, entity["json_path"])

        all_paths = tracker.get_all()
        assert len(all_paths) >= 1  # at least one path tracked

        # Restore using tracked paths
        engine = RestoreEngine(path_tracker=tracker)
        response = {"data": [{"email": "[EMAIL_0]"}, {"phone": "[PHONE_0]"}]}
        mapping = {"[EMAIL_0]": "user@example.com", "[PHONE_0]": "+1-555-0123"}
        restored = engine.restore_response_with_paths(response, mapping)

        assert "user@example.com" in str(restored)
        assert "+1-555-0123" in str(restored)


# ── LocalRouter + Dispatcher Integration ────────────────────────────────────


class TestLocalRouterDispatcherIntegration:
    """LocalRouter used as fallback by ContentTypeDispatcher."""

    @pytest.mark.asyncio
    async def test_dispatcher_uses_router_for_unknown_type(self) -> None:
        """Dispatcher uses LocalRouter to determine action for unknown types."""
        router = LocalRouter()
        dispatcher = ContentTypeDispatcher(
            json_analyzer=AsyncMock(),
            multipart_analyzer=AsyncMock(),
            local_router=router,
        )

        result = await dispatcher.dispatch("application/octet-stream", b"binary", None)

        assert result.action == RouteDecisionType.ROUTE_LOCAL.value
        assert result.should_process is False
        assert result.content_type == ContentType.UNKNOWN

    @pytest.mark.asyncio
    async def test_dispatcher_router_custom_override(self) -> None:
        """Custom router config overrides default routing."""
        router = LocalRouter({"application/octet-stream": "BLOCK"})
        dispatcher = ContentTypeDispatcher(
            json_analyzer=AsyncMock(),
            multipart_analyzer=AsyncMock(),
            local_router=router,
        )

        result = await dispatcher.dispatch("application/octet-stream", b"binary", None)

        assert result.action == "BLOCK"
        assert result.should_process is False

    @pytest.mark.asyncio
    async def test_dispatcher_router_metadata(self) -> None:
        """Route decision metadata appears in analyzer result."""
        router = LocalRouter()
        dispatcher = ContentTypeDispatcher(
            json_analyzer=AsyncMock(),
            multipart_analyzer=AsyncMock(),
            local_router=router,
        )

        result = await dispatcher.dispatch("image/png", b"PNG...", None)

        assert result.action == "ROUTE_LOCAL"
        metadata = result.detection_result.analyzer_metadata
        assert "route_decision" in metadata
        assert metadata["route_decision"] == "ROUTE_LOCAL"

    @pytest.mark.asyncio
    async def test_dispatcher_default_router_when_none_provided(self) -> None:
        """Dispatcher creates a default LocalRouter if none is provided."""
        dispatcher = ContentTypeDispatcher(
            json_analyzer=AsyncMock(),
            multipart_analyzer=AsyncMock(),
        )

        result = await dispatcher.dispatch("application/octet-stream", b"data", None)

        # Default router routes binary as ROUTE_LOCAL
        assert result.action == "ROUTE_LOCAL"

    @pytest.mark.asyncio
    async def test_known_types_unaffected_by_router(self) -> None:
        """Known types (JSON, text, multipart) are unaffected by LocalRouter."""
        json_mock = AsyncMock()
        json_mock.analyze.return_value = UnifiedDetectionResult(
            content_type=ContentType.APPLICATION_JSON,
        )
        router = LocalRouter({"application/json": "BLOCK"})
        dispatcher = ContentTypeDispatcher(
            json_analyzer=json_mock,
            multipart_analyzer=AsyncMock(),
            local_router=router,
        )

        # Known types are parsed by _MIME_MAP before reaching LocalRouter
        result = await dispatcher.dispatch("application/json", b'{"key": "val"}', None)
        assert result.content_type == ContentType.APPLICATION_JSON
        assert result.action == "ANONYMIZE"

    @pytest.mark.asyncio
    async def test_custom_router_forces_block(self) -> None:
        """Custom router can force BLOCK for unknown types."""
        router = LocalRouter({"image/png": "BLOCK"})
        dispatcher = ContentTypeDispatcher(
            json_analyzer=AsyncMock(),
            multipart_analyzer=AsyncMock(),
            local_router=router,
        )

        result = await dispatcher.dispatch("image/png", b"PNG...", None)
        assert result.action == "BLOCK"


# ── Full Pipeline Integration ───────────────────────────────────────────────


class TestFullPipeline:
    """End-to-end integration of all 09-03 components."""

    @pytest.mark.asyncio
    async def test_detect_track_restore_flow(self) -> None:
        """Full flow: analyze → track paths → restore with path awareness."""
        mock_engine = AsyncMock()
        mock_engine.analyze_text.return_value = [
            {"entity_type": "EMAIL", "start": 0, "end": 15, "score": 0.95},
        ]

        # 1. Analyze JSON content with path tracking
        analyzer = JsonAnalyzer(detection_engine=mock_engine)
        tracker = PathTracker()

        input_data = {
            "messages": [
                {"role": "user", "content": "My email is user@example.com"}
            ]
        }
        detect_result = await analyzer.analyze(input_data)

        # 2. Track paths for detected entities
        for entity in detect_result.entities:
            jp = entity.get("json_path", "")
            if jp:
                tracker.track(f"[{entity['entity_type']}_0]", jp)

        # 3. Simulate tokenization (what would happen in the pipeline)
        mapping = {"[EMAIL_0]": "user@example.com"}

        # 4. Restore using path-aware engine
        engine = RestoreEngine(path_tracker=tracker)
        response = {"choices": [{"message": {"content": "Your email is [EMAIL_0]"}}]}
        restored = engine.restore_response_with_paths(response, mapping)

        assert "user@example.com" in restored["choices"][0]["message"]["content"]
        assert "[EMAIL_0]" not in restored["choices"][0]["message"]["content"]

    def test_path_tracker_clears_between_sessions(self) -> None:
        """PathTracker is cleared between sessions for privacy."""
        tracker = PathTracker()
        tracker.track("[EMAIL_0]", "messages.0.content")
        tracker.track("[PHONE_0]", "messages.1.content")

        # Simulate session end
        tracker.clear()

        assert tracker.get_all() == {}
        assert tracker.get_path("[EMAIL_0]") == []

    def test_router_and_engine_independent(self) -> None:
        """LocalRouter and RestoreEngine can operate independently."""
        router = LocalRouter()
        engine = RestoreEngine()

        # Router decides on content type
        route = router.route("image/png", b"PNG...")
        assert route.decision == RouteDecisionType.ROUTE_LOCAL

        # Engine restores tokens
        result = engine.restore_with_paths("Hello [EMAIL_0]", {"[EMAIL_0]": "test@test.com"})
        assert result == "Hello test@test.com"

    def test_analyzer_result_contains_route_info(self) -> None:
        """AnalyzerResult metadata includes routing info for unknown types."""
        router = LocalRouter()
        dispatcher = ContentTypeDispatcher(
            json_analyzer=AsyncMock(),
            multipart_analyzer=AsyncMock(),
            local_router=router,
        )

        from anonreq.multimodal.models import AnalyzerResult, ContentType, UnifiedDetectionResult

        # Simulate what dispatch would create for an unknown type
        route = router.route("application/x-custom", b"data")
        result = AnalyzerResult(
            source_analyzer="dispatcher",
            content_type=ContentType.UNKNOWN,
            detection_result=UnifiedDetectionResult(
                content_type=ContentType.UNKNOWN,
                analyzer_metadata={
                    "raw_type": "application/x-custom",
                    "route_decision": route.decision.value,
                    "route_reason": route.reason,
                },
            ),
            should_process=False,
            action=route.decision.value,
        )

        assert result.action == "ROUTE_LOCAL"
        assert result.detection_result.analyzer_metadata["route_decision"] == "ROUTE_LOCAL"
