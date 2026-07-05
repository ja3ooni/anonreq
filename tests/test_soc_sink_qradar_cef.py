"""Tests for QRadar CEF SIEM sink.

Tests for:
- CEF header format: CEF:0|AnonReq|Appliance|{version}|{sig_id}|{name}|{sev}
- Extension key=value pairs
- Syslog send over TCP/UDP
- Health check (connection probe)
"""

from __future__ import annotations

import asyncio

import pytest

from anonreq.soc.event import NormalizedEvent, SeverityLevel


def _make_event(
    event_type: str = "dlp_alert",
    mitre_id: str = "T1048",
    severity: SeverityLevel = SeverityLevel.CRITICAL,
) -> NormalizedEvent:
    return NormalizedEvent(
        severity=severity,
        event_type=event_type,
        tenant_id="tenant-xyz",
        session_id="sess-456",
        timestamp="2026-06-26T14:30:00.123456Z",
        gateway_version="1.5.0",
        appliance_instance_id="anonreq-fra-1b",
        mitre_technique_id=mitre_id,
        metadata={"dlp_category": "credential", "risk_score": 0.99},
    )


class TestQRadarCEFFormat:
    """Tests for QRadarCEFSink.format_event()."""

    @pytest.mark.asyncio
    async def test_format_cef_header(self):
        """CEF header format: CEF:0|AnonReq|Appliance|{version}|{sig}|{name}|{sev}."""
        from anonreq.soc.sinks.qradar_cef import QRadarCEFSink

        sink = QRadarCEFSink(
            name="qradar_test",
            host="127.0.0.1",
            port=514,
            use_tcp=True,
        )
        await sink.start()

        try:
            event = _make_event()
            cef_line = await sink.format_event(event)
            parts = cef_line.split("|")

            assert parts[0] == "CEF:0"
            assert parts[1] == "AnonReq"
            assert parts[2] == "Appliance"
            assert parts[3] == "1.5.0"
            assert parts[4] == "T1048"
            assert parts[5] == "dlp_alert"
            assert parts[6].strip().split(" ")[0] == "10"
            # Loss-less severity mapping: CRITICAL → 10
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_severity_mapping(self):
        """CEF severity values 1-10 based on NormalizedEvent severity."""
        from anonreq.soc.sinks.qradar_cef import QRadarCEFSink

        sink = QRadarCEFSink(
            name="qradar_test", host="127.0.0.1", port=514, use_tcp=True
        )
        await sink.start()

        test_cases = [
            (SeverityLevel.CRITICAL, "10"),
            (SeverityLevel.HIGH, "8"),
            (SeverityLevel.MEDIUM, "5"),
            (SeverityLevel.LOW, "2"),
            (SeverityLevel.INFORMATIONAL, "1"),
        ]
        try:
            for sev, expected in test_cases:
                event = _make_event(severity=sev)
                cef_line = await sink.format_event(event)
                parts = cef_line.split("|")
                cef_severity = parts[6].strip().split(" ")[0]
                assert (
                    cef_severity == expected
                ), f"Severity {sev} expected CEF severity {expected}, got {cef_severity}"
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_cef_header_has_exactly_seven_pipes(self):
        """CEF header is a 7-pipe-delimited field: version, device vendor, product, version, sig id, name, sev."""
        from anonreq.soc.sinks.qradar_cef import QRadarCEFSink

        sink = QRadarCEFSink(
            name="qradar_test", host="127.0.0.1", port=514, use_tcp=True
        )
        await sink.start()

        try:
            event = _make_event()
            cef_line = await sink.format_event(event)
            # Header ends at the 7th pipe (seventh field)
            prefix = cef_line.split(" ")[0]
            header_parts = prefix.split("|")
            assert len(header_parts) == 7
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_cef_extensions_present(self):
        """CEF extensions include key=value pairs for event metadata."""
        from anonreq.soc.sinks.qradar_cef import QRadarCEFSink

        sink = QRadarCEFSink(
            name="qradar_test",
            host="127.0.0.1",
            port=514,
            use_tcp=True,
        )
        await sink.start()

        try:
            event = _make_event()
            cef_line = await sink.format_event(event)

            # Extensions are after the header (after space)
            assert "tenantId=" in cef_line
            assert "sessionId=" in cef_line
            assert "mitreTechniqueId=" in cef_line
            assert "gatewayVersion=" in cef_line
            assert "applianceId=" in cef_line
            assert "dlpCategory=" in cef_line
        finally:
            await sink.stop()

    @pytest.mark.asyncio
    async def test_empty_metadata(self):
        """format_event handles events with empty metadata gracefully."""
        from anonreq.soc.sinks.qradar_cef import QRadarCEFSink

        sink = QRadarCEFSink(
            name="qradar_test",
            host="127.0.0.1",
            port=514,
            use_tcp=True,
        )
        await sink.start()

        try:
            event = NormalizedEvent(
                severity=SeverityLevel.INFORMATIONAL,
                event_type="heartbeat",
                tenant_id="tenant-abc",
                session_id="sess-123",
                timestamp="2026-06-26T14:30:00.123456Z",
                gateway_version="1.5.0",
                appliance_instance_id="anonreq-test-1",
                mitre_technique_id=None,
                metadata={},
            )
            cef_line = await sink.format_event(event)
            parts = cef_line.split("|")
            assert parts[4] == "0"  # Unknown sig_id
            header_end = parts[5].strip()
            event_name = header_end.split(" ")[0]
            assert event_name == "heartbeat"
        finally:
            await sink.stop()


