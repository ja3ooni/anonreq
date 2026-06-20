# Phase 6 Discussion Log

**Gathered:** 2026-06-20

## Areas Discussed

### TEST-04: Failure Injection Scope
- **All 5 failure modes:** Detection, Cache, ForwardingGuard, Timeout, Circuit Breaker
- **Verified per mode:** forwarded=0, cleanup=True, metric incremented, audit written
- **Both paths:** non-streaming + streaming
- **Metrics verification:** snapshot before/after for fail_secure_events_total, requests_total{500}

### TEST-06: No-PII-in-Logs Definition
- **PII substring:** any original entity value present in request or response
- **Log pathways tested:** application, structured JSON, audit, exception/traceback, metrics labels, access logs
- **Hypothesis strategy:** generate synthetic PII across all entity types × all pipeline paths

### TEST-08: Cross-Request Randomization
- **Decision:** Same value across requests → different tokens. Zero collisions across 1000+ sessions.
- **Mechanism:** UUIDv7 session seed → deterministic offset from seed+value+type
- **Collision bound:** P(duplicate) ≤ 2⁻³²

### Metrics Integration in TEST-04
- **Decision:** Yes. Every fail-secure test verifies metric counters. Metrics are part of the contract.

### Streaming Disconnect Tests
- **Decision:** Close in Phase 6, not deferred.
- **Added:** TEST-07E (disconnect during tokenization), TEST-07F (disconnect during restoration), TEST-07G (disconnect during provider stream), TEST-07H (disconnect + timeout race).

## Architectural Guardrails Added

- **AG-19:** Security Invariants Must Be Proven Under Fault
- **AG-20:** Metrics Are Part of the Contract

## Documents Generated

- `06-CONTEXT.md` — All decisions (D-162 through D-189)
- `06-ARCHITECTURE.md` — Test architecture, failure injection model, verification flows
- `06-TASK-BREAKDOWN.md` — 3 plans, 8 test files
- `06-TEST-PLAN.md` — 24 individual property tests, hypothesis settings, 10 invariants
- `07-SECURITY-ACCEPTANCE.md` — Formal gate document

## Key Insight

Phase 6 is the security proof phase. Every invariant must be demonstrated under fault injection by Hypothesis, not merely asserted in a unit test.

## Deferred Ideas

- Performance regression tests under Hypothesis — Phase 7+
- Fuzz testing — Phase 8+
- Differential testing (Presidio version comparison) — Phase 11+
- Adversarial PII reconstruction from tokens — Phase 14+
