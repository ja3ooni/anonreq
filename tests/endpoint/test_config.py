"""Tests for endpoint agent configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


class TestEndpointConfigDefaults:
    """Test default configuration values."""

    def test_loads_defaults_when_no_file(self):
        """Loading config without a file returns sensible defaults."""
        from anonreq.endpoint.config import EndpointConfig, load_config

        config = load_config()
        assert isinstance(config, EndpointConfig)
        assert config.enabled is True
        assert config.discovery_interval_sec == 30
        assert config.heartbeat_interval_sec == 15
        assert config.gateway_url is None
        assert config.data_dir is not None

    def test_default_bind_address(self):
        """Default API bind address should be localhost for security."""
        from anonreq.endpoint.config import EndpointConfig

        config = EndpointConfig()
        assert config.bind_host == "127.0.0.1"
        assert config.bind_port == 8099

    def test_default_capture_enabled(self):
        """Traffic capture should be enabled by default."""
        from anonreq.endpoint.config import EndpointConfig

        config = EndpointConfig()
        assert config.capture_enabled is True

    def test_discovery_interval_positive(self):
        """Discovery interval must be a positive integer."""
        from anonreq.endpoint.config import EndpointConfig

        config = EndpointConfig()
        assert config.discovery_interval_sec > 0


class TestEndpointConfigYaml:
    """Test YAML configuration loading."""

    def test_loads_from_yaml_file(self, tmp_path: Path):
        """Config loads correctly from a YAML file."""
        from anonreq.endpoint.config import load_config

        config_file = tmp_path / "endpoint.yaml"
        config_file.write_text(yaml.dump({
            "endpoint": {
                "enabled": True,
                "discovery_interval_sec": 60,
                "gateway_url": "ws://gw:8080/ws/endpoint",
                "data_dir": "/opt/anonreq/data",
            }
        }))

        config = load_config(str(config_file))
        assert config.enabled is True
        assert config.discovery_interval_sec == 60
        assert config.gateway_url == "ws://gw:8080/ws/endpoint"
        assert config.data_dir == "/opt/anonreq/data"

    def test_partial_yaml_uses_defaults(self, tmp_path: Path):
        """Partial YAML fills missing fields with defaults."""
        from anonreq.endpoint.config import load_config

        config_file = tmp_path / "endpoint.yaml"
        config_file.write_text(yaml.dump({
            "endpoint": {
                "enabled": False,
            }
        }))

        config = load_config(str(config_file))
        assert config.enabled is False
        assert config.discovery_interval_sec == 30  # default
        assert config.heartbeat_interval_sec == 15  # default

    def test_empty_yaml_uses_defaults(self, tmp_path: Path):
        """Empty or missing endpoint section uses all defaults."""
        from anonreq.endpoint.config import load_config

        config_file = tmp_path / "endpoint.yaml"
        config_file.write_text(yaml.dump({}))

        config = load_config(str(config_file))
        assert isinstance(config, dict) is False  # it's an EndpointConfig
        assert config.enabled is True

    def test_invalid_yaml_raises(self, tmp_path: Path):
        """Invalid YAML content raises a clear error."""
        from anonreq.endpoint.config import EndpointConfigError, load_config

        config_file = tmp_path / "endpoint.yaml"
        config_file.write_text("{invalid: yaml: broken")

        with pytest.raises(EndpointConfigError, match="Failed to parse"):
            load_config(str(config_file))


class TestEndpointConfigFileNotFound:
    """Test behavior when config file doesn't exist."""

    def test_missing_file_returns_defaults(self):
        """Missing config file should return defaults, not crash."""
        from anonreq.endpoint.config import load_config

        config = load_config("/nonexistent/path/endpoint.yaml")
        assert config.enabled is True
        assert config.discovery_interval_sec == 30


class TestEndpointConfigValidation:
    """Test config validation rules."""

    def test_invalid_discovery_interval(self):
        """Discovery interval of 0 or negative raises validation error."""
        from anonreq.endpoint.config import EndpointConfig

        with pytest.raises(ValueError, match="discovery_interval_sec"):
            EndpointConfig(discovery_interval_sec=0)

        with pytest.raises(ValueError, match="discovery_interval_sec"):
            EndpointConfig(discovery_interval_sec=-5)

    def test_invalid_heartbeat_interval(self):
        """Heartbeat interval of 0 or negative raises validation error."""
        from anonreq.endpoint.config import EndpointConfig

        with pytest.raises(ValueError, match="heartbeat_interval_sec"):
            EndpointConfig(heartbeat_interval_sec=0)

        with pytest.raises(ValueError, match="heartbeat_interval_sec"):
            EndpointConfig(heartbeat_interval_sec=-1)
