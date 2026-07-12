from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TrustCenterSettings(BaseSettings):
    """Settings loaded from config/trust_center.yaml at app startup."""

    model_config = SettingsConfigDict(
        extra="ignore",
    )

    enabled: bool = False
    display_name: str = "AnonReq Trust Center"
    contact_email: str = "security@example.com"
    logo_url: str = ""
    supported_frameworks: list[str] = Field(
        default_factory=lambda: ["soc2", "iso27001", "gdpr", "hipaa"]
    )
    feature_summary: dict[str, bool] = Field(
        default_factory=lambda: {
            "anonymization": True,
            "dlp": False,
            "firewall": False,
        }
    )
    security_contact: str = "security@example.com"
    certifications: list[dict[str, str]] = Field(default_factory=list)
