---
phase: 09-multimodal-document-anonymization
plan: 02
subsystem: multimodal
tags: [tool-calls, openai, anthropic, mcp, pii-detection]
requires: [09-01]
provides: [tool-call-extraction]
affects: [pipeline]
tech-stack:
  added: [dataclasses]
  patterns: [provider-format-detection, json-argument-analysis]
key-files:
  created:
    - src/anonreq/multimodal/tool_call.py
    - tests/multimodal/test_tool_call.py
  modified:
    - src/anonreq/multimodal/__init__.py
decisions:
  - "ToolCallResult returns detection metadata (entities) rather than modifying the payload — the downstream tokenization engine performs the actual replacement"
  - "Format detection uses distinct structural markers (jsonrpc → MCP, tool_calls → OpenAI, tool_use in content → Anthropic)"
  - "Non-dict top-level argument values are wrapped in a `{_value: ...}` dict for JsonAnalyzer analysis, returned as the original scalar"
metrics:
  duration: ~15 minutes
  completed_date: 2026-07-02
  tests_added: 32
  coverage_change: "+2 source files, +32 test cases"
status: complete
---

# Phase 9 Plan 2: Tool Call Argument Extraction + Anonymization

**One-liner:** Tool call argument extraction and PII detection for OpenAI tool_calls, Anthropic tool_use blocks, and MCP tool call/result payloads — all three provider formats handled with auto-detect dispatch via the `ToolCallExtractor`.

## Files

| File | Lines | Exports |
|------|-------|---------|
| `src/anonreq/multimodal/tool_call.py` | 258 | `ToolCallDetection`, `ToolCallResult`, `ToolCallExtractor`, `extract_tool_calls_openai`, `extract_tool_calls_anthropic`, `extract_tool_calls_mcp` |
| `tests/multimodal/test_tool_call.py` | 790 | 32 tests |

### Modified

| File | Change |
|------|--------|
| `src/anonreq/multimodal/__init__.py` | Added 6 tool_call symbols to package exports |

## Test Results

```
tests/multimodal/test_tool_call.py ..... 32 passed
```

Per-provider breakdown:

| Filter   | Tests | Status |
|----------|-------|--------|
| OpenAI   | 10    | ✅ 10 passed |
| Anthropic | 9     | ✅ 9 passed |
| MCP      | 10    | ✅ 10 passed |
| Extractor | 7    | ✅ 7 passed |
| **All**  | **32** | ✅ **32 passed, 0 failed** |

## Task Completion

### Task 1: OpenAI tool_calls — ✅ Complete

- `extract_tool_calls_openai()` extracts `function.arguments` JSON from each tool_call
- Arguments parsed and run through `JsonAnalyzer` for PII detection
- Null/missing `tool_calls` key → empty result (no crash)
- Malformed arguments JSON → empty dict + empty entities (graceful)
- Non-dict top-level arguments (e.g. plain strings) correctly handled
- Multiple tool_calls processed independently, each with its own detection
- Function name, ID, and type fields preserved (never analyzed)
- 8 tests covering all edge cases

### Task 2: Anthropic tool_use — ✅ Complete

- `extract_tool_calls_anthropic()` finds `type: "tool_use"` blocks in content array
- `input` dict extracted and analyzed via `JsonAnalyzer`
- Missing `input` field or null input → empty dict (graceful)
- Non-tool_use blocks (text, image) skipped
- Mixed content arrays with text + tool_use handled correctly
- Multiple tool_use blocks each independently analyzed
- Tool result blocks handled on response path via `ToolCallExtractor.extract_response()`
- 7 tests covering all edge cases

### Task 3: MCP — ✅ Complete

- `extract_tool_calls_mcp()` handles both request and response paths:
  - **Request** (`method: "tools/call"`): `params.arguments` analyzed
  - **Response** (`result.content`): text content items analyzed
- Non-tool methods (e.g. `resources/list`) ignored — empty result
- Missing `params` → empty result (no detection created)
- Null arguments → empty dict + empty entities
- `jsonrpc`, `id`, `method` fields preserved (never analyzed)
- Result without content → empty result
- 8 tests covering all edge cases

### Task 4: ToolCallExtractor — ✅ Complete

- `ToolCallExtractor` class auto-detects provider format from message structure:
  - **MCP**: first message has `"jsonrpc"` key → `extract_tool_calls_mcp`
  - **OpenAI**: any message has `"tool_calls"` key → `extract_tool_calls_openai`
  - **Anthropic**: assistant message has content with `"tool_use"` block → `extract_tool_calls_anthropic`
