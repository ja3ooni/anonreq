"""Configuration module for the AnonReq gateway.

Uses Pydantic Settings v2 to load configuration from environment variables
and a YAML-based provider capability registry. All env vars use the
ANONREQ_ prefix.

Per D-07, D-08, D-09, D-10:
- Required vars are validated at import time (fail-secure startup)
- Optional vars have documented defaults
- Unknown vars are silently ignored (extra='ignore')
- YAML safe_load prevents code injection

Submodules:
- ``restricted_names``: Hot-reloadable tenant restricted-names list (Phase 15)
"""

from __future__ import annotations

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
    PRESIDIO_MAX_CONCURRENCY: int = 10
    CACHE_TTL_SECONDS: int = 300
    PROVIDER_BASE_URL: str = Field(
        default="https://api.openai.com",
        validation_alias="PROVIDER_BASE_URL",
    )
    PROVIDER_API_KEY: str | None = Field(
        default=None,
        validation_alias="PROVIDER_API_KEY",
    )
    ACTIVE_PRESETS: str = ""
    POLICY_CONFIG_PATH: str = Field(
        default="config/enterprise-policy.yaml",
        validation_alias="ANONREQ_POLICY_CONFIG_PATH",
        description="Enterprise PDP policy config path. Kept separate from Appliance PDP2 policy.yaml.",  # noqa: E501
    )
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./anonreq.db",
        validation_alias="ANONREQ_DATABASE_URL",
        description="SQLAlchemy async database URL for audit/governance persistence.",
    )
    ANCHOR_SIGNING_KEY: str | None = Field(
        default=None,
        validation_alias="ANONREQ_ANCHOR_SIGNING_KEY",
        description="Optional HMAC signing key for tamper-evident audit chain anchors.",
    )
    ADMIN_API_KEY: str | None = Field(
        default=None,
        validation_alias="ANONREQ_ADMIN_API_KEY",
        description="Separate API key for admin endpoints. If unset, admin endpoints return 401.",
    )
    ADMIN_ROLE: str = Field(
        default="administrator",
        validation_alias="ANONREQ_ADMIN_ROLE",
        description="Default role assigned to admin API key users.",
    )
    OIDC_ISSUER: str | None = Field(
        default=None,
        validation_alias="ANONREQ_OIDC_ISSUER",
        description="OIDC issuer used to validate admin identity tokens.",
    )
    OIDC_AUDIENCE: str | None = Field(
        default=None,
        validation_alias="ANONREQ_OIDC_AUDIENCE",
        description="Expected OIDC audience for admin identity tokens.",
    )
    OIDC_JWKS_URL: str | None = Field(
        default=None,
        validation_alias="ANONREQ_OIDC_JWKS_URL",
        description="JWKS endpoint used to verify OIDC JWT signatures.",
    )
    OIDC_ROLE_CLAIM: str = Field(
        default="role",
        validation_alias="ANONREQ_OIDC_ROLE_CLAIM",
        description="Claim name used to project validated OIDC identity into role_principal.",
    )
    OIDC_JWKS_CACHE_SECONDS: int = Field(
        default=300,
        validation_alias="ANONREQ_OIDC_JWKS_CACHE_SECONDS",
        description="JWKS cache lifetime in seconds.",
    )
    MTLS_ENFORCE: bool = Field(
        default=False,
        validation_alias="ANONREQ_MTLS_ENFORCE",
        description="Enable ingress-forwarded mTLS validation at the gateway boundary.",
    )
    MTLS_TRUSTED_PROXY_CIDRS: str = Field(
        default="",
        validation_alias="ANONREQ_MTLS_TRUSTED_PROXY_CIDRS",
        description="Comma-separated CIDR allowlist for trusted ingress proxies.",
    )
    MTLS_FORWARD_CERT_HEADER: str = Field(
        default="X-Forwarded-Client-Cert",
        validation_alias="ANONREQ_MTLS_FORWARD_CERT_HEADER",
        description="Header carrying the forwarded client certificate.",
    )
    SECRET_BACKEND: str = Field(
        default="vault",
        validation_alias="ANONREQ_SECRET_BACKEND",
        description="Secret backend used to bootstrap provider credentials at startup.",
    )
    SECRET_BACKEND_PATH: str = Field(
        default="anonreq/provider-api-keys",
        validation_alias="ANONREQ_SECRET_BACKEND_PATH",
        description="Logical path inside the secret backend for provider credentials.",
    )
    SECRET_VOLUME_DIR: str = Field(
        default="config/secrets",
        validation_alias="ANONREQ_SECRET_VOLUME_DIR",
        description="Mounted directory for secret volume reloads.",
    )
    SECRET_VOLUME_FILE: str = Field(
        default="provider-api-keys.json",
        validation_alias="ANONREQ_SECRET_VOLUME_FILE",
        description="Filename inside the secret volume that stores provider credentials.",
    )

    # Phase 17: Universal AI Traffic Gateway settings
    CA_DIR: str = Field(
        default="/etc/anonreq/ca",
        validation_alias="ANONREQ_CA_DIR",
        description="Directory for CA certificate storage.",
    )
    PROXY_MODE: str = Field(
        default="proxy-only",
        validation_alias="ANONREQ_PROXY_MODE",
        description="Proxy mode: proxy-only | transparent | full",
    )
    # Phase 26: Enterprise Guardrails — licensing
    LICENSE_SECRET: str | None = Field(
        default=None,
        validation_alias="ANONREQ_LICENSE_SECRET",
        description=(
            "HMAC-SHA256 signing key for license validation. Required for "
            "Appliance-tier features."
        ),
    )
    LICENSE_KEY: str | None = Field(
        default=None,
        validation_alias="ANONREQ_LICENSE_KEY",
        description="Signed license key payload. Base64-encoded HMAC-SHA256 signed JSON.",
    )
    TENANTS_CONFIG_PATH: str = Field(
        default="config/tenants.yaml",
        validation_alias="ANONREQ_TENANTS_CONFIG_PATH",
        description="Path to the YAML seed file for tenant configuration.",
    )
    KMS_BACKEND: str = Field(
        default="local",
        validation_alias="ANONREQ_KMS_BACKEND",
        description="KMS backend for tenant encryption: local | aws | gcp.",
    )
    METRICS_MAX_TENANTS: int = Field(
        default=100,
        validation_alias="ANONREQ_METRICS_MAX_TENANTS",
        description="Maximum unique tenant labels for Prometheus metrics before _overflow fallback.",
    )

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
        result = yaml.safe_load(f)
        return dict(result) if result is not None else {"providers": {}}
