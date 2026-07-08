---
phase: 18-agent-tool-call-governance
plan: 02
subsystem: tool-call-governance
tags:
  - tool-governance
  - approval-flow
  - pii-detection
  - reconstruction-detection
  - tdd
requires:
  - 18-01 (PDPToolEvaluator, ToolCall, ToolResult)
  - 14-01 (OversightService)
provides:
  - Async human approval flow for high-risk tool calls
  - Tool result PII inspection via PresidioClient
  - Reconstruction attempt detection (4 indicator types)
affects:
  - src/anonreq/main.py (lifespan wiring)
  - src/anonreq/governance/router.py (approval endpoints)
tech-stack:
  added:
    - PresidioClient (PII detection)
    - fakeredis (test storage)
  patterns:
    - TDD (RED/GREEN per task)
    - Async approval with Valkey-backed state
    - Hybrid sync+async reconstruction detection
key-files:
  created:
    - src/anonreq/governance/approval.py (423 lines)
    - src/anonreq/governance/tool_inspector.py (294 lines)
    - tests/test_approval.py (287 lines)
    - tests/test_tool_inspector.py (257 lines)
  modified:
    - src/anonreq/governance/__init__.py
    - src/anonreq/governance/router.py
    - src/anonreq/main.py
decisions:
  - "Redis TTL for approval keys = business TTL + 3600s to allow data-level expiry check"
  - "Reconstruction detection cache_manager only queried when PII is detected (performance)"
  - "Suppression threshold set to >=0.9 confidence (not >0.9)"
  - "Approval endpoints share /v1/oversight/approvals/ prefix with Phase 14 oversight router (known overlap)"
metrics:
  duration: 0h 10m 48s
  completed: 2026-07-03T06:57:09Z
status: complete
---

# Phase 18 Plan 02: Agent Tool Call Governance - Wave 2 Summary

Async human approval flow for high-risk tool calls with tool result PII and reconstruction detection.

## What was built

### Task 1: Async Approval Flow (ApprovalManager)

**`src/anonreq/governance/approval.py`**
- `ApprovalManager` with 256-bit random token generation (`secrets.token_urlsafe(32)`)
- Valkey-backed pending approval store with configurable TTL (default 300s)
- Redis TTL = business TTL + 3600s safety margin to enable data-level expiry checks
- Atomic approve/deny with 404 for unknown tokens, 409 for duplicate resolution
- `cleanup_expired()` using Redis SCAN for orphaned approval cleanup
- Integration with Phase 14 OversightService via `create_approval_request()`

**`src/anonreq/governance/router.py`** — Approval endpoints:
- `POST /v1/oversight/approvals` — Create approval (returns token + status=pending)
- `GET /v1/oversight/approvals/{token}` — Poll status (pending/approved/denied/expired/not_found)
- `POST /v1/oversight/approvals/{token}/approve` — Resolve to approved
- `POST /v1/oversight/approvals/{token}/deny` — Resolve to denied
- `POST /v1/oversight/approvals/cleanup` — Delete expired approvals

**`src/anonreq/main.py`** — ApprovalManager wired in lifespan with OversightService integration.

### Task 2: Tool Result Inspection (ToolResultInspector)

**`src/anonreq/governance/tool_inspector.py`**
- PII detection via Phase 2 PresidioClient (email, phone, SSN, etc.)
- Reconstruction attempt detection using 4 indicator types:
  1. Token pattern matches (`[TYPE_N]` placeholders)
  2. Original values matching stored token mappings (CacheManager scan)
  3. Reconstruction prompt language (8 regex patterns for "regenerate", "fill in", etc.)
  4. Suspicious bracket patterns (3+ non-token bracket instances)
