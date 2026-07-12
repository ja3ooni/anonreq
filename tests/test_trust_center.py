"""Tests for Trust Center — config, schemas, rate limiter, fail-closed, and integration.

Per D13: Unit tests for config parsing, schema validation, rate limiter, and
fail-closed behavior. Integration tests for full response format verification.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Lazy imports inside tests are preferred, but we import basic types/models here
from anonreq.trust_center.config import TrustCenterSettings
from anonreq.trust_center.schemas import (
    FrameworkInfo,
    TrustCompliance,
    TrustMetrics,
    TrustSecurity,
    TrustStatus,
)


class TestTrustCenterConfig:
    """Unit tests for TrustCenterSettings config parsing."""

    def test_default_values(self):
        s = TrustCenterSettings()
        assert s.enabled is False
        assert s.display_name == "AnonReq Trust Center"
        assert s.contact_email == "security@example.com"
        assert "soc2" in s.supported_frameworks
        assert s.feature_summary["anonymization"] is True
        assert s.certifications == []

    def test_enabled_true(self):
        s = TrustCenterSettings(enabled=True)
        assert s.enabled is True

    def test_custom_values(self):
        s = TrustCenterSettings(
            display_name="Custom TC",
            contact_email="custom@example.com",
            logo_url="https://example.com/logo.png",
        )
        assert s.display_name == "Custom TC"
        assert s.contact_email == "custom@example.com"
        assert s.logo_url == "https://example.com/logo.png"

    def test_supported_frameworks(self):
        s = TrustCenterSettings(supported_frameworks=["soc2", "gdpr"])
        assert s.supported_frameworks == ["soc2", "gdpr"]

    def test_certifications(self):
        certs = [{"name": "SOC 2 Type II", "issuer": "AuditFirm"}]
        s = TrustCenterSettings(certifications=certs)
        assert s.certifications == certs

    def test_extra_fields_ignored(self):
        s = TrustCenterSettings(enabled=True, extra_dummy_field="ignored")
        assert s.enabled is True
        assert not hasattr(s, "extra_dummy_field")


class TestTrustCenterSchemas:
    """Unit tests for response schema validation."""

    def test_trust_status_creation(self):
        ts = TrustStatus(
            slo_count=5,
            compliant_count=4,
            overall_percentage=80.0,
            last_breach=None,
            period="Last 30 days",
        )
        assert ts.slo_count == 5
        assert ts.compliant_count == 4
        assert ts.overall_percentage == 80.0
        assert ts.last_breach is None
        assert ts.period == "Last 30 days"

    def test_trust_status_with_breach(self):
        breach_dt = datetime(2026, 6, 15, tzinfo=timezone.utc)
        ts = TrustStatus(
            slo_count=5,
            compliant_count=4,
            overall_percentage=80.0,
            last_breach=breach_dt,
            period="Last 30 days",
        )
        assert ts.last_breach == breach_dt

    def test_framework_info(self):
        fi = FrameworkInfo(
            id="soc2",
            name="SOC 2",
            description="SOC 2 security baseline",
            jurisdictions=["US"],
        )
        assert fi.id == "soc2"
        assert fi.name == "SOC 2"
        assert fi.description == "SOC 2 security baseline"
        assert fi.jurisdictions == ["US"]

    def test_trust_compliance(self):
        fi = FrameworkInfo(
            id="soc2",
            name="SOC 2",
            description="desc",
            jurisdictions=["US"],
        )
        tc = TrustCompliance(frameworks=[fi])
        assert len(tc.frameworks) == 1
        assert tc.frameworks[0].id == "soc2"

    def test_trust_metrics(self):
        tm = TrustMetrics(
            total_requests=1000.0,
            total_entities=500.0,
            fail_secure_count=2.0,
            latency_p50_ms=45.0,
            latency_p99_ms=250.0,
            uptime_days=30.5,
        )
        assert tm.total_requests == 1000.0
        assert tm.total_entities == 500.0
        assert tm.fail_secure_count == 2.0
        assert tm.latency_p50_ms == 45.0
        assert tm.latency_p99_ms == 250.0
        assert tm.uptime_days == 30.5

    def test_trust_security(self):
        ts = TrustSecurity(
            display_name="Security",
            contact_email="sec@example.com",
            logo_url="https://logo.png",
            feature_summary={"anonymization": True},
            security_contact="sec@example.com",
            certifications=[{"name": "SOC 2"}],
        )
        assert ts.display_name == "Security"
        assert ts.contact_email == "sec@example.com"
        assert ts.logo_url == "https://logo.png"
        assert ts.feature_summary["anonymization"] is True
        assert ts.security_contact == "sec@example.com"
        assert ts.certifications == [{"name": "SOC 2"}]


@pytest.fixture
async def redis_cache():
    import fakeredis.aioredis
    from anonreq.cache.manager import CacheManager

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = CacheManager.__new__(CacheManager)
    manager._redis = fake_redis
    manager._ttl = 300
    yield manager
    await fake_redis.aclose()


class TestTrustCenterRateLimiter:
    """Unit tests for rate limiter behavior."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_first_request(self, redis_cache):
        from anonreq.trust_center.service import TrustCenterRateLimiter

        limiter = TrustCenterRateLimiter(redis_cache)
        request = MagicMock()
        request.client.host = "127.0.0.1"

        # Should not raise exception
        await limiter(request)

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_at_limit(self, redis_cache):
        from anonreq.trust_center.service import TrustCenterRateLimiter

        limiter = TrustCenterRateLimiter(redis_cache)
        request = MagicMock()
        request.client.host = "127.0.0.1"

        with patch("time.time", return_value=1000000.0):
            for _ in range(60):
                await limiter(request)

            with pytest.raises(HTTPException) as exc_info:
                await limiter(request)
            assert exc_info.value.status_code == 429
            assert exc_info.value.detail == "rate_limit_exceeded"

    @pytest.mark.asyncio
    async def test_rate_limiter_different_ips_independent(self, redis_cache):
        from anonreq.trust_center.service import TrustCenterRateLimiter

        limiter = TrustCenterRateLimiter(redis_cache)
        request_a = MagicMock()
        request_a.client.host = "1.2.3.4"
        request_b = MagicMock()
        request_b.client.host = "5.6.7.8"

        with patch("time.time", return_value=1000000.0):
            for _ in range(60):
                await limiter(request_a)

            # Request A is now blocked
            with pytest.raises(HTTPException):
                await limiter(request_a)

            # Request B should be allowed
            await limiter(request_b)

    @pytest.mark.asyncio
    async def test_rate_limiter_window_expiry(self, redis_cache):
        from anonreq.trust_center.service import TrustCenterRateLimiter

        limiter = TrustCenterRateLimiter(redis_cache)
        request = MagicMock()
        request.client.host = "127.0.0.1"

        with patch("time.time") as mock_time:
            mock_time.return_value = 1000000.0
            for _ in range(60):
                await limiter(request)

            with pytest.raises(HTTPException):
                await limiter(request)

            # Advance time by 65 seconds
            mock_time.return_value = 1000065.0
            # Request should be allowed again
            await limiter(request)


