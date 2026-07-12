"""Tests for SOC integration status API endpoint.

Tests for:
- GET /v1/admin/soc/integration/status returns 200 with JSON body
- Response includes per-sink status entries
- Response includes aggregate status
- Response includes summary counts (healthy, degraded, unknown)
- Status reflects current health monitor state
- No sinks registered returns unknown aggregate with counts
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from anonreq.soc.sinks import SinkStatus


@pytest.fixture
def healthy_monitor():
    """Create a mock health monitor where all sinks are healthy."""
    monitor = MagicMock()
    statuses = {
        "splunk_hec": SinkStatus(
            healthy=True, reachable=True, last_successful_delivery="2026-07-05T12:00:00+00:00"
        ),
        "qradar_cef": SinkStatus(
            healthy=True, reachable=True, last_successful_delivery="2026-07-05T12:00:00+00:00"
        ),
    }
    monitor.get_status.return_value = statuses
    monitor.get_aggregate_status.return_value = "healthy"
    return monitor


@pytest.fixture
def degraded_monitor():
    """Create a mock health monitor where one sink is unreachable."""
    monitor = MagicMock()
    statuses = {
        "splunk_hec": SinkStatus(
            healthy=True, reachable=True, last_successful_delivery="2026-07-05T12:00:00+00:00"
        ),
        "qradar_cef": SinkStatus(
            healthy=False, reachable=False, last_error="Connection refused"
        ),
    }
    monitor.get_status.return_value = statuses
    monitor.get_aggregate_status.return_value = "degraded"
    return monitor


@pytest.fixture
def empty_monitor():
    """Create a mock health monitor with no sinks."""
    monitor = MagicMock()
    monitor.get_status.return_value = {}
    monitor.get_aggregate_status.return_value = "unknown"
    return monitor


from anonreq.soc.api import create_soc_status_response  # noqa: E402


def _make_test_app(monitor) -> AsyncClient:
    """Create a test app with the SOC status endpoint."""
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/v1/admin/soc/integration/status")
    async def get_status():
        return create_soc_status_response(monitor)

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestSocStatusApi:
    """Tests for the SOC status API endpoint."""

    @pytest.mark.asyncio
    async def test_status_returns_200(self, healthy_monitor):
        """GET /v1/admin/soc/integration/status returns 200."""
        async with _make_test_app(healthy_monitor) as client:
            resp = await client.get("/v1/admin/soc/integration/status")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_status_json_body(self, healthy_monitor):
        """Response is valid JSON with expected top-level keys."""
        async with _make_test_app(healthy_monitor) as client:
            resp = await client.get("/v1/admin/soc/integration/status")
            body = resp.json()
            assert "aggregate_status" in body
            assert "sinks" in body
            assert "summary" in body

    @pytest.mark.asyncio
    async def test_status_includes_per_sink_entries(self, healthy_monitor):
        """Response includes per-sink status entries."""
        async with _make_test_app(healthy_monitor) as client:
            resp = await client.get("/v1/admin/soc/integration/status")
            body = resp.json()
            assert "splunk_hec" in body["sinks"]
            assert "qradar_cef" in body["sinks"]

    @pytest.mark.asyncio
    async def test_status_includes_reachable_flag(self, healthy_monitor):
        """Each sink entry includes reachable flag."""
        async with _make_test_app(healthy_monitor) as client:
            resp = await client.get("/v1/admin/soc/integration/status")
            body = resp.json()
            for _name, entry in body["sinks"].items():
                assert "reachable" in entry
                assert isinstance(entry["reachable"], bool)

    @pytest.mark.asyncio
    async def test_status_includes_aggregate(self, healthy_monitor):
        """Aggregate status is healthy when all reachable."""
        async with _make_test_app(healthy_monitor) as client:
            resp = await client.get("/v1/admin/soc/integration/status")
            body = resp.json()
            assert body["aggregate_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_status_summary_counts(self, healthy_monitor):
        """Summary includes healthy, degraded, and unknown counts."""
        async with _make_test_app(healthy_monitor) as client:
            resp = await client.get("/v1/admin/soc/integration/status")
            body = resp.json()
            assert body["summary"]["healthy"] == 2
            assert body["summary"]["degraded"] == 0
            assert body["summary"]["unknown"] == 0

    @pytest.mark.asyncio
    async def test_status_degraded(self, degraded_monitor):
        """Aggregate is degraded and summary reflects unhealthy sinks."""
        async with _make_test_app(degraded_monitor) as client:
            resp = await client.get("/v1/admin/soc/integration/status")
            body = resp.json()
            assert body["aggregate_status"] == "degraded"
            assert body["summary"]["healthy"] == 1
            assert body["summary"]["degraded"] == 1

    @pytest.mark.asyncio
    async def test_status_empty_sinks(self, empty_monitor):
        """Empty sinks returns unknown aggregate and zero counts."""
        async with _make_test_app(empty_monitor) as client:
            resp = await client.get("/v1/admin/soc/integration/status")
            body = resp.json()
            assert body["aggregate_status"] == "unknown"
            assert body["summary"]["healthy"] == 0
            assert body["summary"]["degraded"] == 0
            assert body["summary"]["unknown"] == 0
            assert body["sinks"] == {}

    @pytest.mark.asyncio
    async def test_status_none_monitor(self):
        """None monitor returns safe defaults."""
        async with _make_test_app(None) as client:
            resp = await client.get("/v1/admin/soc/integration/status")
            body = resp.json()
            assert body["aggregate_status"] == "unknown"
            assert body["summary"]["healthy"] == 0
            assert body["summary"]["degraded"] == 0
            assert body["summary"]["unknown"] == 0
            assert body["sinks"] == {}
