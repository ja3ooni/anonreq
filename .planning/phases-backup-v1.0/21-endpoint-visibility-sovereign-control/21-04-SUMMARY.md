---
phase: 21-endpoint-visibility-sovereign-control
plan: 04
subsystem: agent
tags: [mcp, agent-governance, tool-calls, tool-results, content-type-dispatcher]
requires:
  - phase: 09-content-type-dispatcher
    provides: content type routing primitives
  - phase: 10-ai-security-firewall
    provides: prompt injection detection patterns and firewall interface
  - phase: 21-01
    provides: appliance routing foundation
provides:
  - MCP JSON-RPC message parsing and internal ToolCall/ToolResult mapping
  - Agent tool-call schema validation and injection blocking
  - Tool result value-only sanitization with JSON key preservation
  - Error redaction for stack traces, internal IPs, and environment variable names
  - Dispatcher content types for agent_tool_call, agent_tool_result, and mcp_message
affects: [phase-21, agent, multimodal, monitoring]
tech-stack:
  added: []
  patterns: [pydantic-agent-schema, low-cardinality-agent-metrics, value-only-json-sanitization]
key-files:
  created:
    - src/anonreq/agent/config.py
    - src/anonreq/agent/mcp_parser.py
    - src/anonreq/agent/result_sanitizer.py
    - src/anonreq/agent/schema.py
    - src/anonreq/agent/tool_inspector.py
    - tests/test_agent_mcp.py
    - tests/test_agent_result_sanitizer.py
    - tests/test_agent_tool_inspector.py
  modified:
    - src/anonreq/agent/__init__.py
    - src/anonreq/monitoring/metrics.py
    - src/anonreq/multimodal/dispatcher.py
    - src/anonreq/multimodal/models.py
    - tests/multimodal/test_dispatcher.py
key-decisions:
  - "Unknown agent tools are blocked by default via block_unknown_tools=True to satisfy T-21-04-01; configured tools can still use the default allow_with_audit policy."
  - "Tool result audit events are stored on ToolResultSanitizer.audit_events rather than injected into returned tool content, preserving result structure and avoiding metadata leakage."
  - "Agent metrics use only action/redacted labels; tool names, tenant IDs, request IDs, and raw payload markers are intentionally excluded."
requirements-completed:
  - APPL-01/Req51
  - APPL-01/Req59
duration: 18 min
completed: 2026-07-05T15:23:49Z
status: complete
---

# Phase 21 Plan 04: MCP and Agent Tool Governance Summary

**MCP parsing, outbound tool-call injection/schema governance, inbound tool-result sanitization, error redaction, dispatcher routing, and agent metrics**

## Performance

- **Duration:** 18 min
- **Completed:** 2026-07-05T15:23:49Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments

- Added `ToolCall`, `ToolResult`, `ToolArgumentSchema`, `InspectionResult`, and `AgentContentType` models under `anonreq.agent`.
- Added `ToolGovernanceConfig` with per-tool policies, schema registry, feature toggles, default audit policy, and explicit unknown-tool blocking.
- Added `MCPParser` for MCP JSON-RPC frame detection, protocol negotiation, `tools/call` mapping, result mapping, malformed-frame errors, and metadata-only error responses.
- Added `ToolCallInspector` for per-tool policy enforcement, simple JSON-schema validation, recursive argument scanning, optional firewall integration, and injection blocking.
- Added `ToolResultSanitizer` for value-only recursive traversal, detection/tokenization, JSON key preservation, stack trace/internal IP/env-var redaction, audit event tracking, and token mapping capture.
- Extended multimodal `ContentType` and dispatcher routing for `agent_tool_call`, `agent_tool_result`, and `mcp_message`.
- Added Prometheus counters `anonreq_agent_tool_calls_inspected_total` and `anonreq_agent_tool_results_sanitized_total` with low-cardinality labels.

## TDD Gate Compliance

