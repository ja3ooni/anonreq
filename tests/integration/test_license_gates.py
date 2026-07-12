"""Integration tests for require_license route-level gating (Phase 26, GUARD-03)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import FastAPI, Depends
from httpx import ASGITransport, AsyncClient

from anonreq.license.config import license_settings
from anonreq.license.validator import require_license, LicenseValidator


def _create_license_payload(
    org: str = "TestOrg",
    tier: str = "appliance",
    features: list[str] = None,
    expires_in_days: int = 30,
    secret: str = "test-secret-key",
) -> str:
    features = features or ["ai_firewall"]
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
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


@pytest.fixture
def integration_app():
    app = FastAPI()

    @app.get("/test/gated")
    async def gated(_=Depends(require_license("ai_firewall"))):
        return {"status": "ok"}

    @app.get("/test/gated-soc")
    async def gated_soc(_=Depends(require_license("soc_integration"))):
        return {"status": "ok"}

    @app.get("/test/open")
    async def open_endpoint():
        return {"status": "open"}

    return app


@pytest.fixture(autouse=True)
def reset_validator():
    LicenseValidator.invalidate_cache()
    yield
    LicenseValidator.invalidate_cache()


@pytest.mark.asyncio
async def test_gated_route_returns_402_without_license(integration_app):
    """Verify route returns 402 when no license is configured."""
    license_settings.LICENSE_KEY = None
    license_settings.LICENSE_SECRET = "secret"

    async with AsyncClient(
        transport=ASGITransport(app=integration_app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/test/gated")

    assert response.status_code == 402
    assert response.json()["detail"]["error"] == "license_required"


@pytest.mark.asyncio
async def test_gated_route_returns_402_with_invalid_license(integration_app):
    """Verify route returns 402 when signature is invalid."""
    secret = "secret"
    key = _create_license_payload(features=["ai_firewall"], secret="wrong-secret")
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    async with AsyncClient(
        transport=ASGITransport(app=integration_app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/test/gated")

    assert response.status_code == 402


@pytest.mark.asyncio
async def test_gated_route_returns_402_with_expired_license(integration_app):
    """Verify route returns 402 when license is expired."""
    secret = "secret"
    key = _create_license_payload(features=["ai_firewall"], expires_in_days=-1, secret=secret)
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    async with AsyncClient(
        transport=ASGITransport(app=integration_app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/test/gated")

    assert response.status_code == 402


@pytest.mark.asyncio
async def test_gated_route_returns_200_with_valid_license(integration_app):
    """Verify route returns 200 with valid matching license."""
    secret = "secret"
    key = _create_license_payload(features=["ai_firewall"], secret=secret)
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    async with AsyncClient(
        transport=ASGITransport(app=integration_app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/test/gated")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_gated_route_returns_402_with_wrong_feature(integration_app):
    """Verify route returns 402 when license is valid but feature is missing."""
    secret = "secret"
    key = _create_license_payload(features=["soc_integration"], secret=secret)
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    async with AsyncClient(
        transport=ASGITransport(app=integration_app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/test/gated")

    assert response.status_code == 402


@pytest.mark.asyncio
async def test_ungated_route_works_without_license(integration_app):
    """Verify open routes work without any configured license."""
    license_settings.LICENSE_KEY = None

    async with AsyncClient(
        transport=ASGITransport(app=integration_app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/test/open")

    assert response.status_code == 200
    assert response.json() == {"status": "open"}


@pytest.mark.asyncio
async def test_402_response_format(integration_app):
    """Verify 402 error payload matches expected structure."""
    license_settings.LICENSE_KEY = None

    async with AsyncClient(
        transport=ASGITransport(app=integration_app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/test/gated")

    assert response.status_code == 402
    detail = response.json()["detail"]
    assert detail["error"] == "license_required"
    assert detail["feature"] == "ai_firewall"
    assert "message" in detail


@pytest.mark.asyncio
async def test_different_gates_independent(integration_app):
    """Verify that multiple gated endpoints behave independently based on features."""
    secret = "secret"
    # Gated for ai_firewall only
    key = _create_license_payload(features=["ai_firewall"], secret=secret)
    license_settings.LICENSE_KEY = key
    license_settings.LICENSE_SECRET = secret

    async with AsyncClient(
        transport=ASGITransport(app=integration_app),
        base_url="http://test",
    ) as ac:
        res_gated = await ac.get("/test/gated")
        res_soc = await ac.get("/test/gated-soc")

    assert res_gated.status_code == 200
    assert res_soc.status_code == 402
