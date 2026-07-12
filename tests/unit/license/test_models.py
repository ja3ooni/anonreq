"""Unit tests for licensing data models and enums."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from anonreq.license.models import (
    FeatureGate,
    LicensePayload,
    LicenseStatus,
    LicenseTier,
    LicenseError,
)


def test_feature_gate_values():
    """Verify FeatureGate enum values match kebab-case specifications."""
    assert FeatureGate.TRUST_CENTER == "trust_center"
    assert FeatureGate.AI_FIREWALL == "ai_firewall"
    assert FeatureGate.SOC_INTEGRATION == "soc_integration"
    assert FeatureGate.ADVANCED_DETECTION == "advanced_detection"
    assert FeatureGate.COMPLIANCE_MONITORING == "compliance_monitoring"


def test_license_tier_values():
    """Verify LicenseTier has correct values."""
    assert LicenseTier.FREE == "free"
    assert LicenseTier.APPLIANCE == "appliance"


def test_license_payload_creation():
    """Verify LicensePayload constructs successfully with valid arguments."""
    now = datetime.now(timezone.utc)
    payload = LicensePayload(
        org="Acme",
        tier=LicenseTier.APPLIANCE,
        features=[FeatureGate.AI_FIREWALL],
        expires_at=now,
        issued_at=now,
        signature="mysig",
    )
    assert payload.org == "Acme"
    assert payload.tier == LicenseTier.APPLIANCE
    assert payload.features == [FeatureGate.AI_FIREWALL]
    assert payload.expires_at == now
    assert payload.issued_at == now
    assert payload.signature == "mysig"


def test_license_status_defaults():
    """Verify LicenseStatus default values."""
    status = LicenseStatus(valid=False, message="Fail")
    assert status.valid is False
    assert status.message == "Fail"
    assert status.tier is None
    assert status.features == []
    assert status.expires_at is None
    assert status.organization is None


def test_license_error_is_exception():
    """Verify LicenseError is an Exception subclass."""
    assert issubclass(LicenseError, Exception)


def test_feature_gate_from_string():
    """Verify we can construct FeatureGate from string value."""
    gate = FeatureGate("ai_firewall")
    assert gate == FeatureGate.AI_FIREWALL

    with pytest.raises(ValueError):
        FeatureGate("nonexistent_feature")
