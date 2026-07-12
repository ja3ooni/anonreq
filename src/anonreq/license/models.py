"""Licensing data models and schemas.

Per GUARD-03:
- FeatureGate: enum of commercial features
- LicenseKey: custom type for key string
- LicenseTier: free or appliance
- LicensePayload: payload decoded from signed key
- LicenseStatus: current validator validation status
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class FeatureGate(str, Enum):
    """Supported commercial/appliance features."""

    TRUST_CENTER = "trust_center"
    AI_FIREWALL = "ai_firewall"
    SOC_INTEGRATION = "soc_integration"
    ADVANCED_DETECTION = "advanced_detection"
    COMPLIANCE_MONITORING = "compliance_monitoring"


class LicenseKey(str):
    """Custom type representing a raw license key string."""

    pass


class LicenseTier(str, Enum):
    """License tiers."""

    FREE = "free"
    APPLIANCE = "appliance"


class LicensePayload(BaseModel):
    """Payload decoded from the signed license key."""

    org: str
    tier: LicenseTier
    features: list[FeatureGate]
    expires_at: datetime
    issued_at: datetime
    signature: str


class LicenseStatus(BaseModel):
    """Validation status of the license key."""

    valid: bool
    tier: LicenseTier | None = None
    features: list[FeatureGate] = []
    expires_at: datetime | None = None
    organization: str | None = None
    message: str


class LicenseError(Exception):
    """Raised when license validation or loading fails."""

    pass
