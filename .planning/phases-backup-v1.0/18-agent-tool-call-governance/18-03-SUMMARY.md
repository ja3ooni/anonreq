---
phase: 18-agent-tool-call-governance
plan: 03
status: complete
tags: [tool-governance, audit, metrics, property-tests, hypothesis]
requires: [18-01, 18-02]
provides: [audit-events, prometheus-metrics, governance-invariants]
affects: [pdp-tool-evaluator, tool-policy-parser]
tech-stack:
  added: [prometheus_client, hypothesis, structlog]
  patterns: [dataclass-events, prometheus-counters, property-based-testing]
key-files:
  created:
    - src/anonreq/governance/audit.py
    - src/anonreq/governance/metrics.py
    - tests/test_governance_audit.py
    - tests/test_governance_metrics.py
    - tests/property/test_tool_governance.py
  modified:
    - src/anonreq/governance/pdp_tool_evaluator.py
    - src/anonreq/governance/tool_policy_parser.py
decisions:
  - "Audit events emitted via structlog BoundLogger to align with Phase 5 audit logger"
  - "FORBIDDEN_AUDIT_KEYS as module-level set, not dataclass field (avoids Python 3.14 mutable-default rejection)"
  - "emit_tool_audit_event pops 'event' from dict before passing kwargs to avoid structlog event key collision"
  - "Property tests use fresh per-test evaluator via session-scoped fixture to avoid Hypothesis function-scoped fixture warnings"
  - "Counter values read via generate_latest() exposition format (public API) instead of private _value attributes"
metrics:
  duration: "~45 min"
  completed: 2026-07-03
  task_count: 2
  file_count: 7
  test_count: 73
  test_pass_rate: 100%
---

# Phase 18 Plan 03: Agent Tool Call Governance — Wave 3 Summary

## One-liner
Tool governance audit events (7 types), Prometheus counters (3 metrics), and Hypothesis property tests (6 invariants, 20 tests) for agent/tool call governance observability and correctness guarantees.

## What was built

### Task 1: Tool governance audit events and Prometheus metrics

**`src/anonreq/governance/audit.py`** (138 lines):
- `ToolAuditEventType` enum with 7 event types: `TOOL_ALLOWED`, `TOOL_BLOCKED`, `TOOL_APPROVAL_REQUIRED`, `TOOL_APPROVAL_GRANTED`, `TOOL_APPROVAL_DENIED`, `TOOL_RESULT_PII_DETECTED`, `TOOL_RESULT_RECONSTRUCTION_DETECTED`
- `ToolAuditEvent` dataclass with metadata-only fields (no raw arguments, no PII, no token mappings)
- `FORBIDDEN_AUDIT_KEYS` constant: `{"tool_arguments", "raw_content", "pii_value", "token_value"}`
- `tool_audit_event_to_dict()` serializes event with `tool_` prefix on event name, excludes None values
- `emit_tool_audit_event()` sends structured JSON via `audit_logger.info(event_name, **fields)`

**`src/anonreq/governance/metrics.py`** (64 lines):
- `TOOL_CALLS_COUNTER` — `anonreq_tool_calls_total` with `[permission, domain, provider]` labels
- `TOOL_BLOCKS_COUNTER` — `anonreq_tool_blocks_total` with `[tool_name, domain, reason]` labels
- `TOOL_RESULT_VIOLATIONS_COUNTER` — `anonreq_tool_result_violations_total` with `[type_label]` labels
- `register_tool_governance_metrics(registry)` for custom CollectorRegistry support

**Tests** (31 tests covering both modules):
- Event type values, all 7 types present
- Required fields, default values, UTC timestamps
- `to_dict` serialization: key prefix, field presence, None exclusion
- No raw tool arguments, PII, or token patterns in serialized output
- Reconstruction/approval fields included when set
- Logger emission via MagicMock and correct event names
- Counter increment with label separation, multiple increments, different label values
- Custom registry registration and initial values
- Label cardinality safety (no tenant/session labels)
- Global counter smoke tests

### Task 2: Property-based tests for tool governance invariants

**`tests/property/test_tool_governance.py`** (904 lines, 20 tests):
- **Invariant 1 — Permission determinism** (2 tests, 100+ examples): same tool+provider+domain → same permission and risk_level
- **Invariant 2 — Format-switching bypass resistance** (1 test): same tool via openai vs anthropic → same permission
- **Invariant 3 — Cross-domain isolation** (2 tests): model↔host always BLOCK with isolation reason; same-domain NOT blocked by isolation
- **Invariant 4 — Credential isolation** (4 tests): mismatched delegation always BLOCK with credential reason; same delegation NOT blocked; no credential context NOT blocked; credential without session NOT blocked
- **Invariant 5 — No raw values in audit** (4 tests, 400+ examples): FORBIDDEN_AUDIT_KEYS never appear in output; no `[TYPE_N]` token patterns; no PII-looking values; emitted events carry no forbidden keys
- **Invariant 6 — Low-risk unlisted default ALLOW** (2 tests, 200+ examples): unlisted tool → ALLOW; CRITICAL classified tool → REQUIRE_HUMAN_APPROVAL
- **Extra invariants**: tool result always adds audit key; tool result audit no raw content; BLOCK always adds ToolBlockedError to context; non-BLOCK adds no error; REQUIRE_HUMAN_APPROVAL sets context flag

