---
phase: 21-endpoint-visibility-sovereign-control
plan: 01
subsystem: proxy
tags: [transparent-proxy, tls-interception, deployment-modes, reverse-proxy]
requires:
  - phase: 09-content-type-dispatcher
    provides: single content-type routing field and dispatcher pattern
  - phase: 10-ai-security-firewall
    provides: downstream security processing pipeline
provides:
  - Dynamic TLS certificate generation signed by an enterprise CA
  - AI API traffic classification and certificate-pinning policy decisions
  - Transparent proxy request routing with fail-open/fail-closed behavior
  - Reverse proxy request handling with CONNECT tunnel support
  - Deployment mode abstraction for reverse, transparent, virtual, and physical appliance modes
affects: [phase-21, proxy, deployment, appliance]
tech-stack:
  added: []
  patterns: [topology-config-dataclass, fail-closed-proxy-policy, listener-autostart-gate]
key-files:
  created:
    - src/anonreq/proxy/tls_interceptor.py
    - src/anonreq/proxy/detection.py
    - src/anonreq/proxy/transparent_proxy.py
    - src/anonreq/proxy/reverse_proxy.py
    - src/anonreq/deployment/__init__.py
    - src/anonreq/deployment/modes.py
    - tests/test_proxy_tls.py
    - tests/test_proxy_topology.py
    - tests/test_proxy_integration.py
  modified:
    - src/anonreq/proxy/__init__.py
    - src/anonreq/main.py
key-decisions:
  - "Transparent proxy listener creation is explicit: app startup wires the proxy object, while ANONREQ_START_NETWORK_PROXY controls whether a network listener binds a port."
  - "Certificate pinning is represented as a policy signal from observable TLS/client failure markers; fail-closed blocks with HTTP 451 and fail-open forwards untouched."
  - "DEPLOYMENT_MODE defaults to reverse so existing FastAPI startup does not require enterprise CA files."
patterns-established:
  - "DeploymentMode selects topology-specific defaults without forking the core gateway."
  - "Proxy request/response dataclasses make network policy behavior unit-testable without live packet interception."
requirements-completed:
  - APPL-01/Req48
  - APPL-01/Req57
duration: 35 min
completed: 2026-07-05
status: complete
---

# Phase 21 Plan 01: Transparent Proxy and Deployment Topology Summary

**Dynamic enterprise-CA TLS interception with AI traffic classification, fail-closed transparent proxy policy, reverse proxy tunneling, and appliance deployment mode selection**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-05T14:10:00Z
- **Completed:** 2026-07-05T14:45:32Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments

- Added `TLSInterceptor` and `generate_dynamic_cert()` for short-lived domain certificates signed by an enterprise CA, with TLS 1.3 server contexts.
- Added `AITrafficDetector` and `CertPinningDetector` for AI host/path classification and certificate-pinning policy signals.
- Added `TransparentProxy` with fail-closed HTTP 451 behavior, fail-open passthrough, dispatcher routing, header preservation, and TLS 1.3 outbound passthrough context.
- Added `ReverseProxy` with dispatcher forwarding, base URL rewrite, and HTTP CONNECT tunnel handling.
- Added `DeploymentMode`/`TopologyConfig` and startup wiring via `DEPLOYMENT_MODE`, with reverse, transparent, virtual, and physical appliance defaults.

## Task Commits

No task commits were created in this execution because the working tree already contained pre-existing staged and unstaged changes before Phase 21 started. Files and summary were left in place for review and later commit once the broader dirty tree is reconciled.

## Files Created/Modified

