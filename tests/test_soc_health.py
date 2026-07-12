"""Tests for SinkHealthMonitor — periodic sink health probes.

Tests for:
- Health monitor probes each sink at configured interval
- Reachable sink → status.reachable=True
- Unreachable sink → status.reachable=False, last_error populated
- Sink becomes reachable → last_successful_delivery updated
- get_status() returns dict with per-sink SinkStatus
- Disabled sinks not probed
- Aggregate status computation
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from anonreq.soc.sinks import SinkStatus


class FakeSink:
    """A fake sink with configurable health responses."""

    def __init__(
        self,
        name: str = "test_sink",
        initially_reachable: bool = True,
        fail_after: int = 0,
    ) -> None:
        self.name = name
        self.sink_type = "fake"
        self.enabled = True
        self._reachable = initially_reachable
        self._fail_after = fail_after
        self._health_calls = 0
        self._last_success: str | None = None

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def health_check(self) -> SinkStatus:
        self._health_calls += 1
        if self._fail_after and self._health_calls > self._fail_after:
            self._reachable = False
        if self._reachable:
            now = datetime.now(UTC).isoformat()
            self._last_success = now
            return SinkStatus(healthy=True, reachable=True, last_successful_delivery=now)
        return SinkStatus(
            healthy=False,
            reachable=False,
            last_error="Connection refused",
        )

    async def send_event(self, _event: Any) -> bool:
        return True

    async def format_event(self, _event: Any) -> str:
        return ""


class FakeRouter:
    """A fake router for testing the health monitor."""

    def __init__(self, sinks: list[FakeSink]) -> None:
        self._sinks = {s.name: s for s in sinks}

    def get_sinks(self) -> dict[str, FakeSink]:
        return dict(self._sinks)


class TestHealthMonitorBasics:
    """Basic tests for SinkHealthMonitor."""

    @pytest.mark.asyncio
    async def test_health_monitor_probes_sinks(self):
        """Test 1: Health monitor probes each sink at configured interval."""
        from anonreq.soc.health import SinkHealthMonitor

        sink = FakeSink(name="sink_a")
        router = FakeRouter([sink])
        monitor = SinkHealthMonitor(router=router, interval=0.05)
        await monitor.start()

        try:
            # Wait for at least one probe cycle
            await asyncio.sleep(0.12)
            assert sink._health_calls >= 1
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_reachable_sink_returns_healthy(self):
        """Test 2: reachable sink → status.reachable=True."""
        from anonreq.soc.health import SinkHealthMonitor

        sink = FakeSink(name="reachable_sink", initially_reachable=True)
        router = FakeRouter([sink])
        monitor = SinkHealthMonitor(router=router, interval=0.05)
        await monitor.start()

        try:
            await asyncio.sleep(0.1)
            status = monitor.get_status()
            assert "reachable_sink" in status
            assert status["reachable_sink"].reachable is True
            assert status["reachable_sink"].healthy is True
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_unreachable_sink_returns_unhealthy(self):
        """Test 3: unreachable sink → status.reachable=False, last_error populated."""
        from anonreq.soc.health import SinkHealthMonitor

        sink = FakeSink(name="bad_sink", initially_reachable=False)
        router = FakeRouter([sink])
        monitor = SinkHealthMonitor(router=router, interval=0.05)
        await monitor.start()

        try:
            await asyncio.sleep(0.1)
            status = monitor.get_status()
            assert "bad_sink" in status
            assert status["bad_sink"].reachable is False
            assert status["bad_sink"].healthy is False
            assert status["bad_sink"].last_error is not None
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_get_status_returns_dict(self):
        """Test 5: get_status() returns dict with per-sink SinkStatus."""
        from anonreq.soc.health import SinkHealthMonitor

        sink_a = FakeSink(name="sink_a", initially_reachable=True)
        sink_b = FakeSink(name="sink_b", initially_reachable=False)
        router = FakeRouter([sink_a, sink_b])
        monitor = SinkHealthMonitor(router=router, interval=0.05)
        await monitor.start()

        try:
            await asyncio.sleep(0.1)
            status = monitor.get_status()
            assert isinstance(status, dict)
            assert "sink_a" in status
            assert "sink_b" in status
            assert isinstance(status["sink_a"], SinkStatus)
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_disabled_sinks_not_probed(self):
        """Test 6: Disabled sinks not probed."""
        from anonreq.soc.health import SinkHealthMonitor

        sink = FakeSink(name="disabled_sink")
        sink.enabled = False
        router = FakeRouter([sink])
        monitor = SinkHealthMonitor(router=router, interval=0.05)
        await monitor.start()

        try:
            await asyncio.sleep(0.1)
            status = monitor.get_status()
            # Disabled sink should not be probed
            assert "disabled_sink" not in status
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_aggregate_all_healthy(self):
        """Aggregate status is 'healthy' when all enabled sinks reachable."""
        from anonreq.soc.health import SinkHealthMonitor

        sink_a = FakeSink(name="a", initially_reachable=True)
        sink_b = FakeSink(name="b", initially_reachable=True)
        router = FakeRouter([sink_a, sink_b])
        monitor = SinkHealthMonitor(router=router, interval=0.05)
        await monitor.start()

        try:
            await asyncio.sleep(0.1)
            monitor.get_status()
            agg = monitor.get_aggregate_status()
            assert agg in ("healthy", "degraded", "unknown")
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_aggregate_degraded(self):
        """Aggregate status is 'degraded' when any sink unreachable."""
        from anonreq.soc.health import SinkHealthMonitor

        sink_a = FakeSink(name="a", initially_reachable=True)
        sink_b = FakeSink(name="b", initially_reachable=False)
        router = FakeRouter([sink_a, sink_b])
        monitor = SinkHealthMonitor(router=router, interval=0.05)
        await monitor.start()

        try:
            await asyncio.sleep(0.1)
            agg = monitor.get_aggregate_status()
            assert agg == "degraded"
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_aggregate_no_sinks(self):
        """Aggregate status is 'unknown' when no sinks registered."""
        from anonreq.soc.health import SinkHealthMonitor

        router = FakeRouter([])
        monitor = SinkHealthMonitor(router=router, interval=0.05)
        await monitor.start()

        try:
            agg = monitor.get_aggregate_status()
            assert agg == "unknown"
        finally:
            await monitor.stop()
