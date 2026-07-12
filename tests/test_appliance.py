"""Tests for the Appliance Management Agent.

Tests verify:
- ApplianceAgent creation and config loading
- get_health returns correct keys and structure
- get_config returns configuration (secrets redacted)
- update_config validates changes before writing
- get_status returns summary info
- get_logs returns log output
- restart_service returns correct status
- update (image tag) flow with status tracking
- Error handling when Docker is unreachable

All Docker CLI calls are mocked using ``unittest.mock``.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from anonreq.appliance.agent import ApplianceAgent, ApplianceConfig


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def agent(temp_config_dir):
    """Create an ApplianceAgent with a temp config path."""
    return ApplianceAgent(config_path=temp_config_dir)


class TestApplianceAgentInit:
    """Tests for ApplianceAgent initialization."""

    def test_creates_with_default_config(self):
        agent = ApplianceAgent(config_path="/tmp/nonexistent")
        assert isinstance(agent.config, ApplianceConfig)
        assert agent.config.compose_dir == "/opt/anonreq"

    def test_creates_with_temp_config(self, temp_config_dir):
        agent = ApplianceAgent(config_path=temp_config_dir)
        assert agent.config_path == temp_config_dir
        assert isinstance(agent.config, ApplianceConfig)

    def test_loads_config_from_file(self, temp_config_dir):
        config_data = {
            "compose_dir": "/custom/anonreq",
            "compose_file": "/custom/anonreq/docker-compose.yml",
            "services": ["anonreq", "valkey", "minio"],
        }
        config_file = Path(temp_config_dir) / "config.json"
        config_file.write_text(json.dumps(config_data))

        agent = ApplianceAgent(config_path=temp_config_dir)
        assert agent.config.compose_dir == "/custom/anonreq"
        assert "minio" in agent.config.services

    def test_config_path_is_directory(self, temp_config_dir):
        """If config_path is a directory, it looks for config.json inside."""
        config_file = Path(temp_config_dir) / "config.json"
        config_file.write_text(json.dumps({"data_dir": "/custom/data"}))

        agent = ApplianceAgent(config_path=temp_config_dir)
        assert agent.config.data_dir == "/custom/data"


class TestApplianceAgentGetHealth:
    """Tests for get_health method."""

    @patch("anonreq.appliance.agent.ApplianceAgent._check_service_status")
    def test_get_health_returns_expected_keys(self, mock_check, agent):
        mock_check.return_value = [{"name": "anonreq", "status": "running"}]
        health = await_call(agent.get_health())

        assert "services" in health
        assert "disk" in health
        assert "memory" in health
        assert "uptime_seconds" in health
        assert "docker_available" in health

    @patch("anonreq.appliance.agent.ApplianceAgent._check_service_status")
    def test_get_health_service_status(self, mock_check, agent):
        expected = [{"name": "anonreq", "status": "running"}]
        mock_check.return_value = expected
        health = await_call(agent.get_health())
        assert health["services"] == expected

    @patch("anonreq.appliance.agent.ApplianceAgent._check_service_status")
    def test_get_health_uptime_non_negative(self, mock_check, agent):
        mock_check.return_value = []
        health = await_call(agent.get_health())
        assert health["uptime_seconds"] >= 0.0


class TestApplianceAgentGetConfig:
    """Tests for get_config method."""

    def test_get_config_returns_config_keys(self, agent):
        config = await_call(agent.get_config())
        assert "compose_dir" in config
        assert "compose_file" in config
        assert "env_file" in config
        assert "data_dir" in config
        assert "log_dir" in config
        assert "services" in config
        assert "docker_available" in config

    def test_get_config_returns_configured_values(self, temp_config_dir):
        config_file = Path(temp_config_dir) / "config.json"
        config_file.write_text(json.dumps({"data_dir": "/var/data/anonreq"}))
        agent = ApplianceAgent(config_path=temp_config_dir)
        config = await_call(agent.get_config())
        assert config["data_dir"] == "/var/data/anonreq"


class TestApplianceAgentUpdateConfig:
    """Tests for update_config method."""

    def test_update_config_returns_updated(self, agent):
        result = await_call(agent.update_config({"data_dir": "/new/data"}))
        assert result["status"] == "updated"
        assert result["restart_required"] is True

    def test_update_config_rejects_invalid_keys(self, agent):
        with pytest.raises(ValueError, match="Invalid config keys"):
            await_call(agent.update_config({"invalid_key": "value"}))

    def test_update_config_rejects_invalid_services(self, agent):
        with pytest.raises(ValueError, match="services must be a non-empty list"):
            await_call(agent.update_config({"services": []}))

    def test_update_config_rejects_non_string_service(self, agent):
        with pytest.raises(ValueError, match="Invalid service name"):
            await_call(agent.update_config({"services": [123]}))

    def test_update_config_persists_to_disk(self, temp_config_dir):
        agent = ApplianceAgent(config_path=temp_config_dir)
        await_call(agent.update_config({"data_dir": "/persisted/data"}))

        # Check the file was written
        config_file = Path(temp_config_dir) / "config.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["data_dir"] == "/persisted/data"

    def test_update_config_changes_detected(self, agent):
        result = await_call(agent.update_config({"log_dir": "/new/logs"}))
        assert "log_dir" in result["changes"]

    def test_update_config_only_accepts_valid_keys(self, agent):
        valid_keys = {
            "compose_dir", "compose_file", "env_file",
            "data_dir", "log_dir", "compose_command", "services",
        }
        # Should not raise
        for key in valid_keys:
            value = "/tmp/test" if key != "services" else ["anonreq"]
            result = await_call(agent.update_config({key: value}))
            assert result["status"] == "updated"


class TestApplianceAgentGetStatus:
    """Tests for get_status method."""

    def test_get_status_returns_expected_keys(self, agent):
        status = await_call(agent.get_status())
        assert "mode" in status
        assert "version" in status
        assert "uptime_seconds" in status
        assert "service_count" in status
        assert "services" in status

    def test_get_status_mode_is_appliance(self, agent):
        status = await_call(agent.get_status())
        assert status["mode"] == "appliance"

    def test_get_status_service_count(self, temp_config_dir):
        config_file = Path(temp_config_dir) / "config.json"
        config_file.write_text(json.dumps({"services": ["a", "b", "c"]}))
        agent = ApplianceAgent(config_path=temp_config_dir)
        status = await_call(agent.get_status())
        assert status["service_count"] == 3


class TestApplianceAgentGetLogs:
    """Tests for get_logs method."""

    @patch("anonreq.appliance.agent.ApplianceAgent._run_compose_command")
    def test_get_logs_calls_compose(self, mock_run, agent):
        mock_run.return_value = {
            "returncode": 0,
            "stdout": "line1\nline2\nline3",
            "stderr": "",
        }
        logs = await_call(agent.get_logs(service="anonreq", tail=10))
        assert "line1" in logs
        assert "line2" in logs

    @patch("anonreq.appliance.agent.ApplianceAgent._run_compose_command")
    def test_get_logs_default_service(self, mock_run, agent):
        mock_run.return_value = {
            "returncode": 0,
            "stdout": "test log",
            "stderr": "",
        }
        logs = await_call(agent.get_logs())
        assert logs == "test log"

    @patch("anonreq.appliance.agent.ApplianceAgent._run_compose_command")
    def test_get_logs_error_handling(self, mock_run, agent):
        mock_run.return_value = {
            "returncode": 1,
            "stdout": "",
            "stderr": "Service not found",
        }
        logs = await_call(agent.get_logs(service="nonexistent"))
        assert "Error:" in logs
        assert "Service not found" in logs


class TestApplianceAgentRestartService:
    """Tests for restart_service method."""

    @patch("anonreq.appliance.agent.ApplianceAgent._run_compose_command")
    def test_restart_service_success(self, mock_run, agent):
        mock_run.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
        result = await_call(agent.restart_service(service="anonreq"))
        assert result["status"] == "restarted"
        assert result["service"] == "anonreq"

    @patch("anonreq.appliance.agent.ApplianceAgent._run_compose_command")
    def test_restart_service_error(self, mock_run, agent):
        mock_run.return_value = {
            "returncode": 1,
            "stdout": "",
            "stderr": "Service not running",
        }
        result = await_call(agent.restart_service(service="valkey"))
        assert result["status"] == "error"
        assert "Service not running" in result["error"]

    @patch("anonreq.appliance.agent.ApplianceAgent._run_compose_command")
    def test_restart_default_service(self, mock_run, agent):
        mock_run.return_value = {"returncode": 0, "stdout": "", "stderr": ""}
        result = await_call(agent.restart_service())
        assert result["service"] == "anonreq"


class TestApplianceAgentUpdate:
    """Tests for update method."""

    @patch("anonreq.appliance.agent.ApplianceAgent._run_compose_command")
    @patch("anonreq.appliance.agent.ApplianceAgent._update_compose_image_tag")
    def test_update_success(self, _mock_update_tag, mock_run, agent):  # noqa: PT019
        # First call (pull) succeeds, second call (up) succeeds
        mock_run.side_effect = [
            {"returncode": 0, "stdout": "pull ok", "stderr": ""},
            {"returncode": 0, "stdout": "up ok", "stderr": ""},
        ]
        result = await_call(agent.update(image_tag="ghcr.io/anonreq/gateway:1.2.0"))
        assert result["image_tag"] == "ghcr.io/anonreq/gateway:1.2.0"
        assert result["status"] == "completed"
        assert len(result["steps"]) == 4
        assert result["steps"][-1]["step"] == "verify"

    @patch("anonreq.appliance.agent.ApplianceAgent._run_compose_command")
    def test_update_pull_failure(self, mock_run, agent):
        mock_run.return_value = {
            "returncode": 1,
            "stdout": "",
            "stderr": "Image not found",
        }
        result = await_call(agent.update(image_tag="nonexistent:latest"))
        assert result["status"] == "error"
        assert "Image not found" in result["error"]

    @patch("anonreq.appliance.agent.ApplianceAgent._run_compose_command")
    def test_update_with_actual_tag(self, mock_run, agent):
        mock_run.side_effect = [
            {"returncode": 0, "stdout": "pull ok", "stderr": ""},
            {"returncode": 0, "stdout": "up ok", "stderr": ""},
        ]
        result = await_call(agent.update(image_tag="v2.0.0"))
        assert result["image_tag"] == "v2.0.0"


class TestApplianceAgentRunComposeCommand:
    """Tests for _run_compose_command method."""

    @patch("anonreq.appliance.agent.asyncio.create_subprocess_shell")
    def test_run_compose_success(self, mock_subprocess, agent):
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"stdout output", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        result = await_call(agent._run_compose_command("ps --format json"))
        assert result["returncode"] == 0
        assert "stdout" in result

    @patch("anonreq.appliance.agent.asyncio.create_subprocess_shell")
    def test_run_compose_failure_returns_error(self, mock_subprocess, agent):
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"error message")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        result = await_call(agent._run_compose_command("ps"))
        assert result["returncode"] == 1
        assert "error" in result["stderr"]


class TestApplianceAgentErrorHandling:
    """Tests for error handling when Docker is unreachable."""

    @patch("anonreq.appliance.agent.ApplianceAgent._run_compose_command")
    def test_unreachable_docker(self, mock_run, agent):
        mock_run.return_value = {
            "returncode": -1,
            "stdout": "",
            "stderr": "Cannot connect to the Docker daemon",
        }
        health = await_call(agent.get_health())
        services = health["services"]
        assert len(services) > 0
        assert services[0]["status"] == "unknown"


# ---------------------------------------------------------------------------
# Helper to call async methods in sync tests
# ---------------------------------------------------------------------------

def await_call(coro):
    """Run an async callable synchronously for test convenience."""
    import asyncio
    return asyncio.run(coro)