- `src/anonreq/proxy/tls_interceptor.py` - Dynamic TLS certificate generation, CA loading, TLS 1.3 context creation, health check.
- `src/anonreq/proxy/detection.py` - AI API domain/path classifier and certificate-pinning heuristic detector.
- `src/anonreq/proxy/transparent_proxy.py` - Transparent proxy request handling, fail-open/fail-closed policy, dispatcher routing, raw passthrough primitive.
- `src/anonreq/proxy/reverse_proxy.py` - Reverse proxy dispatcher handling, CONNECT tunnel response, upstream URL rewrite.
- `src/anonreq/deployment/modes.py` - Deployment mode enum and topology-specific configuration defaults.
- `src/anonreq/deployment/__init__.py` - Deployment package exports.
- `src/anonreq/proxy/__init__.py` - Proxy package exports for Phase 21 classes.
- `src/anonreq/main.py` - Deployment proxy factory and lifespan wiring.
- `tests/test_proxy_tls.py` - TLS interceptor certificate tests.
- `tests/test_proxy_topology.py` - Transparent proxy classification, pinning, fail-open/fail-closed tests.
- `tests/test_proxy_integration.py` - Deployment mode, reverse proxy, and transparent-to-dispatcher tests.

## Decisions Made

- Default `DEPLOYMENT_MODE` is `reverse`, preserving existing app startup behavior and avoiding CA file requirements unless an intercepting topology is selected.
- `ANONREQ_START_NETWORK_PROXY` gates listener startup. This allows the FastAPI app to own topology selection while tests and regular local runs avoid binding an appliance port unexpectedly.
- Certificate pinning detection is a conservative heuristic over client failure markers and absent SNI signals. This is testable and fits the plan's policy requirement without pretending ClientHello carries an explicit pinning flag.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Subagent stalled during Task 1**
- **Found during:** Task 1 (TLS interceptor implementation)
- **Issue:** The executor subagent staged only the TLS slice and did not return after two long wait windows.
- **Fix:** Closed the stalled subagent, preserved its staged TLS work, and completed Tasks 2 and 3 locally.
- **Files modified:** Phase 21 proxy, deployment, and test files listed above.
- **Verification:** Focused Wave 1 tests passed.
- **Committed in:** Not committed due dirty-tree constraint.

**2. [Rule 2 - Missing Critical] Listener autostart gate added**
- **Found during:** Task 3 (main.py lifespan wiring)
- **Issue:** Starting a transparent listener unconditionally during FastAPI app startup would bind ports during normal tests and require CA files outside transparent/virtual/physical deployments.
- **Fix:** Startup now always creates the deployment proxy object, but only calls `start()` when `ANONREQ_START_NETWORK_PROXY=true`.
- **Files modified:** `src/anonreq/main.py`
- **Verification:** Deployment proxy factory tests pass; reverse mode remains the default.
- **Committed in:** Not committed due dirty-tree constraint.

---

**Total deviations:** 2 auto-fixed (1 blocking execution issue, 1 startup safety issue).  
**Impact on plan:** The delivered behavior matches the plan's functional contract while keeping existing app startup stable.

## Issues Encountered

- Direct `python3 -c` import checks require `PYTHONPATH=src`; pytest already supplies this via `pyproject.toml`.
- The workspace had pre-existing dirty and staged changes before execution, so commits were intentionally deferred.

## Verification

- `pytest tests/test_proxy_tls.py tests/test_proxy_topology.py tests/test_proxy_integration.py -q` → 25 passed.
- `PYTHONPATH=src python3 -c "from anonreq.proxy.tls_interceptor import TLSInterceptor; print('TLS interceptor imports OK')"` → passed.
- `PYTHONPATH=src DEPLOYMENT_MODE=reverse python3 -c "from anonreq.deployment.modes import get_deployment_config, DeploymentMode; config = get_deployment_config('reverse'); assert config.mode == DeploymentMode.REVERSE; assert config.listen_port == 8080; print('Deployment modes OK')"` → passed.
- Artifact line counts meet plan minimums: `tls_interceptor.py` 203 lines, `transparent_proxy.py` 223 lines, `detection.py` 113 lines, `deployment/modes.py` 88 lines.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 21-02. The transparent/reverse proxy foundation and deployment topology config are available for the voice connector and later agent/firewall integration waves.

---
*Phase: 21-endpoint-visibility-sovereign-control*
*Completed: 2026-07-05*
