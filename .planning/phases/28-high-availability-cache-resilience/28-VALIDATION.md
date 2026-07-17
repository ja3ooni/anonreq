---
phase: 28
slug: high-availability-cache-resilience
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-12
---

# Phase 28 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with pytest-asyncio and fakeredis |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_cache.py tests/test_health.py tests/test_startup.py tests/property/test_fail_secure.py::test_cache_retry_exhaustion_returns_503_without_provider_forwarding -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~60 seconds |

## Sampling Rate

- **After Plan 01 Task 2:** Run `uv run pytest tests/test_cache.py -q`
- **After Plan 02 Task 1:** Run `uv run pytest tests/test_cache.py tests/test_exceptions.py tests/property/test_fail_secure.py::test_cache_retry_exhaustion_returns_503_without_provider_forwarding -q`
- **After Plan 02 Task 2:** Run `uv run pytest tests/test_health.py tests/test_startup.py tests/test_cache.py -q`
- **After every plan wave:** Run `uv run pytest`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 28-01-02 | 01 | 1 | HA-01 | T-28-01, T-28-SC | After approval, Tenacity is runtime-locked and only validated standalone, Sentinel, or Cluster topologies construct a client; malformed URLs cannot connect. | async unit | `uv run pytest tests/test_cache.py -q` | Yes | pending |
| 28-02-01 | 02 | 2 | HA-03 | T-28-02, T-28-03 | Retriable Valkey errors use bounded 0.1-2.0-second jittered exponential waits; terminal cache exhaustion returns HTTP 503 and ProviderStage has zero calls. | async unit + focused route invariant | `uv run pytest tests/test_cache.py tests/test_exceptions.py tests/property/test_fail_secure.py::test_cache_retry_exhaustion_returns_503_without_provider_forwarding -q` | Yes | pending |
| 28-02-02 | 02 | 2 | HA-03 | T-28-04, T-28-05 | Startup reuses the topology-aware manager; liveness remains process-only and readiness returns 503 when Valkey or Presidio is unavailable. | endpoint + async unit | `uv run pytest tests/test_health.py tests/test_startup.py tests/test_cache.py -q` | Yes | pending |

## Wave 0 Requirements

- [ ] `tests/test_cache.py` — Plan 01 Task 2 topology parser/factory/dependency cases, then Plan 02 Task 1 retry, bounded-jitter, exhaustion, and client lifecycle cases.
- [ ] `tests/property/test_fail_secure.py` — Plan 02 Task 1 focused terminal-cache-exhaustion route test asserting HTTP 503 and no ProviderStage call.
- [ ] `tests/test_health.py` and `tests/test_startup.py` — Plan 02 Task 2 liveness/readiness split and topology-aware startup validation cases.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A live Sentinel/Cluster election recovers within the configured retry budget. | HA-01, HA-03 | Unit tests mock topology clients; a real election requires deployment infrastructure. | Exercise a planned HA test deployment, trigger primary failover, and confirm requests either recover or return 503 with no forwarding. |

## Validation Sign-Off

- [x] All tasks have automated verification or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verification
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
