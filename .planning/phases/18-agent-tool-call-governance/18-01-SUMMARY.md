---
phase: 18-agent-tool-call-governance
plan: 01
subsystem: governance
tags:
  - tool-governance
  - pdp
  - yaml-policy
  - permission-evaluation
  - isolation

# Dependency graph
requires:
  - phase: 08-01
    provides: Phase 8 policy YAML structure (config/policy.yaml)
  - phase: 09-01
    provides: Multimodal tool call awareness patterns
provides:
  - ToolPolicyParser — parse and validate per-provider tool policies from YAML
  - ToolExtractor — extract tool calls and results from OpenAI, Anthropic, MCP formats
  - PDPToolEvaluator — evaluate tool permission against policy with isolation support
affects:
  - 18-02: Tool governance API router and integration
  - 18-03: Tool governance streaming restoration

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD for all components (test → feat → refactor)
    - Dataclass-based domain models (ToolCall, ToolResult, ToolDecision, ToolPolicy)
    - 4-tier permission model (allow, allow_with_audit, require_human_approval, block)
    - Cross-domain isolation (model ↔ host provider boundary enforcement)
    - Cross-delegation credential isolation for tool access

key-files:
  created:
    - src/anonreq/governance/tool_policy_parser.py
    - src/anonreq/governance/tool_extractor.py
    - src/anonreq/governance/pdp_tool_evaluator.py
    - tests/test_tool_policy_parser.py
    - tests/test_tool_extractor.py
    - tests/test_pdp_tool_evaluator.py
  modified:
    - src/anonreq/governance/__init__.py
    - config/policy.yaml
    - src/anonreq/models/processing_context.py

key-decisions:
  - "ToolPolicyParser is a pure-data parser (no I/O) — YAML loading delegated to Phase 8 config loader"
  - "Pattern matching priority: exact match > prefix match (ends with *) > glob match"
  - "Domain detection uses provider naming convention: host_MCP providers → host, well-known model providers → model"
  - "Cross-domain isolation enforced at PDP level: model → host (or vice versa) → BLOCK + fail-secure error"
  - "Credential isolation checks ToolCall.credential_context against session delegation_id from audit_metadata"
  - "BLOCK permission attaches ToolBlockedError to ProcessingContext via fail_secure() per fail-secure invariant"
  - "ToolResult evaluation is metadata-only audit (no content logging) per no-PII-in-logs requirement"

patterns-established:
  - "TDD: RED test → GREEN implementation → optional REFACTOR, verified with pytest"
  - "Fail-secure integration: blocked tools raise ToolBlockedError onto context.errors"
  - "Provider-scoped tool policy: each provider has its own tool registry with risk classification"
  - "ToolExtractor domain detection is header-based (X-AnonReq-Tool-Domain) with format-aware defaults"

requirements-completed:
  - APPL-AGENT-01
  - APPL-AGENT-02

# Metrics
duration: 5min
completed: 2026-07-03
status: complete
---

# Phase 18 Plan 01: Tool Policy Parser, Multi-Format Tool Call Extractor, PDP #2 Tool Evaluator

**Tool governance foundation: YAML policy parser (glob/prefix/exact matching), 3-format tool call extractor (OpenAI/Anthropic/MCP), and PDP #2 permission evaluator with cross-domain and credential isolation**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-03T08:37:25+02:00
- **Completed:** 2026-07-03T08:42:00+02:00
- **Tasks:** 3 (Task 1: TDD RED+GREEN+config, Task 2: TDD RED+GREEN, Task 3: auto)
- **Files modified:** 14

## Accomplishments

- **ToolPolicyParser** parses per-provider tool policies from YAML with glob/prefix/exact name matching, 4-tier permissions (allow/allow_with_audit/require_human_approval/block), risk classification, parameter rules, and validation
- **ToolExtractor** extracts tool calls and results from OpenAI (tool_calls), Anthropic (tool_use content blocks), and MCP (tools/call) formats with format auto-detection and domain resolution
- **PDPToolEvaluator** evaluates tool permission against policy, enforces model↔host domain isolation, checks cross-delegation credential isolation, and integrates fail-secure error handling

## Task Commits

Each task was committed atomically:

1. **Task 1: Tool Policy Parser** — RED `166d4fa` → GREEN `571e8de` → config+exports `3cac65d`
2. **Task 2: Tool Call Extractor** — RED `6664766` → GREEN `9fb1c07`
3. **Task 3: PDP Tool Evaluator** — `24b63c8` (implementation + tests)

_Note: Tasks 1 and 2 follow TDD (test → feat → refactor). Task 3 is auto (single commit, no TDD)._

## Files Created/Modified

- `src/anonreq/governance/tool_policy_parser.py` — ToolPermission/ToolRiskLevel enums, ToolPolicy/ProviderToolPolicy dataclasses, ToolPolicyParser with parse/get_policy/validate (113 lines)
- `src/anonreq/governance/tool_extractor.py` — ToolCall/ToolResult dataclasses, ToolExtractor with extract_calls/extract_results/detect_format/detect_domain (397 lines)
- `src/anonreq/governance/pdp_tool_evaluator.py` — ToolDecision dataclass, ToolBlockedError exception, PDPToolEvaluator with evaluate/evaluate_tool_result/get_permitted_actions (378 lines)
- `src/anonreq/governance/__init__.py` — Exports all Phase 18 tool governance classes
- `config/policy.yaml` — Added per-provider tool governance sections (openai, anthropic, gemini, host_mcp) with defaults
- `src/anonreq/models/processing_context.py` — Added `requires_approval` field for tool governance approval flow
- `tests/test_tool_policy_parser.py` — 28 tests (parse, validation, get_policy matching, parameter rules)
- `tests/test_tool_extractor.py` — 28 tests (extract calls/results for all 3 formats, format detection, domain detection)
- `tests/test_pdp_tool_evaluator.py` — 22 tests (permission evaluation, cross-domain isolation, credential isolation, tool result audit, get_permitted_actions, error handling)

## Decisions Made

- **No new YAML loading dependency** — ToolPolicyParser accepts parsed dicts, YAML loading delegated to Phase 8's `PolicyConfig.load_policy_config()`, avoiding a new config loading pathway
- **Pattern matching priority** — exact tool name > prefix wildcard (ends with `*`) > fnmatch glob > unknown default (based on risk classification or ALLOW)
- **Domain detection heuristic** — provider names starting with `host_` → host domain; known model providers (openai, anthropic, gemini, etc.) → model domain; unknown → model domain (conservative)
- **Credential isolation key** — ToolCall.credential_context compared against ProcessingContext.audit_metadata["delegation_id"]; mismatch → BLOCK + fail-secure
- **ToolResult is metadata-only** — evaluate_tool_result records tool_id, name, is_error to audit_metadata but never logs raw content (no-PII-in-logs compliance)

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `hasattr(dataclass_class, field_name)` returns False for plain-annotated dataclass fields — fixed test helper to use `__dataclass_fields__` instead
- Added `credential_context` to ToolCall dataclass mid-implementation — PDPToolEvaluator already expected it but the field was missing from the dataclass (Rule 2 deviation: missing critical functionality for delegation isolation)

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 18-02 can integrate PDPToolEvaluator into the tool governance API router
- Phase 18-03 can wire PDP into streaming restoration for SSE tool decision injection
- All three components ready for integration testing with Phase 8 policy config loader

---

*Phase: 18-agent-tool-call-governance*
*Completed: 2026-07-03*
