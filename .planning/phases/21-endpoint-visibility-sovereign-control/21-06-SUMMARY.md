---
phase: 21-endpoint-visibility-sovereign-control
plan: 06
subsystem: observability-validation
tags: [metrics, fail-closed, property-tests, phase-21]
requires:
  - phase: 21
    plan: 01
    provides: transparent proxy and deployment topology primitives
  - phase: 21
    plan: 03
    provides: voice pipeline and audio sanitization
  - phase: 21
    plan: 04
    provides: agent tool governance and result sanitization
  - phase: 21
    plan: 05
    provides: AI Firewall pipeline
provides:
  - Phase 21 Prometheus metrics modules with duplicate-safe get-or-create registration
  - Metrics registration tests for the 15 metrics listed in 21-SECURITY-ACCEPTANCE.md
  - Fail-closed integration tests across proxy, firewall, voice, and agent sanitizer paths
  - Hypothesis property tests for firewall, agent tool result, and voice sanitization invariants
affects: [phase-21, metrics, firewall, agent, voice, proxy, tests]
tech-stack:
  added: []
  patterns: [prometheus-get-or-create, deterministic-fake-services, hypothesis-invariants]
key-files:
  created:
    - src/anonreq/agent/metrics.py
    - src/anonreq/voice/metrics.py
    - src/anonreq/proxy/metrics.py
    - tests/test_metrics_registration.py
    - tests/test_fail_closed_integration.py
    - tests/test_firewall_pbt.py
    - tests/test_agent_pbt.py
    - tests/test_voice_pbt.py
  modified:
    - src/anonreq/firewall/metrics.py
    - src/anonreq/firewall/pipeline.py
    - src/anonreq/agent/tool_inspector.py
    - src/anonreq/agent/result_sanitizer.py
    - src/anonreq/voice/pipeline.py
    - src/anonreq/proxy/transparent_proxy.py
    - src/anonreq/monitoring/metrics.py
key-decisions:
  - "21-SECURITY-ACCEPTANCE.md is the source of truth for metrics; it lists 15 required Prometheus metrics although the plan prose says 17."
  - "Phase 21 metrics use duplicate-safe collector lookup to avoid Prometheus registration crashes under repeated test imports."
  - "Existing Phase 21 call paths that do not yet carry tenant context record tenant_id='default' to satisfy the metric label contract without adding request identifiers."
requirements-completed:
  - APPL-01/Req48
  - APPL-01/Req50
  - APPL-01/Req51
  - APPL-01/Req52
  - TEST-01
  - TEST-02
  - TEST-03
duration: 20 min
completed: 2026-07-05
status: complete
---

# Phase 21 Plan 06: Metrics, Fail-Closed Integration, and Property Tests Summary

**Prometheus metric coverage, fail-closed integration tests, and Hypothesis invariants for the Phase 21 proxy, firewall, voice, and agent governance surfaces**

## Performance

- **Tasks:** 3
- **Files modified:** 15
- **Focused tests:** 26 passed
- **Representative Phase 21 smoke tests:** 45 passed

## Accomplishments

- Added duplicate-safe Prometheus metric modules for firewall, agent, voice, and proxy components.
- Wired existing Phase 21 paths to increment the required metrics for firewall decisions, agent inspections/sanitization, voice stream latency/entities/audio sanitization, TLS interception, cert pinning, non-AI fail-closed blocks, and fail-closed events.
- Added metrics registration tests that verify collector existence, collector type, label names, increment behavior, and `/metrics` scrape output.
- Added fail-closed integration tests for TLS interception failure, detection timeout, cache failure, firewall classifier crash, STT failure, tool sanitizer crash, listener startup failure, all four deployment topologies, and blocked firewall requests causing zero downstream calls.
- Added Hypothesis tests for firewall monotonicity/fail-closed behavior, blocked-request zero-spend behavior, agent tool-result round trip/key preservation/cross-session token randomization, voice muted-frame zeroing, range merge consistency, severity ordering, and beep replacement.

## Files Created/Modified