class TestQRadarCEFSend:
    """Tests for QRadarCEFSink.send_event()."""

    @pytest.mark.asyncio
    async def test_send_event_over_tcp(self):
        """send_event sends CEF message as TCP syslog to configured host:port."""
        from anonreq.soc.sinks.qradar_cef import QRadarCEFSink

        server_data = []

        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            data = await reader.readuntil(b"\n")
            server_data.append(data)
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        addr = server.sockets[0].getsockname()

        sink = QRadarCEFSink(
            name="qradar_test",
            host="127.0.0.1",
            port=addr[1],
            use_tcp=True,
        )
        await sink.start()

        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is True

            # Give server time to receive
            await asyncio.sleep(0.05)

            assert len(server_data) == 1
            msg = server_data[0].decode("utf-8")
            assert msg.startswith("CEF:0|AnonReq|Appliance|")
            assert b"\n" in server_data[0]
        finally:
            await sink.stop()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_send_event_connection_refused(self):
        """send_event returns False when connection is refused."""
        from anonreq.soc.sinks.qradar_cef import QRadarCEFSink

        sink = QRadarCEFSink(
            name="qradar_test",
            host="127.0.0.1",
            port=11999,
            use_tcp=True,
        )
        await sink.start()

        try:
            event = _make_event()
            result = await sink.send_event(event)
            assert result is False
        finally:
            await sink.stop()


class TestQRadarCEFHealth:
    """Tests for QRadarCEFSink.health_check()."""

    @pytest.mark.asyncio
    async def test_health_check_tcp_connection(self):
        """health_check connects to host:port to verify reachability."""
        from anonreq.soc.sinks.qradar_cef import QRadarCEFSink

        server = await asyncio.start_server(
            lambda r, w: None, "127.0.0.1", 0
        )
        addr = server.sockets[0].getsockname()

        sink = QRadarCEFSink(
            name="qradar_test",
            host="127.0.0.1",
            port=addr[1],
            use_tcp=True,
        )
        await sink.start()

        try:
            status = await sink.health_check()
            assert status.healthy is True
            assert status.reachable is True
        finally:
            await sink.stop()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_health_check_unreachable(self):
        """health_check returns unhealthy when host:port is unreachable."""
        from anonreq.soc.sinks.qradar_cef import QRadarCEFSink

        sink = QRadarCEFSink(
            name="qradar_test",
            host="127.0.0.1",
            port=11998,
            use_tcp=True,
        )
        await sink.start()

        try:
            status = await sink.health_check()
            assert status.healthy is False
            assert status.reachable is False
        finally:
            await sink.stop()
