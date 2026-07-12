"""Unit and property-based tests for LicenseValidator."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException
from hypothesis import given, strategies as st

from anonreq.license.config import license_settings
from anonreq.license.models import FeatureGate, LicenseStatus, LicenseTier
from anonreq.license.validator import LicenseValidator, require_license


def _create_license_payload(
    org: str = "TestOrg",
    tier: str = "appliance",
    features: list[str] = None,
    expires_in_days: int = 365,
    secret: str = "test-secret-key",
) -> tuple[str, str]:
    """Create a signed license key for testing.

    Returns (license_key_string, secret_key).
    """
    features = features or ["ai_firewall", "soc_integration"]
    payload = {
        "org": org,
        "tier": tier,
        "features": features,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat(),
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "signature": "dummy",
    }
    data_str = json.dumps(payload)
    sig = hmac.new(
        secret.encode("utf-8"),
        data_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    raw = f"{data_str}.{sig}"
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8"), secret


@pytest.fixture(autouse=True)
def clean_cache():
    """Clear license validator cache before and after each test."""
    LicenseValidator.invalidate_cache()
    yield
    LicenseValidator.invalidate_cache()


@pytest.mark.asyncio
async def test_valid_license():
    """Verify that a valid license key + correct secret -> valid status."""
    key, secret = _create_license_payload()
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    status = await LicenseValidator.validate_license()
    assert status.valid is True
    assert status.organization == "TestOrg"
    assert status.tier == LicenseTier.APPLIANCE
    assert FeatureGate.AI_FIREWALL in status.features


@pytest.mark.asyncio
async def test_missing_license_key():
    """Verify missing key gives invalid status with correct message."""
    license_settings.LICENSE_KEY = None
    license_settings.LICENSE_SECRET = "secret"
    status = await LicenseValidator.validate_license()
    assert status.valid is False
    assert "No license key" in status.message


@pytest.mark.asyncio
async def test_invalid_signature():
    """Verify signature mismatch gives invalid status."""
    key, secret = _create_license_payload()
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = "wrong-secret"

    status = await LicenseValidator.validate_license()
    assert status.valid is False
    assert "Invalid license signature" in status.message


@pytest.mark.asyncio
async def test_tampered_payload():
    """Verify that tampering with the payload fails signature verification."""
    key, secret = _create_license_payload()
    decoded = base64.b64decode(key).decode("utf-8")
    data, sig = decoded.rsplit(".", 1)

    # Tamper with the JSON data (change org name)
    payload_dict = json.loads(data)
    payload_dict["org"] = "TamperedCorp"
    tampered_data = json.dumps(payload_dict)

    tampered_key = base64.b64encode(f"{tampered_data}.{sig}".encode("utf-8")).decode("utf-8")
    license_settings.LICENSE_KEY = tampered_key
    license_settings.LICENSE_SECRET = secret

    status = await LicenseValidator.validate_license()
    assert status.valid is False
    assert "signature" in status.message


@pytest.mark.asyncio
async def test_expired_license():
    """Verify that an expired license gives invalid status."""
    key, secret = _create_license_payload(expires_in_days=-30)
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    status = await LicenseValidator.validate_license()
    assert status.valid is False
    assert "expired" in status.message


@pytest.mark.asyncio
async def test_malformed_key():
    """Verify malformed base64 strings fail gracefully."""
    license_settings.LICENSE_KEY = "not-base64-at-all-!!!"
    license_settings.LICENSE_SECRET = "secret"

    status = await LicenseValidator.validate_license()
    assert status.valid is False
    assert "failed" in status.message


@pytest.mark.asyncio
async def test_cached_status():
    """Verify that license verification is cached."""
    key, secret = _create_license_payload(org="CachedOrg")
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    status1 = await LicenseValidator.get_status()
    assert status1.valid is True
    assert status1.organization == "CachedOrg"

    # Corrupt settings key
    license_settings.LICENSE_KEY = "corrupted"
    status2 = await LicenseValidator.get_status()
    assert status2.valid is True
    assert status2.organization == "CachedOrg"

    LicenseValidator.invalidate_cache()
    status3 = await LicenseValidator.get_status()
    assert status3.valid is False


@pytest.mark.asyncio
async def test_check_feature_valid():
    """Verify check_feature returns True for features in license."""
    key, secret = _create_license_payload(features=["ai_firewall"])
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    assert await LicenseValidator.check_feature("ai_firewall") is True


@pytest.mark.asyncio
async def test_check_feature_not_in_license():
    """Verify check_feature returns False for unlicensed features."""
    key, secret = _create_license_payload(features=["ai_firewall"])
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    assert await LicenseValidator.check_feature("trust_center") is False


@pytest.mark.asyncio
async def test_check_feature_no_license():
    """Verify check_feature returns False when no license is configured."""
    license_settings.LICENSE_KEY = None
    assert await LicenseValidator.check_feature("ai_firewall") is False


@pytest.mark.asyncio
async def test_require_license_dependency():
    """Verify require_license dependency callable structure."""
    dep = require_license("ai_firewall")
    assert callable(dep)


@pytest.mark.asyncio
async def test_require_license_multiple_gates():
    """Verify different feature gates reject or allow independently."""
    key, secret = _create_license_payload(features=["ai_firewall"])
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    gate_ok = require_license(FeatureGate.AI_FIREWALL)
    gate_fail = require_license(FeatureGate.SOC_INTEGRATION)

    class DummyRequest:
        pass

    # Should pass
    await gate_ok(DummyRequest())

    # Should raise 402
    with pytest.raises(HTTPException) as exc:
        await gate_fail(DummyRequest())
    assert exc.value.status_code == 402


@given(
    org=st.text(min_size=1, max_size=50),
    tier=st.sampled_from(["free", "appliance"]),
    features=st.lists(
        st.sampled_from([
            "ai_firewall",
            "soc_integration",
            "trust_center",
            "advanced_detection",
            "compliance_monitoring",
        ]),
        min_size=1,
        max_size=5,
        unique=True,
    ),
)
@pytest.mark.asyncio
async def test_property_roundtrip(org, tier, features):
    """Property-based round-trip signature verification."""
    secret = "prop-secret"
    # Re-import and run inside async helper to bridge hypothesis with async
    key, _ = _create_license_payload(
        org=org,
        tier=tier,
        features=features,
        expires_in_days=30,
        secret=secret,
    )
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    # Reset cache manually since hypothesis bypasses fixtures
    LicenseValidator.invalidate_cache()

    status = await LicenseValidator.validate_license()
    assert status.valid is True
    assert status.organization == org
    assert status.tier == LicenseTier(tier)
    assert len(status.features) == len(features)
