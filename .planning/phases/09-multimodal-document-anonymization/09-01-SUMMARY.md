---
phase: 09-multimodal-document-anonymization
plan: 01
subsystem: content-routing
tags: multimodal, json-analyzer, multipart, content-type-dispatcher, payload-limits

# Dependency graph
requires:
  - phase: 02-core-pipeline-classification-non-streaming
    provides: Detection and tokenization pipeline architecture
  - phase: 08-Enterprise-Policy-Engine
    provides: PDP #1/#2 policy enforcement points
provides:
  - Content-Type Dispatcher (routes text/plain, application/json, multipart/form-data)
  - JSON Analyzer (recursive tree walk with sensitive key-pattern detection)
  - Multipart Analyzer (per-part content-type routing)
  - Payload size/depth limit validation
  - ContentTypeMiddleware (FastAPI ASGI middleware, HTTP 415 for unsupported types)
affects: 09-02, 09-03, 09-04, 10-ai-security-firewall

# Tech tracking
tech-stack:
  added:
    - python-multipart (multipart form-data parsing)
  patterns:
    - Content-Type dispatching with charset stripping and fallback
    - Recursive JSON tree walking with depth-guarded recursion
    - Sensitive key-pattern detection with confidence boosting
    - Payload limit validation as a pre-processing gate

key-files:
  created:
    - src/anonreq/multimodal/models.py
    - src/anonreq/multimodal/dispatcher.py
    - src/anonreq/multimodal/json_analyzer.py
    - src/anonreq/multimodal/multipart_analyzer.py
    - src/anonreq/multimodal/limits.py
    - src/anonreq/multimodal/__init__.py
    - src/anonreq/middleware/content_type.py
    - config/multimodal.yaml
    - tests/multimodal/__init__.py
    - tests/multimodal/test_dispatcher.py
    - tests/multimodal/test_json_analyzer.py
    - tests/multimodal/test_multipart_analyzer.py
    - tests/multimodal/test_limits.py
  modified: []

key-decisions:
  - "Unknown Content-Type returns ROUTE_LOCAL via LocalRouter, never FORWARD"
  - "Missing/empty Content-Type header defaults to text/plain"
  - "Sensitive key-pattern detection boosts confidence by 0.15 (cap at 1.0) instead of creating new entity types"
  - "JSON Analyzer is read-only — input structure is never mutated"
  - "Depth limit only enforced for JSON content type (not text or multipart)"
  - "Binary parts in multipart are skipped with structured audit log entry"

patterns-established:
  - "Content-Type dispatching pattern: header parsing -> charset stripping -> allowlist match -> analyzer delegation"
  - "Payload limit gates before any processing (fail-closed on exceeded limits)"
  - "UnifiedDetectionResult as the standard return type for all content analyzers"

requirements-completed:
  - MULTI-03
  - MULTI-04
  - MULTI-05

# Metrics
duration: 0min
completed: 2026-07-03
status: complete
---

# Phase 9 Plan 01: Content-Type Dispatcher + JSON/Multipart Analyzers Summary

**Content-Type Dispatcher middleware routing text/plain, application/json, and multipart/form-data to correct analyzers with JSON recursive tree walk, multipart per-part routing, and payload limit validation**

## Performance

- **Duration:** <1 min
- **Started:** 2026-07-03T07:21:43Z
- **Completed:** 2026-07-03T07:22:18Z
- **Tasks:** 4
- **Files modified:** 13

## Accomplishments

- ContentTypeDispatcher routes requests to correct analyzer based on Content-Type header with charset stripping
- Unknown Content-Type returns ROUTE_LOCAL decision (never FORWARD) via LocalRouter
- ContentTypeMiddleware returns HTTP 415 for unsupported Content-Type types
- JSON Analyzer recursively walks JSON trees to configurable max_depth (50) with 14 sensitive key patterns
- Sensitive key detection boosts confidence scores by 0.15 (cap at 1.0)
- Multipart Analyzer parses form-data parts and routes each by content type (JSON -> JsonAnalyzer, text -> text engine, binary -> skip with audit log)
- Payload limit validation enforces 5MB JSON, 50MB multipart, depth 50, 100 max parts
- All 52 unit tests passing with structured assertions

## Task Commits

Each task was committed atomically:

1. **Task 1: Content-Type Dispatcher + Models** — `c4e13a5` (feat)
   - ContentType enum, UnifiedDetectionResult/AnalyzerResult models
   - ContentTypeDispatcher, ContentTypeMiddleware
   - Config (multimodal.yaml), 20 dispatcher tests
2. **Task 2: JSON Analyzer** — `950841a` (feat)
   - JsonAnalyzer with recursive tree walk, 14 sensitive key patterns
   - 11 JSON analyzer tests