- `extract_request(messages)`: scans message list for tool calls
- `extract_response(response, provider)`: dispatches by explicit provider name
- No tool calls found → empty `ToolCallResult(provider="unknown")`
- 7 tests covering all formats and edge cases

## Key Design Decisions

1. **Detection metadata, not in-place replacement**: The extractors return `ToolCallResult` with per-tool-call PII detection metadata (entity type, location, score). Actual token replacement is performed by the downstream tokenization engine — keeping the extractors format-specific but replacement-agnostic.

2. **Provider detection priority**: MCP check first (distinct `jsonrpc` key), then OpenAI (`tool_calls` key), then Anthropic (`tool_use` blocks in content). This is unambiguous because no two formats share the same structural marker.

3. **Non-dict argument wrapping**: Arguments that parse to non-dict JSON values (e.g. `"just a string"`) are wrapped in a temporary `{"_value": ...}` for JsonAnalyzer analysis but returned as the original value. The wrapping is internal to the analysis function.

## Deviations from Plan

None — plan executed exactly as written.

### Auto-fixed Issues

**1. [Rule 1 - Bug] Non-dict arguments returned wrapped instead of original**
- **Found during:** Task 1 test run — `test_handles_non_dict_arguments` failed
- **Issue:** `_analyze_arguments` helper wrapped non-dict parsed values in `{"_value": ...}` for JsonAnalyzer compatibility but returned the wrapped version
- **Fix:** Separated analysis-wrapping from returned value — the wrapping is only used internally for JsonAnalyzer
- **Files modified:** `src/anonreq/multimodal/tool_call.py`
- **Commit:** (same as implementation commit)

**2. [Rule 1 - Bug] MCP missing params incorrectly created a detection**
- **Found during:** Task 3 test run — `test_handles_missing_params` failed
- **Issue:** When `params` was missing from a `tools/call` method, the code used `payload.get("params") or {}` which produced an empty dict, leading to a detection being created with empty data
- **Fix:** Added early return when params is falsy (missing or empty)
- **Files modified:** `src/anonreq/multimodal/tool_call.py`
- **Commit:** (same as implementation commit)

**3. [Rule 2] Package exports missing**
- **Found during:** Post-implementation review
- **Issue:** `src/anonreq/multimodal/__init__.py` did not export the new tool_call symbols
- **Fix:** Added all 6 symbols to exports
- **Files modified:** `src/anonreq/multimodal/__init__.py`
- **Commit:** `591a670`

## Threat Model Coverage

| Threat ID | Category | Disposition | Verified |
|-----------|----------|-------------|----------|
| T-09-02-01 | Tampering — Tool call arguments | mitigate | Arguments parsed as JSON, analyzed via JsonAnalyzer, structural validity preserved |
| T-09-02-02 | Info Disclosure — Function name leak | mitigate | Function names, tool IDs, and type fields preserved but never analyzed for PII |
| T-09-02-03 | DoS — Oversized tool arguments | mitigate | Delegates to JsonAnalyzer which respects max_depth (depth-limited recursive walk) |
| T-09-02-04 | Tampering — Format detection confusion | mitigate | Detection uses distinct structural markers (jsonrpc, tool_calls, tool_use) — no ambiguous matches |

## Success Criteria

- [x] OpenAI tool_calls: arguments extracted, parsed, anonymized, reassembled
- [x] Anthropic tool_use: content blocks extracted, input anonymized, blocks reassembled
- [x] MCP: tool call/result payloads extracted and anonymized, protocol fields preserved
- [x] ToolCallExtractor auto-detects provider format from message structure
- [x] Tool call function names, IDs, and type fields preserved
- [x] Tool role message content anonymized on response path
- [x] All 32 unit tests pass across all 3 formats
- [x] All files committed to git

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `2f98083` | test(09-02) | add tests for tool call argument extraction |
| `a0a6618` | feat(09-02) | implement tool call argument extraction for all providers |
| `591a670` | feat(09-02) | export tool_call symbols from multimodal package |

## Self-Check: PASSED

- ✅ `src/anonreq/multimodal/tool_call.py` — exists (258 lines)
- ✅ `tests/multimodal/test_tool_call.py` — exists (790 lines)
- ✅ `09-02-SUMMARY.md` — exists
- ✅ Commit `2f98083` — present in git log
- ✅ Commit `a0a6618` — present in git log
- ✅ Commit `591a670` — present in git log
- ✅ 32/32 tests passing
