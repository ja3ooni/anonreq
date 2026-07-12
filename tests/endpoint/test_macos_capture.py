"""Tests for macOS traffic capture module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestTrafficCaptureInit:
    """Test traffic capture initialization."""

    def test_init_with_defaults(self):
        """Capture initializes with default values."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        capture = TrafficCapture()
        assert capture.interface == "en0"
        assert capture.running is False

    def test_init_with_custom_interface(self):
        """Capture initializes with custom interface."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        capture = TrafficCapture(interface="en1")
        assert capture.interface == "en1"

    def test_init_with_hostname_matcher(self):
        """Capture can be initialized with a hostname matcher."""
        from anonreq.endpoint.discovery import HostnameMatcher
        from anonreq.endpoint.macos.capture import TrafficCapture

        matcher = HostnameMatcher()
        capture = TrafficCapture(matcher=matcher)
        assert capture._matcher is matcher


class TestTrafficCaptureLifecycle:
    """Test traffic capture start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        """Start sets running flag to True."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        capture = TrafficCapture()
        assert capture.running is False

        await capture.start()
        assert capture.running is True
        await capture.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self):
        """Stop sets running flag to False."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        capture = TrafficCapture()
        await capture.start()
        assert capture.running is True

        await capture.stop()
        assert capture.running is False

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self):
        """Starting an already-running capture is safe (no-op)."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        capture = TrafficCapture()
        await capture.start()
        await capture.start()  # should not raise
        assert capture.running is True
        await capture.stop()

    @pytest.mark.asyncio
    async def test_double_stop_is_safe(self):
        """Stopping an already-stopped capture is safe (no-op)."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        capture = TrafficCapture()
        await capture.stop()  # should not raise
        assert capture.running is False

    @pytest.mark.asyncio
    async def test_start_and_stop_emits_audit(self):
        """Start and stop emit audit events."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        audit_logger = MagicMock()
        capture = TrafficCapture(audit_logger=audit_logger)

        await capture.start()
        await capture.stop()

        assert audit_logger.info.call_count >= 2


class TestTrafficCaptureFiltering:
    """Test AI provider traffic filtering."""

    def test_is_ai_traffic_positive(self):
        """Known AI provider hostname is identified as AI traffic."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        capture = TrafficCapture()
        assert capture._is_ai_traffic("api.openai.com") is True
        assert capture._is_ai_traffic("api.anthropic.com") is True
        assert capture._is_ai_traffic("generativelanguage.googleapis.com") is True

    def test_is_ai_traffic_negative(self):
        """Non-AI hostname is not identified as AI traffic."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        capture = TrafficCapture()
        assert capture._is_ai_traffic("example.com") is False
        assert capture._is_ai_traffic("google.com") is False
        assert capture._is_ai_traffic("apple.com") is False

    def test_is_ai_traffic_empty(self):
        """Empty hostname is not AI traffic."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        capture = TrafficCapture()
        assert capture._is_ai_traffic("") is False


class TestTrafficCaptureEvents:
    """Test traffic event emission."""

    def test_emit_traffic_event_schema(self):
        """Traffic event follows expected schema with metadata only."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        audit_logger = MagicMock()
        capture = TrafficCapture(audit_logger=audit_logger)

        capture._emit_traffic_event(
            hostname="api.openai.com",
            provider="openai",
            process_name="Cursor",
            pid=1234,
        )

        audit_logger.info.assert_called_once()
        call_args = audit_logger.info.call_args
        assert call_args[0][0] == "ai_traffic_observed"
        fields = call_args[1]
        assert fields["hostname"] == "api.openai.com"
        assert fields["provider"] == "openai"
        assert fields["process_name"] == "Cursor"
        assert fields["pid"] == 1234
        assert "timestamp" in fields

    def test_emit_traffic_event_no_raw_content(self):
        """Traffic event must not contain raw traffic content."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        audit_logger = MagicMock()
        capture = TrafficCapture(audit_logger=audit_logger)

        capture._emit_traffic_event(
            hostname="api.openai.com",
            provider="openai",
            process_name="Cursor",
            pid=1234,
        )

        call_args = audit_logger.info.call_args
        fields = call_args[1]
        # Must NOT contain raw request/response content
        assert "raw_request" not in fields
        assert "raw_response" not in fields
        assert "payload" not in fields
        assert "body" not in fields

    def test_emit_traffic_event_minimal_fields(self):
        """Traffic event works with minimal fields."""
        from anonreq.endpoint.macos.capture import TrafficCapture

        audit_logger = MagicMock()
        capture = TrafficCapture(audit_logger=audit_logger)

        capture._emit_traffic_event(
            hostname="api.anthropic.com",
            provider="anthropic",
        )

        audit_logger.info.assert_called_once()
        call_args = audit_logger.info.call_args
        fields = call_args[1]
        assert fields["hostname"] == "api.anthropic.com"
        assert fields["provider"] == "anthropic"
        # process_name and pid are optional
        assert "process_name" in fields
        assert "pid" in fields
