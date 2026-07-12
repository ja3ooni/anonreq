"""Unit tests for the license status admin endpoints."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from anonreq.admin.router import require_auth
from anonreq.license.config import license_settings
from anonreq.license.models import FeatureGate, LicenseTier
from anonreq.license.router import router as license_router
from anonreq.license.validator import LicenseValidator


def _create_license_payload(
    org: str = "TestOrg",
    tier: str = "appliance",
    features: list[str] = None,
    secret: str = "test-secret-key",
) -> str:
    features = features or ["ai_firewall", "soc_integration"]
    payload = {
        "org": org,
        "tier": tier,
        "features": features,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
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
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


@pytest.fixture
def license_app():
    app = FastAPI()
    # Bypass administrative authentication in tests
    app.dependency_overrides[require_auth] = lambda: None
    app.include_router(license_router)
    return app


@pytest.fixture(autouse=True)
def reset_validator():
    LicenseValidator.invalidate_cache()
    yield
    LicenseValidator.invalidate_cache()


@pytest.mark.asyncio
async def test_license_status_no_key(license_app):
    """GET /v1/admin/license with no key configured returns 200 with valid=False."""
    license_settings.LICENSE_KEY = None
    license_settings.LICENSE_SECRET = "secret"

    async with AsyncClient(
        transport=ASGITransport(app=license_app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/v1/admin/license")

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert "No license key" in data["message"]


@pytest.mark.asyncio
async def test_license_status_valid_key(license_app):
    """GET /v1/admin/license with valid key returns 200 with valid=True."""
    secret = "my-secret"
    key = _create_license_payload(org="Axiom", features=["ai_firewall"], secret=secret)
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    async with AsyncClient(
        transport=ASGITransport(app=license_app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/v1/admin/license")

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["organization"] == "Axiom"
    assert data["tier"] == "appliance"
    assert "ai_firewall" in data["features"]


@pytest.mark.asyncio
async def test_license_status_invalid_key(license_app):
    """GET /v1/admin/license with invalid signature returns 200 with valid=False."""
    secret = "my-secret"
    key = _create_license_payload(org="Axiom", features=["ai_firewall"], secret="different-secret")
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    async with AsyncClient(
        transport=ASGITransport(app=license_app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/v1/admin/license")

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert "signature" in data["message"]
