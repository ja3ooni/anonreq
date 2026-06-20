# Security Acceptance Gate — AnonReq MVP

**Phase:** 6
**Signed:** _(to be signed after all Phase 6 property tests pass)_

## Purpose

This document is the formal security acceptance gate for the AnonReq v1.0 MVP. No Phase 7 work begins until all gates are verified passing.

## Gates

| # | Gate | Test | Status |
|---|------|------|--------|
| 1 | **No PII Leaks** | TEST-06 — synthetic PII across all entity types and all pipeline paths produces zero entity values in any log sink | ❌ Pending |
| 2 | **No Fail-Open Paths** | TEST-04 — all 5 failure modes in both streaming and non-streaming paths produce HTTP 5xx, 0 bytes forwarded | ❌ Pending |
| 3 | **No Orphaned Mappings** | TEST-07E through TEST-07H — disconnect at any pipeline point produces cleanup_session() exactly once, 0 orphaned Valkey keys | ❌ Pending |
| 4 | **100% Cleanup Coverage** | Every TEST-04 variant verifies SessionCleanup._cleaned == True | ❌ Pending |
| 5 | **Cross-Request Token Reuse** | TEST-08 — 1000+ sessions with same entity value produce zero token collisions | ❌ Pending |
| 6 | **Disconnect Tests 100% Pass** | TEST-07E through TEST-07H — all disconnect adversarial tests pass | ❌ Pending |
| 7 | **Metrics Validation Pass** | Every fail-secure test verifies `anonreq_fail_secure_events_total` incremented correctly | ❌ Pending |
| 8 | **P95 Latency Within Target** | Phase 5 k6 load test confirms P95 overhead ≤ 100ms at 50 concurrent users, 1000-word prompts | ❌ Pending |
| 9 | **Streaming Invariants Pass** | TEST-07A through TEST-07D (Phase 3) + TEST-07E through TEST-07H (Phase 6) all pass | ❌ Pending |

## Sign-Off

| Role | Name | Date |
|------|------|------|
| Security Verification | _(all gates pass)_ | — |
| Product Owner | _(reviewed)_ | — |

## Post-Acceptance

After all gates pass:

1. Sign this document (date + commit)
2. Proceed to **Phase 6.5: Production Readiness Review**
3. Then **Phase 7: Developer Experience & Documentation**

---

*Document: 07-SECURITY-ACCEPTANCE.md*
*Created: 2026-06-20*
