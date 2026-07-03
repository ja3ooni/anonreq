# Phase 08 Plan 02 Summary: Enterprise Policy Engine — PDP, PEP, ForwardingGuard, Middleware

## Overview
Wired the Enterprise Policy Engine into the gateway request pipeline with 4 components: PolicyDecisionPoint (PDP), PolicyEnforcementPoint (PEP), ForwardingGuard, and PolicyMiddleware. All components are fully tested and integrated.

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `src/anonreq/policy/pdp.py` | 156 | PolicyDecisionPoint — evaluates classification, rate-limit, spend, residency rules with fail-fast and decision caching |
| `src/anonreq/policy/pep.py` | 148 | PolicyEnforcementPoint — maps PolicyDecision → HTTP status codes (403/402/429/451/503) + structured error bodies |
| `src/anonreq/policy/forwarding_guard.py` | 93 | ForwardingGuard — validates policy decision exists, action is ALLOW/FLAG_AND_FORWARD, transformed_request is set, TTL not expired |
| `src/anonreq/middleware/policy.py` | 90 | PolicyMiddleware — FastAPI BaseHTTPMiddleware that gates /v1/* routes through PDP→PEP before route handlers |
| `src/anonreq/middleware/__init__.py` | 3 | Exports PolicyMiddleware |

## Files Modified

| File | Changes |
|------|---------|
| `src/anonreq/models/processing_context.py` | Added `policy_decision` and `policy_enforcement` fields |
| `src/anonreq/main.py` | Added PolicyMiddleware registration; lifespan creates PDP/PEP/ForwardingGuard/PolicyStore/UsageLimiter/SpendController/ResidencyRouter |

## Test Results — 57/57 passed

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/policy/test_pdp.py` | 21 | evaluate_classification (5), evaluate_rate_limit (3), evaluate_spend (3), evaluate_residency (3), evaluate_all (7) |
| `tests/policy/test_pep.py` | 18 | BLOCK→403/429/402/451/503 (7), ALLOW (2), FLAG_AND_FORWARD (2), ROUTE_LOCAL (1), structured bodies (3), transparency headers (3) |
| `tests/policy/test_forwarding_guard.py` | 8 | valid pass, no decision, BLOCK action, missing transformed_request, expired TTL, FLAG_AND_FORWARD no body, fail-closed, error body |
| `tests/policy/test_integration.py` | 10 | ALLOW passthrough, BLOCK early return, X-AnonReq-Blocked header, health skip, PDP 503, PEP 503, transparency headers, FLAG_AND_FORWARD header, ForwardingGuard as dependency, blocked dependency |

## Key Design Decisions

- **Fail-fast**: first BLOCK from classification/rate-limit/spend/residency chain short-circuits remaining checks
- **Decision caching**: in-memory `dict` keyed by `tenant_id:sha256(request_hash)[:16]` with 5s default TTL; reduces repeated evaluations
- **Fail-closed**: any exception in PDP/PEP/ForwardingGuard returns 503 (never forwards unsanitized)
- **Block type detection**: heuristic on `matched_rule_ids` and `reason` — rate_limit→429, spend→402, classification/residency→451, errors→503, generic→403
- **Middleware skips**: `/health`, `/metrics`, `/`, and non-`/v1/*` routes bypass policy evaluation