### Bugfix (Rule 2)

Fixed `PDPToolEvaluator._get_tool_risk_level()` to consult the provider's `risk_classification` map for unlisted tools. Previously only checked individual tool policy entries — unlisted tools classified as CRITICAL in the risk map would incorrectly default to ALLOW instead of REQUIRE_HUMAN_APPROVAL. Added `ToolPolicyParser.get_provider_policy()` to expose provider-level policy data.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Unlisted CRITICAL risk tools ignored classification map**
- **Found during:** Task 2 — property test `test_unlisted_critical_risk_needs_approval` failed
- **Issue:** `_get_tool_risk_level()` only checked individual tool policy entries, not the provider's risk_classification map. Tools listed in `tool_risk_classification` as `critical` but not in the `tools` list would default to ALLOW instead of REQUIRE_HUMAN_APPROVAL
- **Fix:** Added fallback in `_get_tool_risk_level()` to check `ProviderToolPolicy.risk_classification` for unlisted tools. Added `ToolPolicyParser.get_provider_policy()` to expose the full provider policy
- **Files modified:** `src/anonreq/governance/pdp_tool_evaluator.py`, `src/anonreq/governance/tool_policy_parser.py`
- **Commit:** `3f0f279`

**2. [Rule 1 - Bug] Metrics tests used private _value attribute**
- **Found during:** Task 1 — `counter._value.get()` failed with AttributeError
- **Issue:** prometheus_client version on Python 3.14 uses different internal attribute names
- **Fix:** Rewrote all metric value reads to use `generate_latest()` exposition format parsing (public API)
- **Files modified:** `tests/test_governance_metrics.py` (entirely rewritten)
- **Commit:** `73aef5a`

**3. [Rule 1 - Bug] Audit test used structlog in a way incompatible with test buffer capture**
- **Found during:** Task 1 — `test_emits_via_structlog_logger` could not capture structlog output via StreamHandler
- **Issue:** structlog with default PrintLoggerFactory writes to stdout, not through stdlib handlers
- **Fix:** Replaced with `test_emits_with_correct_event_name` and `test_emits_no_forbidden_field_names` using MagicMock
- **Files modified:** `tests/test_governance_audit.py`
- **Commit:** `73aef5a`

## Success Criteria Verification

- [x] 7 audit event types defined (ToolAuditEventType enum)
- [x] Audit events contain metadata only — verified by property tests
- [x] No token patterns `[TYPE_N]` in any audit event field
- [x] Prometheus counters: anonreq_tool_calls_total, anonreq_tool_blocks_total, anonreq_tool_result_violations_total
- [x] Property test: permission determinism (100+ examples → same decision)
- [x] Property test: format-switching bypass resistance (openai/anthropic → same decision)
- [x] Property test: cross-domain isolation (model→host always BLOCK)
- [x] Property test: credential isolation (cross-delegation always BLOCK)
- [x] Property test: no raw values in audit events (400+ examples)
- [x] Property test: unlisted low-risk tools default to ALLOW (200+ examples)
- [x] All 3 test suites pass (73 tests total)
- [x] All files committed to git

## Test Results

```
tests/test_governance_audit.py ............. 18 passed
tests/test_governance_metrics.py ........... 13 passed
tests/property/test_tool_governance.py ..... 20 passed
tests/test_pdp_tool_evaluator.py .......... 22 passed
----------------------------------------------------
Total: 73 passed, 0 failed, 0 errors
```

## Threat Model Compliance

| Threat ID | Disposition | Coverage |
|-----------|-------------|----------|
| T-18-03-01 Info Disclosure | mitigate | Field allowlist enforced via FORBIDDEN_AUDIT_KEYS + property test |
| T-18-03-02 Metrics Tampering | accept | In-memory counters, no persistence |
| T-18-03-03 Property Test Bypass | mitigate | 20 property tests run on every change |

## Key Commits

| Hash | Message |
|------|---------|
| `73aef5a` | feat(18-03): add tool governance audit events and Prometheus metrics |
| `3f0f279` | feat(18-03): add property-based tests for tool governance invariants |

## Threat Flags

None — all security-relevant surface (audit events and metrics) is covered by the plan's threat model.

## Known Stubs

None — all files deliver complete functionality.

## Self-Check: PASSED

All 7 files verified on disk. Both commits exist in git log. SUMMARY.md confirms all success criteria met.