3. **Task 3: Multipart Analyzer** — `b8fb22b` (feat)
   - MultipartAnalyzer with per-part routing using python-multipart
   - 8 multipart analyzer tests
4. **Task 4: Payload Limits** — `648a3ef` (feat)
   - PayloadLimits model, validate_payload_limits function
   - 13 limit validation tests

## Files Created/Modified

- `src/anonreq/multimodal/__init__.py` — Package exports for all multimodal types
- `src/anonreq/multimodal/models.py` — ContentType enum, UnifiedDetectionResult, AnalyzerResult
- `src/anonreq/multimodal/dispatcher.py` — ContentTypeDispatcher with charset parsing and routing
- `src/anonreq/multimodal/json_analyzer.py` — JsonAnalyzer with recursive tree walk and key sensitivity
- `src/anonreq/multimodal/multipart_analyzer.py` — MultipartAnalyzer with per-part routing
- `src/anonreq/multimodal/limits.py` — PayloadLimits, LimitCheckResult, validate_payload_limits
- `src/anonreq/middleware/content_type.py` — ContentTypeMiddleware (ASGI, HTTP 415 for unknown types)
- `config/multimodal.yaml` — Per-type size/depth/part limits configuration
- `tests/multimodal/__init__.py` — Test package init
- `tests/multimodal/test_dispatcher.py` — 20 tests for routing, models, middleware
- `tests/multimodal/test_json_analyzer.py` — 11 tests for JSON walking, key boosting, depth limits
- `tests/multimodal/test_multipart_analyzer.py` — 8 tests for multipart parsing and routing
- `tests/multimodal/test_limits.py` — 13 tests for size/depth/parts validation

## Decisions Made

- **Unknown Content-Type**: Returns ROUTE_LOCAL decision (never FORWARD), consistent with fail-secure principle
- **Missing Content-Type header**: Defaults to text/plain (safe default for LLM gateway)
- **Sensitive key boosting**: Confidence boost of +0.15 applied to existing detection results — no new entity types created from key names alone (prevents false positives)
- **Read-only scanning**: JSON Analyzer never modifies the input structure
- **Depth limit scope**: Only enforced for JSON content type; text and multipart have natural size limits only
- **Binary parts**: Skipped with structured audit log entry (not silently dropped)

## Deviations from Plan

None - plan executed exactly as written. All 4 tasks completed with code and tests committed atomically.

### Verification Results

| Check | Status |
|-------|--------|
| `pytest tests/multimodal/test_dispatcher.py -x --tb=short -v` | PASSED (20 tests) |
| `pytest tests/multimodal/test_json_analyzer.py -x --tb=short -v` | PASSED (11 tests) |
| `pytest tests/multimodal/test_multipart_analyzer.py -x --tb=short -v` | PASSED (8 tests) |
| `pytest tests/multimodal/test_limits.py -x --tb=short -v` | PASSED (13 tests) |
| Unknown Content-Type -> ROUTE_LOCAL, never FORWARD | PASSED |
| Content-Type charset stripping | PASSED |
| JSON analyzer walks to max_depth and stops | PASSED |
| Multipart analyzer routes per-part correctly | PASSED |
| Oversized payloads trigger controlled failure | PASSED |

## Issues Encountered

- `python-multipart` package was missing from project dependencies (not listed in pyproject.toml `dependencies` or `[dev]`). Installed in `.venv` to unblock test execution. Consider adding to project dependencies.

## Threat Model Compliance

| Threat ID | Description | Verdict |
|-----------|-------------|---------|
| T-09-01-01 | Content-Type bypass | Mitigated — unknown types -> ROUTE_LOCAL via explicit allowlist |
| T-09-01-02 | Deep JSON DoS | Mitigated — max_depth=50 enforced, exceeded -> ROUTE_LOCAL |
| T-09-01-03 | Oversized payload | Mitigated — size limits enforced before processing |
| T-09-01-04 | Multipart part explosion | Mitigated — max_parts=100 enforced |
| T-09-01-05 | Sensitive key info disclosure | Mitigated — confidence boost only, no new entity creation |

## Next Phase Readiness

- Ready for Plan 09-02 (tool call argument extraction)
- Content-Type Dispatcher integrates with pipeline after PDP #1 and before PDP #2
- Analyzers produce UnifiedDetectionResult consumable by Phase 2 Anonymization Engine

## Self-Check: PASSED

- ✅ All 13 source/test files exist on disk
- ✅ All 4 commit hashes found in git history
- ✅ 52/52 tests passing
- ✅ Threat model compliance verified (T-09-01-01 through T-09-01-05)

---

*Phase: 09-multimodal-document-anonymization*
*Completed: 2026-07-03*