- RED gate: `pytest tests/test_agent_mcp.py tests/test_agent_tool_inspector.py tests/test_agent_result_sanitizer.py -q` failed with missing module imports before implementation.
- GREEN gate: focused agent and dispatcher suites pass after implementation.

## Task Commits

No task commits were created before this summary because the workspace already had pre-existing staged and unstaged changes from other waves. A scoped commit was attempted after summary creation if the dirty index allowed committing only Plan 21-04 files.

## Files Created/Modified

- `src/anonreq/agent/__init__.py` - Agent package exports.
- `src/anonreq/agent/config.py` - Tool governance configuration.
- `src/anonreq/agent/schema.py` - Agent/tool-call internal schemas.
- `src/anonreq/agent/mcp_parser.py` - MCP parser and ToolCall/ToolResult mapping.
- `src/anonreq/agent/tool_inspector.py` - Tool-call policy/schema/injection inspection.
- `src/anonreq/agent/result_sanitizer.py` - Tool-result tokenization and error redaction.
- `src/anonreq/multimodal/models.py` - Agent/MCP content type enum values.
- `src/anonreq/multimodal/dispatcher.py` - Agent/MCP MIME routing.
- `src/anonreq/monitoring/metrics.py` - Agent governance counters.
- `tests/test_agent_mcp.py` - MCP parser tests.
- `tests/test_agent_tool_inspector.py` - Tool inspector tests.
- `tests/test_agent_result_sanitizer.py` - Result sanitizer tests.
- `tests/multimodal/test_dispatcher.py` - Dispatcher coverage for agent/MCP content types.

## Decisions Made

- Unknown tools are blocked by default. This is stricter than a blanket allow-with-audit fallback and directly implements the plan threat model mitigation for T-21-04-01.
- Returned tool result content is not augmented with audit metadata. Audit events are exposed on the sanitizer object so callers can emit metadata-only logs without changing tool output structure.
- Schema enforcement uses local validation for the subset this plan needs (`required`, JSON types, and `additionalProperties: false`) instead of adding a new dependency.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Unknown-tool blocking added**
- **Found during:** Task 1
- **Issue:** The task text said the default config allows all with audit, but the threat model requires unknown tools to be blocked by default.
- **Fix:** Added `block_unknown_tools=True` while keeping `default_tool_policy="allow_with_audit"` for configured/default policy behavior.
- **Files modified:** `src/anonreq/agent/config.py`, `src/anonreq/agent/tool_inspector.py`

**2. [Rule 2 - Missing Critical] Agent metrics added**
- **Found during:** Success criteria review
- **Issue:** The tasks omitted metric implementation details, but success criteria require two Prometheus counters.
- **Fix:** Added low-cardinality counters and incremented them from the inspector and sanitizer.
- **Files modified:** `src/anonreq/monitoring/metrics.py`, `src/anonreq/agent/tool_inspector.py`, `src/anonreq/agent/result_sanitizer.py`

## Known Stubs

None - no placeholder or TODO stubs were introduced.

## Verification

- `pytest tests/test_agent_mcp.py tests/test_agent_tool_inspector.py tests/test_agent_result_sanitizer.py tests/multimodal/test_dispatcher.py -q` -> 43 passed.
- `PYTHONPATH=src python3 -c "from anonreq.agent.schema import ToolCall, ToolResult, InspectionResult, AgentContentType; ..."` -> `Agent schema OK`.
- Artifact line counts: `mcp_parser.py` 183 lines, `tool_inspector.py` 175 lines, `result_sanitizer.py` 138 lines.

## Self-Check: PASSED

- Created files exist: agent config/schema/parser/inspector/sanitizer and three focused test files.
- Required dispatcher integration exists for `agent_tool_call`, `agent_tool_result`, and `mcp_message`.
- Plan acceptance tests pass.
- No summary-blocking known stubs remain.

## User Setup Required

None.

## Next Phase Readiness

Ready for the remaining Phase 21 waves. The gateway can now identify agent/MCP content types and enforce basic tool-call and tool-result governance without adding external dependencies.

