"""Licensing settings loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LicenseSettings(BaseSettings):
    """Licensing settings parsing ANONREQ_ LICENSE_SECRET and LICENSE_KEY."""

    model_config = SettingsConfigDict(
        env_prefix="ANONREQ_",
        extra="ignore",
    )

    LICENSE_SECRET: str | None = Field(
        default=None,
        validation_alias="ANONREQ_LICENSE_SECRET",
        description="HMAC-SHA256 signing key for license validation.",
    )

    LICENSE_KEY: str | None = Field(
        default=None,
        validation_alias="ANONREQ_LICENSE_KEY",
        description="Signed license key payload (Base64-encoded HMAC-SHA256 signed JSON).",
    )


license_settings = LicenseSettings()
