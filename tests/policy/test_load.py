"""Simulated load tests to validate PDP/PEP latency budgets.

Simulates:
- Baseline profile: 10 concurrent users, P95 < 10ms
- Burst profile: 100 concurrent users, P95 < 50ms
- Soak profile: 25 concurrent users, verify stability
- Failover/Recovery: Cache manager disconnection handling
Logs latency statistics to ``tests/policy/load-results.json``.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from anonreq.models.processing_context import ProcessingContext
from anonreq.policy.models import PolicyAction, PolicyDecision
from anonreq.policy.pdp import PolicyDecisionPoint
from anonreq.policy.residency_router import ResidencyRouter
from anonreq.policy.spend_controller import SpendController
from anonreq.policy.store import PolicyStore
from anonreq.policy.usage_limiter import UsageLimiter


@pytest.fixture
def mock_pdp_dependencies():
    store = AsyncMock(spec=PolicyStore)
    store.enabled_rules.return_value = []
    
    limiter = AsyncMock(spec=UsageLimiter)
    limiter.check_rate_limit.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(timezone.utc)
    )
    
    spend = AsyncMock(spec=SpendController)
    spend.check_spend.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(timezone.utc)
    )
    
    residency = AsyncMock(spec=ResidencyRouter)
    residency.resolve_region.return_value = PolicyDecision(
        action=PolicyAction.ALLOW, matched_rule_ids=[], decision_ts=datetime.now(timezone.utc)
    )
    
    return store, limiter, spend, residency


async def run_concurrent_requests(pdp, concurrency: int, count: int) -> list[float]:
    latencies = []
    semaphore = asyncio.Semaphore(concurrency)

    async def single_request(i: int):
        async with semaphore:
            ctx = ProcessingContext(
                request_id=f"req_{i}",
                tenant_id="tenant_load",
                classification_result={"classification_level": "Public"},
            )
            # Add a micro sleep to simulate network roundtrip (1ms)
            await asyncio.sleep(0.001)
            start = time.perf_counter()
            await pdp.evaluate_all(ctx)
            elapsed = (time.perf_counter() - start) * 1000.0  # in ms
            latencies.append(elapsed)

    tasks = [single_request(i) for i in range(count)]
    await asyncio.gather(*tasks)
    return latencies


def calculate_p95(latencies: list[float]) -> float:
    if not latencies:
        return 0.0
    sorted_l = sorted(latencies)
    idx = int(len(sorted_l) * 0.95)
    return sorted_l[min(idx, len(sorted_l) - 1)]


@pytest.mark.asyncio
async def test_baseline_load_profile(mock_pdp_dependencies):
    store, limiter, spend, residency = mock_pdp_dependencies
    pdp = PolicyDecisionPoint(store, limiter, spend, residency, cache_ttl=60)

    # 10 concurrent users, 50 requests
    latencies = await run_concurrent_requests(pdp, concurrency=10, count=50)
    p95 = calculate_p95(latencies)

    # Verify P95 latency is well within the 10ms budget
    assert p95 < 10.0

    # Save result
    results = {
        "profile": "baseline",
        "concurrency": 10,
        "total_requests": 50,
        "p95_ms": p95,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open("tests/policy/load-results.json", "w") as f:
        json.dump(results, f, indent=2)


@pytest.mark.asyncio
async def test_burst_load_profile(mock_pdp_dependencies):
    store, limiter, spend, residency = mock_pdp_dependencies
    pdp = PolicyDecisionPoint(store, limiter, spend, residency, cache_ttl=60)

    # 100 concurrent users, 200 requests
    latencies = await run_concurrent_requests(pdp, concurrency=100, count=200)
    p95 = calculate_p95(latencies)

    # Verify P95 latency is well within 50ms budget for burst
    assert p95 < 50.0


@pytest.mark.asyncio
async def test_soak_load_profile(mock_pdp_dependencies):
    store, limiter, spend, residency = mock_pdp_dependencies
    pdp = PolicyDecisionPoint(store, limiter, spend, residency, cache_ttl=60)

    # 25 concurrent users, 100 requests to check stability
    latencies = await run_concurrent_requests(pdp, concurrency=25, count=100)
    p95 = calculate_p95(latencies)
    assert p95 < 20.0


@pytest.mark.asyncio
async def test_failover_recovery_latency(mock_pdp_dependencies):
    store, limiter, spend, residency = mock_pdp_dependencies
    pdp = PolicyDecisionPoint(store, limiter, spend, residency, cache_ttl=1)

    # Simulating outage (store throws error)
    store.enabled_rules.side_effect = Exception("Outage")
    ctx = ProcessingContext(request_id="fail_1", tenant_id="tenant_load")
    decision = await pdp.evaluate_all(ctx)
    assert decision.action == PolicyAction.BLOCK
    assert decision.enforcement == "503"

    # Simulating recovery (store works again)
    store.enabled_rules.side_effect = None
    store.enabled_rules.return_value = []
    ctx_recovery = ProcessingContext(request_id="rec_1", tenant_id="tenant_load", model="diff_model")
    decision_recovery = await pdp.evaluate_all(ctx_recovery)
    assert decision_recovery.action == PolicyAction.ALLOW
