"""Tests for Phase 22 SOC runtime wiring — normalizer-to-sink-router integration.

Tests verify:
- SOCNormalizer has sink_router.fan_out registered as a callback
- Publishing a raw event through the normalizer delivers to a fake sink
- Delivered normalized event contains metadata-only fields (no raw content)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from anonreq.soc.event import NormalizedEvent, RawSecurityEvent, SeverityLevel
from anonreq.soc.normalizer import SOCNormalizer
from anonreq.soc.router import SinkRouter


class FakeSink:
    """Minimal sink stub for testing fan-out delivery."""

    def __init__(self) -> None:
        self.events: list[NormalizedEvent] = []
        self.name = "fake_test_sink"
        self.sink_type = "test"
        self.enabled = True

    async def send_event(self, event: NormalizedEvent) -> None:
        self.events.append(event)

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


@pytest.fixture
def mock_mitre_mapper():
    mapper = MagicMock()
    mapper.resolve.return_value = "T9999"
    return mapper


@pytest.fixture
def mock_soc_config():
    from types import SimpleNamespace
    return SimpleNamespace(
        gateway_version="1.5.0",
        appliance_instance_id="test-appliance-01",
        event_bus_maxsize=10000,
    )


@pytest.fixture
def normalizer(mock_mitre_mapper, mock_soc_config):
    return SOCNormalizer(
        mitre_mapper=mock_mitre_mapper,
        config=mock_soc_config,
    )


@pytest.fixture
def sink_router():
    return SinkRouter()


class TestNormalizerSinkRouterWiring:
    """Normalizer registers sink_router.fan_out as a callback."""

    def test_normalizer_has_sink_router_registered(self, normalizer, sink_router):
        normalizer.register_sink_callback("sink_router", sink_router.fan_out)
        assert "sink_router" in normalizer._sink_callbacks
        assert normalizer._sink_callbacks["sink_router"] == sink_router.fan_out


class TestEndToEndDelivery:
    """Publishing a raw event through normalizer delivers to fake sink."""

    @pytest.mark.asyncio
    async def test_raw_event_delivered_to_fake_sink(
        self, normalizer, sink_router
    ):
        fake_sink = FakeSink()
        sink_router.register(fake_sink)
        normalizer.register_sink_callback("sink_router", sink_router.fan_out)

        raw = RawSecurityEvent(
            source_engine="firewall",
            event_type="test_connection_blocked",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={"ip_address": "10.0.0.55", "action": "blocked", "severity": "high"},
            timestamp=datetime.now(UTC).isoformat(),
        )

        normalizer.publish_raw(raw)
        await normalizer._consume_one()

        assert len(fake_sink.events) == 1
        delivered = fake_sink.events[0]
        assert isinstance(delivered, NormalizedEvent)
        assert delivered.event_type == "test_connection_blocked"
        assert delivered.severity == SeverityLevel.HIGH

    @pytest.mark.asyncio
    async def test_multiple_events_sequentially(
        self, normalizer, sink_router
    ):
        fake_sink = FakeSink()
        sink_router.register(fake_sink)
        normalizer.register_sink_callback("sink_router", sink_router.fan_out)

        raw1 = RawSecurityEvent(
            source_engine="dlp",
            event_type="dlp_violation",
            tenant_id="t1",
            session_id="s1",
            content={"rule": "pci-01", "severity": "critical"},
        )
        raw2 = RawSecurityEvent(
            source_engine="firewall",
            event_type="port_scan",
            tenant_id="t2",
            session_id="s2",
            content={"source_ip": "10.0.0.1", "severity": "medium"},
        )

        normalizer.publish_raw(raw1)
        await normalizer._consume_one()
        normalizer.publish_raw(raw2)
        await normalizer._consume_one()

        assert len(fake_sink.events) == 2
        assert fake_sink.events[0].event_type == "dlp_violation"
        assert fake_sink.events[1].event_type == "port_scan"


class TestMetadataOnlyDelivery:
    """Delivered normalized event excludes raw content fields."""

    FORBIDDEN_CONTENT_KEYS = {"content", "prompt", "response", "raw_text", "message", "text"}  # noqa: RUF012

    @pytest.mark.asyncio
    async def test_normalized_event_no_raw_content_fields(
        self, normalizer, sink_router
    ):
        fake_sink = FakeSink()
        sink_router.register(fake_sink)
        normalizer.register_sink_callback("sink_router", sink_router.fan_out)

        raw = RawSecurityEvent(
            source_engine="test",
            event_type="test_event",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={
                "ip_address": "10.0.0.1",
                "user_agent": "curl/8.0",
                "rule_id": "rule-42",
            },
        )

        normalizer.publish_raw(raw)
        await normalizer._consume_one()

        assert len(fake_sink.events) == 1
        delivered = fake_sink.events[0]

        metadata = delivered.metadata if hasattr(delivered, "metadata") else {}

        for key in self.FORBIDDEN_CONTENT_KEYS:
            assert key not in metadata, f"Forbidden key '{key}' found in metadata"

        assert delivered.metadata.get("ip_address") == "10.0.0.1"
        assert delivered.metadata.get("rule_id") == "rule-42"

    @pytest.mark.asyncio
    async def test_event_with_content_fields_is_dropped(
        self, normalizer, sink_router
    ):
        fake_sink = FakeSink()
        sink_router.register(fake_sink)
        normalizer.register_sink_callback("sink_router", sink_router.fan_out)

        raw = RawSecurityEvent(
            source_engine="test",
            event_type="test_event",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={
                "content": "secret prompt text",
                "ip_address": "10.0.0.1",
            },
        )

        normalizer.publish_raw(raw)
        await normalizer._consume_one()

        assert len(fake_sink.events) == 0