class TestTrustCenterFailClosed:
    """Unit tests for service layer fail-closed pattern."""

    @pytest.fixture
    def trust_settings(self):
        return TrustCenterSettings(enabled=True)

    @pytest.fixture
    def mock_slo_engine(self):
        engine = MagicMock()
        engine.get_all_compliance = AsyncMock()
        return engine

    @pytest.fixture
    def mock_preset_engine(self):
        engine = MagicMock()
        engine.list_presets = MagicMock()
        return engine

    @pytest.fixture
    def service(self, trust_settings, mock_slo_engine, mock_preset_engine):
        from anonreq.trust_center.service import TrustCenterService

        return TrustCenterService(
            slo_engine=mock_slo_engine,
            preset_engine=mock_preset_engine,
            settings=trust_settings,
        )

    @pytest.mark.asyncio
    async def test_fail_closed_slo_unavailable(self, service, mock_slo_engine):
        mock_slo_engine.get_all_compliance.side_effect = RuntimeError("SLO engine down")
        res = await service.get_status()
        assert res is None

    @pytest.mark.asyncio
    async def test_fail_closed_preset_unavailable(self, service, mock_preset_engine):
        mock_preset_engine.list_presets.side_effect = RuntimeError("Preset engine down")
        res = await service.get_compliance()
        assert res is None

    @pytest.mark.asyncio
    async def test_fail_closed_both_unavailable(
        self, service, mock_slo_engine, mock_preset_engine
    ):
        mock_slo_engine.get_all_compliance.side_effect = RuntimeError("SLO engine down")
        mock_preset_engine.list_presets.side_effect = RuntimeError("Preset engine down")
        assert (await service.get_status()) is None
        assert (await service.get_compliance()) is None

    @pytest.mark.asyncio
    async def test_preset_engine_none(self, trust_settings, mock_slo_engine):
        from anonreq.trust_center.service import TrustCenterService

        service = TrustCenterService(
            slo_engine=mock_slo_engine,
            preset_engine=None,
            settings=trust_settings,
        )
        res = await service.get_compliance()
        assert isinstance(res, TrustCompliance)
        assert res.frameworks == []


