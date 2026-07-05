"""Tests for SOC event normalizer with content stripping and metadata enrichment.

Tests for:
- Subscription to event bus
- NormalizedEvent contains all 8 required fields
- Content field stripping (content, prompt, response, raw_text removed)
- Content field detection → event dropped + soc_strip_failure audit event
- MITRE mapping application
- TEMP:UNMAPPED fallback
- gateway_version and appliance_instance_id populated from config
- Prometheus counter incremented per event
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from anonreq.soc.event import NormalizedEvent, SeverityLevel, RawSecurityEvent
from anonreq.soc.normalizer import SOCNormalizer, STRIP_FIELDS


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
def mock_audit_logger():
    return AsyncMock()


@pytest.fixture
def mock_metrics():
    from prometheus_client import Counter, REGISTRY
    # Clean up any existing counter
    for name in list(REGISTRY._names_to_collector.keys()):
        if "soc_events_normalized" in name:
            try:
                REGISTRY.unregister(REGISTRY._names_to_collector[name])
            except KeyError:
                pass
    return MagicMock()


class TestSOCNormalizerInit:
    """Tests for SOCNormalizer initialization and event bus."""

    def test_init_creates_event_bus(self, mock_mitre_mapper, mock_soc_config):
        """Test 1: SOCNormalizer creates event bus on init."""
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
        )
        assert normalizer.event_bus is not None
        assert normalizer.event_bus.maxsize == 10000

    def test_subscribe_registers_callback(self, mock_mitre_mapper, mock_soc_config):
        """Test 1 variant: register_sink_callback stores callback."""
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
        )
        callback = AsyncMock()
        normalizer.register_sink_callback("test_sink", callback)
        assert "test_sink" in normalizer._sink_callbacks


class TestSOCNormalizerNormalize:
    """Tests for the _normalize method."""

    @pytest.mark.asyncio
    async def test_normalized_event_has_all_required_fields(self, mock_mitre_mapper, mock_soc_config):
        """Test 2: Normalized event contains all 8 required fields."""
        mock_mitre_mapper.resolve.return_value = "T1048"
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
        )

        raw = RawSecurityEvent(
            source_engine="firewall",
            event_type="firewall_violation",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={"ip_address": "10.0.0.1", "action": "blocked", "severity": "high"},
        )

        ev = await normalizer._normalize(raw)
        assert ev is not None
        assert ev.severity == SeverityLevel.HIGH
        assert ev.event_type == "firewall_violation"
        assert ev.tenant_id == "tenant-abc"
        assert ev.session_id == "sess-123"
        assert ev.timestamp is not None and len(ev.timestamp) > 0
        assert ev.gateway_version == "1.5.0"
        assert ev.appliance_instance_id == "test-appliance-01"
        assert ev.mitre_technique_id == "T1048"

    @pytest.mark.asyncio
    async def test_content_fields_stripped_drops_event(self, mock_mitre_mapper, mock_soc_config):
        """Test 3: Content fields named content, prompt, response, raw_text cause drop."""
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
        )

        raw = RawSecurityEvent(
            source_engine="firewall",
            event_type="test_event",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={
                "content": "raw prompt text",
                "prompt": "another raw",
                "response": "llm output",
                "raw_text": "sensitive data",
            },
        )

        # Per D-012 fail-secure: content field detected → event dropped
        ev = await normalizer._normalize(raw)
        assert ev is None

    @pytest.mark.asyncio
    async def test_content_field_detected_drops_event_with_audit(self, mock_mitre_mapper, mock_soc_config):
        """Test 4: Event with content field detected → event dropped, audit event emitted."""
        mock_audit = AsyncMock()
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
            audit_logger=mock_audit,
        )

        raw = RawSecurityEvent(
            source_engine="firewall",
            event_type="test_event",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={"content": "sensitive prompt", "safe": "data"},
        )

        ev = await normalizer._normalize(raw)
        assert ev is None
        mock_audit.log_event.assert_awaited_once()

        event_args = mock_audit.log_event.call_args
        assert event_args[0][0] == "soc_strip_failure"
        assert event_args[1]["event_type"] == "test_event"
        assert event_args[1]["source_engine"] == "firewall"

    @pytest.mark.asyncio
    async def test_no_content_fields_passes_through(self, mock_mitre_mapper, mock_soc_config):
        """Event without content fields normalizes successfully."""
        mock_audit = AsyncMock()
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
            audit_logger=mock_audit,
        )

        raw = RawSecurityEvent(
            source_engine="firewall",
            event_type="test_event",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={"severity": "high", "ip_address": "10.0.0.1"},
        )

        ev = await normalizer._normalize(raw)
        assert ev is not None
        mock_audit.log_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_mitre_mapping_applied(self, mock_mitre_mapper, mock_soc_config):
        """Test 5: MITRE mapping applied via MITREMapper.resolve()."""
        mock_mitre_mapper.resolve.return_value = "T1190"
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
        )

        raw = RawSecurityEvent(
            source_engine="firewall",
            event_type="firewall_violation",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={},
        )

        ev = await normalizer._normalize(raw)
        assert ev is not None
        assert ev.mitre_technique_id == "T1190"
        mock_mitre_mapper.resolve.assert_called_with("firewall_violation")

    @pytest.mark.asyncio
    async def test_unmapped_event_type_gets_temp_unmapped(self, mock_mitre_mapper, mock_soc_config):
        """Test 6: Unmapped event_type gets TEMP:UNMAPPED."""
        mock_mitre_mapper.resolve.return_value = "TEMP:UNMAPPED"
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
        )

        raw = RawSecurityEvent(
            source_engine="new_engine",
            event_type="brand_new_event",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={},
        )

        ev = await normalizer._normalize(raw)
        assert ev is not None
        assert ev.mitre_technique_id == "TEMP:UNMAPPED"

    @pytest.mark.asyncio
    async def test_gateway_version_and_appliance_instance_populated(self, mock_mitre_mapper, mock_soc_config):
        """Test 7: gateway_version and appliance_instance_id populated from config."""
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
        )

        raw = RawSecurityEvent(
            source_engine="test",
            event_type="test_event",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={},
        )

        ev = await normalizer._normalize(raw)
        assert ev is not None
        assert ev.gateway_version == "1.5.0"
        assert ev.appliance_instance_id == "test-appliance-01"

    @pytest.mark.asyncio
    async def test_severity_propagated_from_content(self, mock_mitre_mapper, mock_soc_config):
        """Severity from raw event content maps to NormalizedEvent severity."""
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
        )

        raw = RawSecurityEvent(
            source_engine="test",
            event_type="test_event",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={"severity": "critical"},
        )

        ev = await normalizer._normalize(raw)
        assert ev is not None
        assert ev.severity == SeverityLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_default_severity_is_informational(self, mock_mitre_mapper, mock_soc_config):
        """Unknown severity in content defaults to informational."""
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
        )

        raw = RawSecurityEvent(
            source_engine="test",
            event_type="test_event",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={},
        )

        ev = await normalizer._normalize(raw)
        assert ev is not None
        assert ev.severity == SeverityLevel.INFORMATIONAL


class TestSOCNormalizerAsync:
    """Tests for async event bus operations."""

    @pytest.mark.asyncio
    async def test_publish_raw_non_blocking(self, mock_mitre_mapper, mock_soc_config):
        """publish_raw puts event on the event bus without blocking."""
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
        )

        raw = RawSecurityEvent(
            source_engine="test",
            event_type="test_event",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={},
        )

        # Should not raise or block
        normalizer.publish_raw(raw)
        assert normalizer.event_bus.qsize() == 1

    @pytest.mark.asyncio
    async def test_consume_loop_normalizes_and_fans_out(self, mock_mitre_mapper, mock_soc_config):
        """Background consume loop normalizes event and fans out to registered sinks."""
        mock_audit = AsyncMock()
        normalizer = SOCNormalizer(
            mitre_mapper=mock_mitre_mapper,
            config=mock_soc_config,
            audit_logger=mock_audit,
        )

        callback = AsyncMock(return_value=True)
        normalizer.register_sink_callback("test_sink", callback)

        raw = RawSecurityEvent(
            source_engine="test",
            event_type="test_event",
            tenant_id="tenant-abc",
            session_id="sess-123",
            content={},
        )

        normalizer.publish_raw(raw)

        # Run consume once
        await normalizer._consume_one()

        callback.assert_awaited_once()
        args = callback.call_args[0]
        assert isinstance(args[0], NormalizedEvent)
        assert args[0].event_type == "test_event"


class TestSTRIP_FIELDS:
    """Test the STRIP_FIELDS constant."""

    def test_content_in_strip_fields(self):
        assert "content" in STRIP_FIELDS
        assert "prompt" in STRIP_FIELDS
        assert "response" in STRIP_FIELDS
        assert "raw_text" in STRIP_FIELDS
        assert "message" in STRIP_FIELDS
        assert "text" in STRIP_FIELDS

    def test_all_lowercase(self):
        for field in STRIP_FIELDS:
            assert field == field.lower()