- Confidence scoring 0.0-1.0 with 0.7 detection threshold
- Action determination: allow / alert / suppress (suppress at >=0.9 confidence)
- Graceful PresidioClient error handling (timeouts/HTTP errors don't block)
- `to_dict()` serialization for audit metadata

## TDD Gate Compliance

| Gate | Task 1 (ApprovalManager) | Task 2 (ToolResultInspector) |
|------|------------------------|---------------------------|
| RED  | `1fa0bcb` test(18-02)  | `eefecaf` test(18-02)     |
| GREEN| `82757ad` feat(18-02)  | `1c43e23` feat(18-02)     |

Both RED and GREEN gate commits present for both tasks. ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `__import__("datetime")` replaced with proper import**
- **Found during:** Task 1 implementation
- **Issue:** Code smell using `__import__` inline instead of module-level `from datetime import timedelta`
- **Fix:** Added proper timedelta import at module top; amended into feat commit
- **Commit:** `82757ad` (amended)

**2. [Rule 3 - Blocking] ToolResultInspector built as JSON schema validator instead of PII detector**
- **Found during:** Post-implementation review against PLAN.md
- **Issue:** Initial implementation validated JSON schemas; plan requires PII detection via PresidioClient + reconstruction attempt detection via CacheManager
- **Fix:** Rewrote both tests and implementation to match plan specification. Separated Task 2 tests (`test_tool_inspector.py`) from old JSON-schema tests.
- **Files:** `src/anonreq/governance/tool_inspector.py`, `tests/test_tool_inspector.py`

**3. [Rule 1 - Bug] Sync `run_until_complete` in async test context**
- **Found during:** Task 2 test execution
- **Issue:** `_detect_reconstruction_attempts` used `loop.run_until_complete()` which fails in pytest-asyncio context
- **Fix:** Made `_detect_reconstruction_attempts` fully async
- **Commit:** `1c43e23`

**4. [Rule 3 - Blocking] Test fixture used `ToolCall()` without required `format` parameter**
- **Found during:** Task 2 initial test run
- **Issue:** `ToolCall.__init__()` requires `format` parameter
- **Fix:** Added `format="openai"` to all test fixtures
- **Commit:** `1c43e23`

## Key Decisions

1. **Approval TTL architecture**: Redis TTL (safety net) set to max(ttl+3600, 7200) while business-level expiry is tracked in the record's `expires_at` field. This prevents key auto-deletion before human-readable expiry can be checked.

2. **Reconstruction detection scope**: CacheManager is only queried for mapping values when PII is detected. This is a performance optimization — no point checking mapping matches if there's no PII to reconstruct.

3. **Approval endpoint routing**: Approval endpoints use `/v1/oversight/approvals/` prefix, sharing with Phase 14 oversight routes. FastAPI route precedence means the governance `approval_router` is registered first, taking priority for `GET /{param}` matches.

## Known Stubs

None — all implementations are complete with full test coverage.

## Threat Flags

None — all new surface (approval endpoints, token generation, PII detection) is covered by the threat model (T-18-02-01 through T-18-02-05).

## Verification

- [x] `pytest tests/test_approval.py -x --tb=short -v` — 12 passed
- [x] `pytest tests/test_tool_inspector.py -x --tb=short -v` — 18 passed
- [x] Both suites together — 30 passed
- [x] ApprovalManager creates 256-bit URL-safe tokens
- [x] Approval record stored in Valkey with TTL, single-use
- [x] GET /v1/oversight/approvals/{token} returns status (pending/approved/denied/expired)
- [x] POST /v1/oversight/approvals/{token}/approve and /deny work
- [x] Second approve/deny on same token returns HTTP 409
- [x] Expired token returns status=expired
- [x] ToolResultInspector detects PII via PresidioClient
- [x] Reconstruction detection: token patterns, mapping matches, prompt language, bracket patterns
- [x] High-confidence reconstruction → content suppression
- [x] All files committed to git

## Self-Check: PASSED

- [x] `src/anonreq/governance/approval.py` exists (423 lines)
- [x] `src/anonreq/governance/tool_inspector.py` exists (294 lines)
- [x] `tests/test_approval.py` exists (287 lines)
- [x] `tests/test_tool_inspector.py` exists (257 lines)
- [x] All 5 commits are in git history
- [x] 30 tests pass