class TestTrustCenterIntegration:
    """Integration tests with TestClient."""

    @pytest.fixture
    def trust_app(self):
        """Create a minimal FastAPI app with Trust Center router and mocked dependencies."""
        from anonreq.cache.manager import CacheManager
        from anonreq.compliance.preset import CompliancePreset
        from anonreq.services.slo_engine import SLOCompliance
        from anonreq.trust_center.config import TrustCenterSettings
        from anonreq.trust_center.router import router as trust_router
        from anonreq.trust_center.service import TrustCenterRateLimiter, TrustCenterService
        import fakeredis.aioredis

        app = FastAPI()
        app.state.trust_center_enabled = True

        # Mock SLO engine
        slo_engine = MagicMock()
        comp1 = SLOCompliance(
            slo_name="success_rate",
            target=99.9,
            current=99.95,
            compliant=True,
            window_type="daily",
            window_key="2026-07-07",
            last_breach=None,
        )
        slo_engine.get_all_compliance = AsyncMock(
            return_value={
                "success_rate": [comp1],
                "fail_secure_rate": [],
            }
        )

        # Mock PresetEngine
        preset_engine = MagicMock()
        preset_engine.list_presets = MagicMock(
            return_value={
                "soc2": CompliancePreset(
                    id="soc2",
                    name="SOC 2",
                    description="desc",
                    jurisdictions=["US"],
                    mandatory_entity_types=[],
                ),
            }
        )

        settings = TrustCenterSettings(enabled=True)
        service = TrustCenterService(slo_engine, preset_engine, settings)
        app.state.trust_center_service = service

        # Rate limiter with fakeredis
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache_mgr = CacheManager.__new__(CacheManager)
        cache_mgr._redis = fake_redis
        cache_mgr._ttl = 300
        limiter = TrustCenterRateLimiter(cache_mgr)
        app.state.trust_center_rate_limiter = limiter

        app.include_router(trust_router)
        return app

    def test_status_endpoint_returns_200(self, trust_app):
        client = TestClient(trust_app)
        resp = client.get("/v1/trust/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "slo_count" in data
        assert "compliant_count" in data
        assert "overall_percentage" in data
        assert "last_breach" in data
        assert "period" in data

    def test_status_endpoint_computes_correctly(self, trust_app):
        client = TestClient(trust_app)
        resp = client.get("/v1/trust/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slo_count"] == 2
        # success_rate compliant=True (any window compliant), fail_secure_rate is empty -> default non-compliant
        # So overall percentage should be 50%
        assert data["overall_percentage"] == 50.0

    def test_compliance_endpoint_returns_frameworks(self, trust_app):
        client = TestClient(trust_app)
        resp = client.get("/v1/trust/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert "frameworks" in data
        assert len(data["frameworks"]) == 1
        assert data["frameworks"][0]["id"] == "soc2"
        assert data["frameworks"][0]["name"] == "SOC 2"

    def test_metrics_endpoint_returns_aggregates(self, trust_app):
        client = TestClient(trust_app)
        resp = client.get("/v1/trust/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_requests" in data
        assert "total_entities" in data
        assert "fail_secure_count" in data
        assert "latency_p50_ms" in data
        assert "latency_p99_ms" in data
        assert "uptime_days" in data

    def test_security_endpoint_returns_static_metadata(self, trust_app):
        client = TestClient(trust_app)
        resp = client.get("/v1/trust/security")
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_name"] == "AnonReq Trust Center"
        assert isinstance(data["feature_summary"], dict)
        assert isinstance(data["certifications"], list)

    def test_disabled_gate_returns_404(self, trust_app):
        trust_app.state.trust_center_enabled = False
        client = TestClient(trust_app)
        for path in [
            "/v1/trust/status",
            "/v1/trust/compliance",
            "/v1/trust/metrics",
            "/v1/trust/security",
        ]:
            resp = client.get(path)
            assert resp.status_code == 404

    def test_rate_limiter_allows_normal_traffic(self, trust_app):
        client = TestClient(trust_app)
        for _ in range(5):
            resp = client.get("/v1/trust/status")
            assert resp.status_code == 200

    def test_fail_closed_integration(self, trust_app):
        trust_app.state.trust_center_service = None
        client = TestClient(trust_app)
        resp = client.get("/v1/trust/status")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "service_unavailable"

    def test_all_endpoints_cors_not_set(self, trust_app):
        client = TestClient(trust_app)
        resp = client.get("/v1/trust/status", headers={"Origin": "https://example.com"})
        assert resp.status_code == 200
        assert "Access-Control-Allow-Origin" not in resp.headers
