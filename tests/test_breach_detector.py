"""Unit tests for BreachDetector."""

from __future__ import annotations

import os
import asyncio
from datetime import datetime, timezone
import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import create_async_engine

from anonreq.models.audit import Base
from anonreq.services.audit_chain import AuditChainService, AuditConfig
from anonreq.services.breach_detector import BreachDetector
from anonreq.services.slo_engine import SLOEngine


@pytest.fixture
async def audit_engine():
    """Create an in-memory SQLite engine with the audit schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def audit_chain(audit_engine):
    config = AuditConfig(retention_days=2557)
    return AuditChainService(audit_engine, config)


@pytest.mark.asyncio
@respx.mock
async def test_breach_detector_triggers_alert_and_audit(cache_manager, audit_chain):
    # Setup SLOEngine with a target success rate
    slo_engine = SLOEngine(cache_manager, config_path="nonexistent.yaml")
    
    # Setup httpx client and respx mock for webhook
    webhook_url = "https://alerts.internal/slo"
    import os
    os.environ["ANONREQ_BREACH_WEBHOOK_URL"] = webhook_url

    route = respx.post(webhook_url).respond(status_code=200)

    async with httpx.AsyncClient() as http_client:
        detector = BreachDetector(
            slo_engine=slo_engine,
            audit_chain=audit_chain,
            cache_manager=cache_manager,
            http_client=http_client,
            config_path="nonexistent.yaml"
        )

        # Trigger non-compliance: 1 success, 1 failure -> 50% success rate (target 99.9%)
        tenant_id = "tenant_test"
        await slo_engine.record_success(tenant_id, "success_rate")
        await slo_engine.record_failure(tenant_id, "success_rate")

        # Evaluate breaches
        breaches = await detector.evaluate(tenant_id)
        
        # Verify breach detected
        assert len(breaches) == 4  # daily, monthly, 24h, 30d windows are all non-compliant!
        
        # Wait a small moment for async task webhook calls to complete
        await asyncio.sleep(0.1)

        # Verify webhook was called
        assert route.called
        assert route.call_count == 4

        # Verify audit event was logged to DB
        events = await audit_chain.get_events(tenant_id=tenant_id, event_type="slo_breach_detected")
        assert len(events) == 4
        assert events[0].event_type == "slo_breach_detected"


@pytest.mark.asyncio
@respx.mock
async def test_breach_detector_cooldown_prevents_duplicates(cache_manager, audit_chain):
    slo_engine = SLOEngine(cache_manager, config_path="nonexistent.yaml")
    # Set cooldown to 300 seconds
    slo_engine._cooldown = 300

    webhook_url = "https://alerts.internal/slo"
    os.environ["ANONREQ_BREACH_WEBHOOK_URL"] = webhook_url
    route = respx.post(webhook_url).respond(status_code=200)

    async with httpx.AsyncClient() as http_client:
        detector = BreachDetector(
            slo_engine=slo_engine,
            audit_chain=audit_chain,
            cache_manager=cache_manager,
            http_client=http_client,
            config_path="nonexistent.yaml"
        )

        tenant_id = "tenant_test"
        await slo_engine.record_failure(tenant_id, "success_rate")

        # First evaluation: triggers webhook
        breaches_1 = await detector.evaluate(tenant_id)
        assert len(breaches_1) == 4
        
        await asyncio.sleep(0.05)
        assert route.call_count == 4

        # Second evaluation immediately: should skip due to cooldown
        breaches_2 = await detector.evaluate(tenant_id)
        assert len(breaches_2) == 0


@pytest.mark.asyncio
@respx.mock
async def test_breach_webhook_retries_and_dlq(cache_manager, audit_chain):
    slo_engine = SLOEngine(cache_manager, config_path="nonexistent.yaml")

    webhook_url = "https://alerts.internal/slo"
    os.environ["ANONREQ_BREACH_WEBHOOK_URL"] = webhook_url
    
    # Mock webhook to fail (500 Internal Server Error)
    route = respx.post(webhook_url).respond(status_code=500)

    async with httpx.AsyncClient() as http_client:
        detector = BreachDetector(
            slo_engine=slo_engine,
            audit_chain=audit_chain,
            cache_manager=cache_manager,
            http_client=http_client,
            config_path="nonexistent.yaml"
        )
        # Fast retry backoff for testing
        detector._retry_backoff_base = 0.01

        tenant_id = "tenant_test"
        await slo_engine.record_failure(tenant_id, "success_rate")

        # Evaluate: triggers webhook, fails all retries, goes to DLQ
        await detector.evaluate(tenant_id)
        
        # Wait for retries to finish (3 attempts * backoff)
        await asyncio.sleep(0.2)

        # Verify 3 retries made per window (4 windows * 3 retries = 12 calls)
        assert route.call_count == 12

        # Verify entries in DLQ
        dlq_entries = await detector.get_dlq_entries(tenant_id)
        assert len(dlq_entries) == 4
        
        # Test retry DLQ after recovery
        respx.clear()
        recovery_route = respx.post(webhook_url).respond(status_code=200)
        
        success_count = await detector.retry_dlq(tenant_id)
        assert success_count == 4
        assert recovery_route.called
        
        # Verify DLQ is empty now
        dlq_entries_after = await detector.get_dlq_entries(tenant_id)
        assert len(dlq_entries_after) == 0
