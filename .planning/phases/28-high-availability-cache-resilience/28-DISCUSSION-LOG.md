# Phase 28: High Availability Cache & Resilience - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-12
**Phase:** 28-High Availability Cache & Resilience
**Areas discussed:** Connection URL scheme resolution, Retry policy customization, Fail-closed behavior & health reporting

---

## Connection URL Scheme Resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Option A | Use custom sub-schemes in `ANONREQ_VALKEY_URL` (`redis+sentinel://` and `redis+cluster://`) | ✓ |
| Option B | Use separate dedicated environment variables | |

**User's choice:** Option A
**Notes:** Custom schemes keep the env/settings space cleaner and represent all configurations under a single unified cache connection string.

---

## Retry Policy Customization

| Option | Description | Selected |
|--------|-------------|----------|
| Option B | Self-healing defaults (clean settings footprint) | ✓ |
| Option A | Configurable retry settings via environment variables | |

**User's choice:** Option B
**Notes:** Hardcoded robust default retry rules are preferred to prevent configuration clutter, letting the application handle failovers transparently.

---

## Fail-Closed Behavior & Health Reporting

| Option | Description | Selected |
|--------|-------------|----------|
| Option A | Readiness probe fails (503), Liveness probe succeeds (200) | ✓ |
| Option B | Keep readiness active, return HTTP 503 on requests only | |

**User's choice:** Option A
**Notes:** Follows cloud-native/Kubernetes standard patterns, taking degraded instances out of routing pools while keeping the containers alive.

---

## the agent's Discretion

- Exact parsing mechanisms for Sentinel/Cluster formats from the URL string.
- Handling connection and read-only exceptions thrown during reelection failovers inside the retry loop.

## Deferred Ideas

None — discussion stayed within phase scope
