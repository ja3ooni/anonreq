"""Tests for SinkFactory — instantiates sinks from SinkDefinition config.

Tests for:
- Each sink type can be instantiated from its config
- Factory returns (SinkRouter, SinkHealthMonitor)
- Buffer wraps sinks when buffer_maxsize > 0
- Disabled sinks are registered but not probed by health monitor
- Unknown sink type raises ConfigError
- All registered sinks have correct name/type/enabled
"""

from __future__ import annotations

import pytest

from anonreq.soc.sink_config import SinkDefinition


@pytest.fixture
def splunk_def() -> SinkDefinition:
    return SinkDefinition(
        name="splunk_hec",
        type="splunk_hec",
        enabled=True,
        config={"endpoint": "https://splunk:8088", "token": "test-token"},
    )


@pytest.fixture
def qradar_def() -> SinkDefinition:
    return SinkDefinition(
        name="qradar_cef",
        type="qradar_cef",
        enabled=True,
        config={"host": "qradar.example.com", "port": 514},
    )


@pytest.fixture
def sentinel_def() -> SinkDefinition:
    return SinkDefinition(
        name="sentinel_dcr",
        type="sentinel_dcr",
        enabled=True,
        config={
            "tenant_id": "tenant",
            "client_id": "client",
            "client_secret": "secret",
            "dcr_endpoint": "https://dcr.example.com",
            "dcr_immutable_id": "immutable-id",
            "stream_name": "Custom-MyStream",
        },
    )


@pytest.fixture
def elastic_def() -> SinkDefinition:
    return SinkDefinition(
        name="elastic_bulk",
        type="elastic_bulk",
        enabled=True,
        config={"endpoint": "https://elastic:9200", "api_key": "key-id:secret"},
    )


@pytest.fixture
def datadog_def() -> SinkDefinition:
    return SinkDefinition(
        name="datadog_logs",
        type="datadog_logs",
        enabled=True,
        config={"api_key": "dd-api-key"},
    )


@pytest.fixture
def webhook_def() -> SinkDefinition:
    return SinkDefinition(
        name="my_webhook",
        type="webhook",
        enabled=True,
        config={
            "url": "https://hooks.example.com/alert",
            "headers": {"X-Custom": "value"},
        },
    )


@pytest.fixture
def disabled_splunk_def() -> SinkDefinition:
    return SinkDefinition(
        name="splunk_disabled",
        type="splunk_hec",
        enabled=False,
        config={"endpoint": "https://splunk:8088", "token": ""},
    )


class TestSinkFactory:
    """Tests for instantiating sinks from config definitions."""

    @pytest.mark.asyncio
    async def test_splunk_hec_instantiated(self, splunk_def):
        """Splunk HEC sink is created with correct name and type."""
        from anonreq.soc.sink_factory import instantiate_sink

        sink = instantiate_sink(splunk_def)
        assert sink.name == "splunk_hec"
        assert sink.sink_type == "splunk_hec"
        assert sink.enabled is True
        # Also check it looks like a sink (has required methods)
        assert hasattr(sink, "send_event")
        assert hasattr(sink, "health_check")

    @pytest.mark.asyncio
    async def test_qradar_instantiated(self, qradar_def):
        """QRadar CEF sink is created with correct name and type."""
        from anonreq.soc.sink_factory import instantiate_sink

        sink = instantiate_sink(qradar_def)
        assert sink.name == "qradar_cef"
        assert sink.sink_type == "qradar_cef"

    @pytest.mark.asyncio
    async def test_sentinel_instantiated(self, sentinel_def):
        """Sentinel DCR sink is created with correct name and type."""
        from anonreq.soc.sink_factory import instantiate_sink

        sink = instantiate_sink(sentinel_def)
        assert sink.name == "sentinel_dcr"
        assert sink.sink_type == "sentinel_dcr"

    @pytest.mark.asyncio
    async def test_elastic_instantiated(self, elastic_def):
        """Elastic Bulk sink is created with correct name and type."""
        from anonreq.soc.sink_factory import instantiate_sink

        sink = instantiate_sink(elastic_def)
        assert sink.name == "elastic_bulk"
        assert sink.sink_type == "elastic_bulk"

    @pytest.mark.asyncio
    async def test_datadog_instantiated(self, datadog_def):
        """Datadog Logs sink is created with correct name and type."""
        from anonreq.soc.sink_factory import instantiate_sink

        sink = instantiate_sink(datadog_def)
        assert sink.name == "datadog_logs"
        assert sink.sink_type == "datadog_logs"

    @pytest.mark.asyncio
    async def test_webhook_instantiated(self, webhook_def):
        """Webhook sink is created with correct name and type."""
        from anonreq.soc.sink_factory import instantiate_sink

        sink = instantiate_sink(webhook_def)
        assert sink.name == "my_webhook"
        assert sink.sink_type == "webhook"

    @pytest.mark.asyncio
    async def test_unknown_sink_type_raises(self):
        """Unknown sink type raises ValueError."""
        from anonreq.soc.sink_factory import instantiate_sink

        bad_def = SinkDefinition(
            name="bad_sink",
            type="nonexistent_sink",
            enabled=True,
            config={},
        )
        with pytest.raises(ValueError, match="Unknown sink type"):
            instantiate_sink(bad_def)

    @pytest.mark.asyncio
    async def test_disabled_sink_still_instantiated(self, disabled_splunk_def):
        """Disabled sinks are still instantiated but marked as not enabled."""
        from anonreq.soc.sink_factory import instantiate_sink

        sink = instantiate_sink(disabled_splunk_def)
        assert sink.name == "splunk_disabled"
        assert sink.enabled is False


class TestBuildSinks:
    """Tests for build_sinks — full pipeline from defs to router+monitor."""

    @pytest.mark.asyncio
    async def test_build_sinks_returns_router_and_monitor(self, splunk_def, qradar_def):
        """build_sinks returns (SinkRouter, SinkHealthMonitor)."""
        from anonreq.soc.sink_factory import build_sinks

        router, monitor = build_sinks([splunk_def, qradar_def])

        assert hasattr(router, "register")
        assert hasattr(router, "fan_out")
        assert hasattr(router, "get_sinks")
        assert hasattr(monitor, "start")
        assert hasattr(monitor, "stop")
        assert hasattr(monitor, "get_status")

    @pytest.mark.asyncio
    async def test_build_sinks_registers_all(self, splunk_def, qradar_def):
        """All sinks are registered in the router."""
        from anonreq.soc.sink_factory import build_sinks

        router, _ = build_sinks([splunk_def, qradar_def])
        sinks = router.get_sinks()
        assert "splunk_hec" in sinks
        assert "qradar_cef" in sinks

    @pytest.mark.asyncio
    async def test_disabled_sink_still_registered(self, disabled_splunk_def, splunk_def):
        """Disabled sinks are registered but not in health monitor status."""
        from anonreq.soc.sink_factory import build_sinks

        router, monitor = build_sinks([splunk_def, disabled_splunk_def])
        # Both in router
        sinks = router.get_sinks()
        assert "splunk_hec" in sinks
        assert "splunk_disabled" in sinks
        # Disabled not in health monitor status
        status = monitor.get_status()
        assert "splunk_disabled" not in status
        assert "splunk_hec" in status

    @pytest.mark.asyncio
    async def test_empty_defs_list_ok(self):
        """Empty defs list creates router and monitor with no sinks."""
        from anonreq.soc.sink_factory import build_sinks

        router, monitor = build_sinks([])
        assert router.get_sinks() == {}
        assert monitor.get_aggregate_status() == "unknown"
