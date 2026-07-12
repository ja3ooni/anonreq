"""Endpoint agent configuration.

Supports YAML file loading with sensible defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class EndpointConfigError(Exception):
    """Raised when endpoint config cannot be loaded or parsed."""


class EndpointConfig:
    """Configuration for the endpoint agent.

    Args:
        enabled: Whether the agent is active.
        discovery_interval_sec: How often to scan for AI apps (seconds).
        heartbeat_interval_sec: How often to emit heartbeat telemetry (seconds).
        capture_enabled: Whether traffic capture is active.
        capture_interface: Network interface for packet capture.
        gateway_url: Optional WebSocket URL for gateway connection.
        data_dir: Directory for agent data storage.
        bind_host: API bind address.
        bind_port: API bind port.
    """

    __slots__ = (
        "bind_host",
        "bind_port",
        "capture_enabled",
        "capture_interface",
        "data_dir",
        "discovery_interval_sec",
        "enabled",
        "gateway_url",
        "heartbeat_interval_sec",
    )

    def __init__(
        self,
        enabled: bool = True,
        discovery_interval_sec: int = 30,
        heartbeat_interval_sec: int = 15,
        capture_enabled: bool = True,
        capture_interface: str = "en0",
        gateway_url: str | None = None,
        data_dir: str = "/var/lib/anonreq/endpoint",
        bind_host: str = "127.0.0.1",
        bind_port: int = 8099,
    ) -> None:
        # Validate
        if discovery_interval_sec <= 0:
            raise ValueError(
                f"discovery_interval_sec must be positive, got {discovery_interval_sec}"
            )
        if heartbeat_interval_sec <= 0:
            raise ValueError(
                f"heartbeat_interval_sec must be positive, got {heartbeat_interval_sec}"
            )

        self.enabled = enabled
        self.discovery_interval_sec = discovery_interval_sec
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.capture_enabled = capture_enabled
        self.capture_interface = capture_interface
        self.gateway_url = gateway_url
        self.data_dir = data_dir
        self.bind_host = bind_host
        self.bind_port = bind_port

    def __repr__(self) -> str:
        return (
            f"EndpointConfig(enabled={self.enabled}, "
            f"discovery_interval_sec={self.discovery_interval_sec}, "
            f"heartbeat_interval_sec={self.heartbeat_interval_sec})"
        )


def load_config(path: str | None = None) -> EndpointConfig:
    """Load endpoint configuration from YAML file.

    Args:
        path: Path to YAML config file. If None, returns defaults.
            If file doesn't exist, returns defaults.

    Returns:
        EndpointConfig with values from YAML merged over defaults.

    Raises:
        EndpointConfigError: If YAML parsing fails.
    """
    if path is None:
        return EndpointConfig()

    config_path = Path(path)
    if not config_path.exists():
        return EndpointConfig()

    try:
        with open(config_path) as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise EndpointConfigError(f"Failed to parse endpoint config: {e}") from e

    endpoint_raw = raw.get("endpoint", {})
    if not isinstance(endpoint_raw, dict):
        endpoint_raw = {}

    return EndpointConfig(
        enabled=endpoint_raw.get("enabled", True),
        discovery_interval_sec=endpoint_raw.get("discovery_interval_sec", 30),
        heartbeat_interval_sec=endpoint_raw.get("heartbeat_interval_sec", 15),
        capture_enabled=endpoint_raw.get("capture_enabled", True),
        capture_interface=endpoint_raw.get("capture_interface", "en0"),
        gateway_url=endpoint_raw.get("gateway_url"),
        data_dir=endpoint_raw.get("data_dir", "/var/lib/anonreq/endpoint"),
        bind_host=endpoint_raw.get("bind_host", "127.0.0.1"),
        bind_port=endpoint_raw.get("bind_port", 8099),
    )
