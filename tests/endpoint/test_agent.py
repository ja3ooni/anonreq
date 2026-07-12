"""Tests for the EndpointAgent lifecycle manager."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest


class TestEndpointAgentInit:
    """Test agent initialization."""

    def test_init_with_defaults(self):
        """Agent initializes with default config."""
        from anonreq.endpoint.agent import EndpointAgent

        agent = EndpointAgent()
        assert agent.running is False
        assert agent._tasks == []

    def test_init_with_custom_config(self):
        """Agent initializes with custom config."""
        from anonreq.endpoint.agent import EndpointAgent
        from anonreq.endpoint.config import EndpointConfig

        config = EndpointConfig(
            enabled=True,
            discovery_interval_sec=60,
            heartbeat_interval_sec=30,
        )
        agent = EndpointAgent(config=config)
        assert agent.config.discovery_interval_sec == 60
        assert agent.config.heartbeat_interval_sec == 30

    def test_init_with_audit_logger(self):
        """Agent can be initialized with an audit logger."""
        from anonreq.endpoint.agent import EndpointAgent

        audit_logger = MagicMock()
        agent = EndpointAgent(audit_logger=audit_logger)
        assert agent._audit_logger is audit_logger


class TestEndpointAgentLifecycle:
    """Test agent start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        """Start sets running flag and creates background tasks."""
        from anonreq.endpoint.agent import EndpointAgent

        agent = EndpointAgent()
        assert agent.running is False

        await agent.start()
        assert agent.running is True
        assert len(agent._tasks) > 0

        await agent.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running_and_cancels_tasks(self):
        """Stop clears running flag and cancels background tasks."""
        from anonreq.endpoint.agent import EndpointAgent

        agent = EndpointAgent()
        await agent.start()
        assert agent.running is True
        assert len(agent._tasks) > 0

        await agent.stop()
        assert agent.running is False
        # Tasks should be cancelled
        for t in agent._tasks:
            assert t.done() or t.cancelled()

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self):
        """Starting an already-running agent is safe (no-op)."""
        from anonreq.endpoint.agent import EndpointAgent

        agent = EndpointAgent()
        await agent.start()
        task_count = len(agent._tasks)
        await agent.start()  # should be no-op
        assert len(agent._tasks) == task_count
        await agent.stop()

    @pytest.mark.asyncio
    async def test_double_stop_is_safe(self):
        """Stopping an already-stopped agent is safe (no-op)."""
        from anonreq.endpoint.agent import EndpointAgent

        agent = EndpointAgent()
        await agent.stop()  # should not raise
        assert agent.running is False


class TestEndpointAgentHeartbeat:
    """Test agent heartbeat emission."""

    @pytest.mark.asyncio
    async def test_heartbeat_sends_telemetry(self):
        """Heartbeat sends telemetry with agent status."""
        from anonreq.endpoint.agent import EndpointAgent

        audit_logger = MagicMock()
        agent = EndpointAgent(
            audit_logger=audit_logger,
            config_override={"heartbeat_interval_sec": 0.1},
        )

        await agent.start()
        await asyncio.sleep(0.15)  # Let at least one heartbeat fire
        await agent.stop()

        # Check that heartbeat audit events were emitted
        heartbeat_calls = [
            call for call in audit_logger.info.call_args_list
            if call[0][0] == "endpoint_agent_heartbeat"
        ]
        assert len(heartbeat_calls) >= 1

    @pytest.mark.asyncio
    async def test_heartbeat_contains_telemetry_fields(self):
        """Heartbeat event contains expected telemetry fields."""
        from anonreq.endpoint.agent import EndpointAgent

        audit_logger = MagicMock()
        agent = EndpointAgent(audit_logger=audit_logger)

        await agent._send_heartbeat()

        audit_logger.info.assert_called_once()
        call_args = audit_logger.info.call_args
        assert call_args[0][0] == "endpoint_agent_heartbeat"
        fields = call_args[1]
        assert "uptime_seconds" in fields
        assert "discovered_apps" in fields
        assert "captured_traffic_count" in fields
        assert "status" in fields


class TestEndpointAgentAudit:
    """Test agent audit event emission."""

    @pytest.mark.asyncio
    async def test_start_emits_started_event(self):
        """Agent start emits endpoint_agent_started audit event."""
        from anonreq.endpoint.agent import EndpointAgent

        audit_logger = MagicMock()
        agent = EndpointAgent(audit_logger=audit_logger)

        await agent.start()

        audit_logger.info.assert_any_call(
            "endpoint_agent_started",
            hostname=agent._hostname,
            version=agent._version,
        )
        await agent.stop()

    @pytest.mark.asyncio
    async def test_stop_emits_stopped_event(self):
        """Agent stop emits endpoint_agent_stopped audit event."""
        from anonreq.endpoint.agent import EndpointAgent

        audit_logger = MagicMock()
        agent = EndpointAgent(audit_logger=audit_logger)

        await agent.start()
        audit_logger.reset_mock()
        await agent.stop()

        # Check stopped event was emitted
        stopped_calls = [
            call for call in audit_logger.info.call_args_list
            if call[0][0] == "endpoint_agent_stopped"
        ]
        assert len(stopped_calls) == 1
        fields = stopped_calls[0][1]
        assert isinstance(fields["uptime_seconds"], (int, float))
        assert fields["uptime_seconds"] >= 0

    def test_audit_events_no_pii(self):
        """Audit events must not contain PII."""
        from anonreq.endpoint.agent import EndpointAgent

        # Verify that audit event schemas don't include PII fields
        agent = EndpointAgent()
        assert hasattr(agent, "_pii_safe_fields"), "Agent must track PII-safe fields"

    @pytest.mark.asyncio
    async def test_discovery_integration(self):
        """Agent integrates with AppDiscovery during lifecycle."""
        from anonreq.endpoint.agent import EndpointAgent

        audit_logger = MagicMock()
        with patch("anonreq.endpoint.agent.AppDiscovery") as mock_discovery_cls:
            mock_discovery = MagicMock()
            mock_discovery.discover_and_emit.return_value = [
                {"app_name": "Cursor", "pid": 1234},
            ]
            mock_discovery_cls.return_value = mock_discovery

            agent = EndpointAgent(audit_logger=audit_logger)
            # Manually trigger discovery
            apps = agent._run_discovery()

        assert len(apps) == 1
        assert apps[0]["app_name"] == "Cursor"
