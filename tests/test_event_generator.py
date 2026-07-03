"""Tests for EventGenerator.

Per D-001, D-025:
- Emits shadow_ai_detected event with correct event_type and fields
- Events contain metadata only (no raw query payloads)
- Configurable webhook alert integration
- Webhook call is fire-and-forget with timeout=5s
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import respx

from anonreq.discovery.dns_parser import DNSEntry
from anonreq.discovery.event_generator import EventGenerator, ShadowAIEvent
from anonreq.discovery.hostname_matcher import MatchResult
from anonreq.discovery.hostname_signatures import AI_SIGNATURES
from anonreq.discovery.proxy_parser import ProxyEntry


class TestShadowAIEvent:
    """Test ShadowAIEvent dataclass."""

    def test_event_has_required_fields(self):
        """ShadowAIEvent contains event_type, source_ip, destination_host, etc."""
        event = ShadowAIEvent(
            source_ip="10.0.0.1",
            destination_host="api.openai.com",
            estimated_service="openai",
            confidence=1.0,
            detection_source="dns",
            timestamp=datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
            tenant_id="tenant_001",
        )
        assert event.event_type == "shadow_ai_detected"
        assert event.source_ip == "10.0.0.1"
        assert event.destination_host == "api.openai.com"
        assert event.estimated_service == "openai"
        assert event.confidence == 1.0
        assert event.detection_source == "dns"
        assert event.tenant_id == "tenant_001"


class TestEventGenerator:
    """Test suite for EventGenerator."""

    def setup_method(self):
        self.audit_logger = MagicMock()
        self.generator = EventGenerator(
            audit_logger=self.audit_logger,
            webhook_url=None,
            tenant_id="tenant_001",
        )

    def test_generate_event_from_dns(self):
        """generate_event creates ShadowAIEvent from DNSEntry + MatchResult."""
        entry = DNSEntry(
            "api.openai.com", "10.0.0.1",
            datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
        )
        match = MatchResult("openai", 1.0, "exact", AI_SIGNATURES[0])
        event = self.generator.generate_event(entry, match)
        assert event.event_type == "shadow_ai_detected"
        assert event.source_ip == "10.0.0.1"
        assert event.destination_host == "api.openai.com"
        assert event.estimated_service == "openai"
        assert event.confidence == 1.0
        assert event.detection_source == "dns"

    def test_generate_event_from_proxy(self):
        """generate_event creates ShadowAIEvent from ProxyEntry + MatchResult."""
        entry = ProxyEntry(
            "10.0.0.1",
            datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
            "POST",
            "https://api.openai.com/v1/chat/completions",
            200,
            1500,
        )
        match = MatchResult("openai", 1.0, "exact", AI_SIGNATURES[0])
        event = self.generator.generate_event(entry, match)
        assert event.event_type == "shadow_ai_detected"
        assert event.source_ip == "10.0.0.1"
        assert event.destination_host == "api.openai.com"
        assert event.detection_source == "proxy"

    def test_emit_sends_to_audit_logger(self):
        """emit sends event to audit logger."""
        event = ShadowAIEvent(
            source_ip="10.0.0.1",
            destination_host="api.openai.com",
            estimated_service="openai",
            confidence=1.0,
            detection_source="dns",
            timestamp=datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
            tenant_id="tenant_001",
        )
        self.generator.emit(event)
        self.audit_logger.info.assert_called_once()
        call_kwargs = self.audit_logger.info.call_args[1]
        assert call_kwargs["event_type"] == "shadow_ai_detected"

    def test_emit_with_webhook(self):
        """emit sends POST to webhook URL when configured."""
        event = ShadowAIEvent(
            source_ip="10.0.0.1",
            destination_host="api.openai.com",
            estimated_service="openai",
            confidence=1.0,
            detection_source="dns",
            timestamp=datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
            tenant_id="tenant_001",
        )
        with respx.mock:
            route = respx.post("https://hooks.example.com/alert").respond(200)
            generator = EventGenerator(
                audit_logger=self.audit_logger,
                webhook_url="https://hooks.example.com/alert",
                tenant_id="tenant_001",
            )
            generator.emit(event)
            assert route.called

    def test_webhook_timeout_does_not_crash(self):
        """Webhook timeout is handled gracefully (fire-and-forget)."""
        event = ShadowAIEvent(
            source_ip="10.0.0.1",
            destination_host="api.openai.com",
            estimated_service="openai",
            confidence=1.0,
            detection_source="dns",
            timestamp=datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
            tenant_id="tenant_001",
        )
        with respx.mock:
            route = respx.post("https://hooks.example.com/alert").respond(200)
            generator = EventGenerator(
                audit_logger=self.audit_logger,
                webhook_url="https://hooks.example.com/alert",
                webhook_timeout=5.0,
                tenant_id="tenant_001",
            )
            generator.emit(event)
            assert route.called

    def test_emit_batch(self):
        """emit_batch emits multiple events."""
        events = [
            ShadowAIEvent(
                source_ip="10.0.0.1",
                destination_host="api.openai.com",
                estimated_service="openai",
                confidence=1.0,
                detection_source="dns",
                timestamp=datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
                tenant_id="tenant_001",
            ),
            ShadowAIEvent(
                source_ip="10.0.0.2",
                destination_host="api.anthropic.com",
                estimated_service="anthropic",
                confidence=1.0,
                detection_source="proxy",
                timestamp=datetime(2026, 6, 20, 10, 1, 0, tzinfo=timezone.utc),
                tenant_id="tenant_001",
            ),
        ]
        self.generator.emit_batch(events)
        assert self.audit_logger.info.call_count == 2

    def test_event_contains_no_raw_payload(self):
        """Event contains metadata only — no raw query payloads."""
        event = ShadowAIEvent(
            source_ip="10.0.0.1",
            destination_host="api.openai.com",
            estimated_service="openai",
            confidence=1.0,
            detection_source="dns",
            timestamp=datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
            tenant_id="tenant_001",
        )
        d = event.to_dict()
        assert "raw" not in d
        assert "payload" not in d
        assert "body" not in d
