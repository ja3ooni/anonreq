"""Sink configuration loader with secret resolution.

Per D-025 through D-028:
- Loads ``config/soc-sinks.yaml``
- Resolves ``$env:VAR_NAME`` and ``$file:/path/to/secret`` references
- Validates per-sink required fields
- Returns list of ``SinkDefinition`` dataclass instances
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

logger = logging.getLogger("anonreq.soc.sink_config")

SECRET_ENV_RE = re.compile(r"^\$env:([A-Z_][A-Z0-9_]*)$")
SECRET_FILE_RE = re.compile(r"^\$file:(.+)$")

# Allowed file path prefix for $file: secrets
ALLOWED_SECRET_DIR = "/etc/anonreq/secrets/"


class ConfigError(Exception):
    """Configuration loading or validation error."""


@dataclass
class SinkDefinition:
    """A validated sink configuration definition.

    Attributes:
        name: Unique sink instance name.
        type: Sink type identifier (e.g. ``splunk_hec``, ``sentinel_dcr``).
        enabled: Whether this sink is active on startup.
        config: Dict of type-specific configuration parameters with secrets
            resolved to plaintext values.
        buffer_maxsize: Per-sink buffer maxsize (default 10000).
    """

    name: str
    type: str
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    buffer_maxsize: int = 10000


# Per-sink-type required fields
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "splunk_hec": ["endpoint", "token"],
    "qradar_cef": ["host", "port"],
    "sentinel_dcr": [
        "tenant_id",
        "client_id",
        "client_secret",
        "dcr_endpoint",
        "dcr_immutable_id",
        "stream_name",
    ],
    "elastic_bulk": ["endpoint", "api_key"],
    "datadog_logs": ["api_key"],
    "webhook": ["url"],
}


class SinkConfigLoader:
    """Loads and validates sink configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.
            Defaults to ``"config/soc-sinks.yaml"``.
    """

    def __init__(self, config_path: str = "config/soc-sinks.yaml") -> None:
        self._config_path = config_path

    def load(self) -> list[SinkDefinition]:
        """Load, validate, and resolve secrets for all sink definitions.

        Returns:
            List of ``SinkDefinition`` instances with resolved secrets.

        Raises:
            ConfigError: If the config file cannot be loaded, parsed, or
                if any sink definition fails validation or secret resolution.
        """
        try:
            with open(self._config_path) as f:
                raw: dict[str, Any] = yaml.safe_load(f)
        except FileNotFoundError:
            raise ConfigError(f"Config file not found: {self._config_path}")
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML parse error in {self._config_path}: {e}")

        if raw is None or "sinks" not in raw:
            raise ConfigError("No 'sinks' key found in config")

        definitions: list[SinkDefinition] = []
        for idx, entry in enumerate(raw["sinks"]):
            if not isinstance(entry, dict):
                raise ConfigError(f"Sink entry {idx}: expected a dict, got {type(entry).__name__}")

            name = entry.get("name", f"sink_{idx}")
            sink_type = entry.get("type", "")
            enabled = bool(entry.get("enabled", True))
            buffer_maxsize = int(entry.get("buffer_maxsize", 10000))

            if not sink_type:
                raise ConfigError(f"Sink '{name}': missing 'type' field")

            # Resolve secrets and validate only for enabled sinks
            config: dict[str, Any] = {}
            errors: list[str] = []

            if enabled:
                for key, value in entry.items():
                    if key in ("name", "type", "enabled", "buffer_maxsize"):
                        continue
                    if isinstance(value, str):
                        try:
                            config[key] = self._resolve_secret(value)
                        except ConfigError as e:
                            errors.append(f"  {key}: {e}")
                    elif isinstance(value, dict):
                        # Resolve secrets in nested dict (e.g. headers)
                        resolved = {}
                        for k, v in value.items():
                            if isinstance(v, str):
                                try:
                                    resolved[k] = self._resolve_secret(v)
                                except ConfigError as e:
                                    errors.append(f"  {key}.{k}: {e}")
                            else:
                                resolved[k] = v
                        config[key] = resolved
                    else:
                        config[key] = value

                # Validate required fields for enabled sinks
                validation_errors = self._validate_sink(sink_type, config)
                errors.extend(f"  {e}" for e in validation_errors)
            else:
                # For disabled sinks, pass raw config without resolution
                for key, value in entry.items():
                    if key in ("name", "type", "enabled", "buffer_maxsize"):
                        continue
                    config[key] = value

            if errors:
                error_msg = f"Sink '{name}' ({sink_type}):\n" + "\n".join(errors)
                raise ConfigError(error_msg)

            definitions.append(
                SinkDefinition(
                    name=name,
                    type=sink_type,
                    enabled=enabled,
                    config=config,
                    buffer_maxsize=buffer_maxsize,
                )
            )

        return definitions

    def _resolve_secret(self, value: str) -> str:
        """Resolve a secret reference to its actual value.

        Supports:
        - ``$env:VAR_NAME``: Reads from environment variable.
        - ``$file:/path/to/secret``: Reads from file (restricted to
          ``/etc/anonreq/secrets/``).
        - Any other value: Returned as-is.

        Args:
            value: The value string, possibly a secret reference.

        Returns:
            Resolved value.

        Raises:
            ConfigError: If the referenced secret cannot be resolved.
        """
        # Check $env: reference
        env_match = SECRET_ENV_RE.match(value)
        if env_match:
            var_name = env_match.group(1)
            resolved = os.environ.get(var_name)
            if resolved is None:
                raise ConfigError(
                    f"Environment variable '{var_name}' is not set"
                )
            # Do not log the resolved value — per D-027
            return resolved

        # Check $file: reference
        file_match = SECRET_FILE_RE.match(value)
        if file_match:
            file_path = file_match.group(1)
            # Path traversal check
            if not file_path.startswith(ALLOWED_SECRET_DIR):
                raise ConfigError(
                    f"Secret file path '{file_path}' is not in allowed "
                    f"directory '{ALLOWED_SECRET_DIR}'"
                )
            try:
                with open(file_path) as f:
                    return f.read().strip()
            except FileNotFoundError:
                raise ConfigError(
                    f"Secret file not found: {file_path}"
                )
            except PermissionError:
                raise ConfigError(
                    f"Permission denied reading secret file: {file_path}"
                )

        # Not a secret reference — return as-is
        return value

    @staticmethod
    def _validate_sink(sink_type: str, config: dict[str, Any]) -> list[str]:
        """Validate that all required fields are present for a sink type.

        Args:
            sink_type: The sink type identifier.
            config: Resolved configuration dict.

        Returns:
            List of validation error messages. Empty list if valid.
        """
        errors: list[str] = []
        required = _REQUIRED_FIELDS.get(sink_type, [])
        for field in required:
            if field not in config or config[field] is None or config[field] == "":
                errors.append(f"Missing required field '{field}' for sink type '{sink_type}'")
        return errors