- `src/anonreq/firewall/metrics.py` - Firewall metrics plus preserved prompt-security metric singleton.
- `src/anonreq/agent/metrics.py` - Agent inspection/sanitization counters and governance latency histogram.
- `src/anonreq/voice/metrics.py` - Voice stream, latency, entity, audio sanitization, and latency-exceeded metrics.
- `src/anonreq/proxy/metrics.py` - Proxy TLS/pinning/non-AI/fail-closed counters.
- `src/anonreq/firewall/pipeline.py` - Uses the shared firewall metric collectors.
- `src/anonreq/agent/tool_inspector.py` - Records tool-call inspection and governance duration metrics.
- `src/anonreq/agent/result_sanitizer.py` - Records result sanitization and governance duration metrics.
- `src/anonreq/voice/pipeline.py` - Uses labeled voice metrics and records entities, sanitized seconds, and latency exceedances.
- `src/anonreq/proxy/transparent_proxy.py` - Records TLS, pinning, non-AI block, and fail-closed metrics; TLS/dispatcher errors return HTTP 500.
- `src/anonreq/monitoring/metrics.py` - Aliases agent metrics from `anonreq.agent.metrics` to avoid duplicate registration and label drift.
- `tests/test_metrics_registration.py` - Metrics contract tests.
- `tests/test_fail_closed_integration.py` - Fail-closed integration tests.
- `tests/test_firewall_pbt.py` - Firewall property-based tests.
- `tests/test_agent_pbt.py` - Agent tool-result property-based tests.
- `tests/test_voice_pbt.py` - Voice/audio property-based tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Metrics source-of-truth mismatch handled**
- **Found during:** Task 1
- **Issue:** Plan prose and must-haves say "17 Prometheus metrics", but `21-SECURITY-ACCEPTANCE.md` lists 15 required metrics.
- **Fix:** Implemented and verified all 15 metrics from the acceptance table, and documented the discrepancy instead of adding unspecified metrics.
- **Files modified:** Phase 21 metric modules and `tests/test_metrics_registration.py`.

**2. [Rule 2 - Missing Critical] Existing metric label drift corrected**
- **Found during:** Task 1
- **Issue:** Prior agent metrics in `monitoring/metrics.py` used labels that did not match the Phase 21 acceptance table.
- **Fix:** Added `anonreq.agent.metrics` as the authoritative module and aliased those collectors from `monitoring/metrics.py`.
- **Files modified:** `src/anonreq/agent/metrics.py`, `src/anonreq/monitoring/metrics.py`, agent caller modules.

**3. [Rule 2 - Missing Critical] Proxy interception errors now fail closed**
- **Found during:** Task 2
- **Issue:** TLS certificate generation/dispatcher errors could propagate out of `TransparentProxy.handle_request()` instead of returning the plan-required HTTP 500 response.
- **Fix:** Wrapped the interception/dispatch path, increments `anonreq_fail_closed_total`, and returns a generic fail-closed HTTP 500 body with no raw request data.
- **Files modified:** `src/anonreq/proxy/transparent_proxy.py`.

## Known Stubs

None. Tests use fakes and mocks intentionally to avoid external services, network calls, Redis, Presidio, and model downloads.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: metrics_labels | `src/anonreq/agent/metrics.py`, `src/anonreq/firewall/metrics.py`, `src/anonreq/voice/metrics.py`, `src/anonreq/proxy/metrics.py` | New Prometheus label surfaces include tenant/domain/action/component labels per Phase 21 acceptance criteria. Tests verify fixed label names. |
| threat_flag: fail_closed_surface | `src/anonreq/proxy/transparent_proxy.py` | New fail-closed HTTP 500 handling at the transparent proxy trust boundary; response body is generic and excludes raw request content. |

## Verification

- `pytest tests/test_metrics_registration.py tests/test_fail_closed_integration.py tests/test_firewall_pbt.py tests/test_agent_pbt.py tests/test_voice_pbt.py -q` -> 26 passed.
- `pytest tests/test_proxy_topology.py tests/test_proxy_integration.py tests/test_voice_pipeline.py tests/test_agent_tool_inspector.py tests/test_agent_result_sanitizer.py tests/test_firewall_pipeline.py -q` -> 45 passed.
- `PYTHONPATH=src python3 -c "... expected metrics ..."` -> All 15 Phase 21 metrics registered OK.
- Artifact line counts meet plan minimums: `test_fail_closed_integration.py` 229 lines, `test_firewall_pbt.py` 111 lines, `test_agent_pbt.py` 124 lines, `test_voice_pbt.py` 86 lines, `test_metrics_registration.py` 101 lines.

## Task Commits

No commits were created. The repository is a shared dirty main worktree with prior Phase 21 wave files still untracked, including files this plan had to integrate with (`src/anonreq/firewall/pipeline.py`, `src/anonreq/agent/result_sanitizer.py`, `src/anonreq/agent/tool_inspector.py`, `src/anonreq/voice/pipeline.py`, and `src/anonreq/proxy/transparent_proxy.py`). Creating a scoped Plan 21-06 commit would have captured prior-wave implementation content that this plan does not own.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/21-endpoint-visibility-sovereign-control/21-06-SUMMARY.md`.
- All created test files exist and pass.
- All metric modules exist and import without duplicate collector registration errors.
- Commits intentionally skipped due dirty shared worktree constraints.
