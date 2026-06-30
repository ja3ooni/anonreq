"""Configuration module for the AnonReq gateway.

Uses Pydantic Settings v2 to load configuration from environment variables
and a YAML-based provider capability registry. All env vars use the
ANONREQ_ prefix.

Per D-07, D-08, D-09, D-10:
- Required vars are validated at import time (fail-secure startup)
- Optional vars have documented defaults
- Unknown vars are silently ignored (extra='ignore')
- YAML safe_load prevents code injection
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All environment variables must be prefixed with ``ANONREQ_``.
    Required variables are validated at instantiation time — if any
    required variable is missing, startup fails with a clear error
    message (D-10 fail-secure startup).

    Attributes:
        API_KEY: API authentication key (min 32 characters, required).
        VALKEY_URL: Valkey/Redis connection URL (required).
        PRESIDIO_URL: Presidio Analyzer base URL (required).
        HOST: Bind address (default: 0.0.0.0).
        PORT: Listen port (default: 8080).
        LOG_LEVEL: Logging level (default: INFO).
        REQUEST_TIMEOUT_SECONDS: Upstream request timeout (default: 30).
    """

    model_config = SettingsConfigDict(
        env_prefix="ANONREQ_",
        extra="ignore",
    )

    # Required fields
    API_KEY: str = Field(min_length=32, validation_alias="ANONREQ_API_KEY")
    VALKEY_URL: str = Field(validation_alias="ANONREQ_VALKEY_URL")
    PRESIDIO_URL: str = Field(validation_alias="ANONREQ_PRESIDIO_URL")

    # Optional fields with defaults
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    LOG_LEVEL: str = "INFO"
    REQUEST_TIMEOUT_SECONDS: int = 30

    @field_validator("API_KEY", mode="before")
    @classmethod
    def validate_api_key_length(cls, v: Any) -> str:
        """Validate that the API key meets minimum length requirement.

        Raises:
            ValueError: If the key is not a string or is shorter than 32 chars.
        """
        if not isinstance(v, str):
            raise ValueError("API_KEY must be a string")
        if len(v) < 32:
            raise ValueError(
                f"API_KEY must be at least 32 characters long (got {len(v)})"
            )
        return v


settings = Settings()
"""Module-level settings singleton.

Instantiated at import time to enforce fail-secure startup validation.
Will raise ``ValidationError`` if required environment variables are
missing, preventing the application from starting with an invalid
configuration.
"""


def load_provider_registry() -> dict[str, Any]:
    """Load the YAML-based provider capability registry.

    Reads ``config/providers.yaml`` and returns the parsed content as a
    Python dictionary. Uses ``yaml.safe_load()`` to prevent arbitrary code
    execution from untrusted YAML (per T-01-01-02 in the threat model).

    Returns:
        A dict with at least a ``providers`` key.
    """
    config_path = Path("config/providers.yaml")
    if not config_path.exists():
        return {"providers": {}}
    with open(config_path) as f:
        return yaml.safe_load(f)
