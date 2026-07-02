---
phase: 09
plan: 03
subsystem: multimodal-restore
tags:
  - restore
  - path-tracking
  - routing
  - local-router
  - content-type
requires:
  - 09-01 (Content-Type dispatcher, JSON/Multipart analyzers)
  - 09-02 (Tool call argument extraction)
provides:
  - PathTracker for path-aware token tracking
  - RestoreEngine for path-aware restoration
  - LocalRouter for content-type based routing decisions
affects:
  - src/anonreq/multimodal/dispatcher.py (LocalRouter integration)
  - src/anonreq/multimodal/__init__.py (new exports)
tech-stack:
  added:
    - Python 3.12, dataclasses, re (no new external deps)
  patterns:
    - TDD: test first, implementation second, per-task commits
    - Integration: detect → track → restore pipeline
key-files:
  created:
    - src/anonreq/restore/path_tracker.py
    - src/anonreq/restore/engine.py
    - src/anonreq/restore/__init__.py
    - src/anonreq/multimodal/router.py
    - tests/restore/__init__.py
    - tests/restore/test_path_tracker.py
    - tests/restore/test_restore_extensions.py
    - tests/restore/test_integration.py
    - tests/multimodal/test_router.py
  modified:
    - src/anonreq/multimodal/dispatcher.py
    - src/anonreq/multimodal/__init__.py
decisions:
  - PathTracker stores as dict[str, list[str]] with deduplication
  - RestoreEngine uses regex-based token matching with case-insensitive and bracket-optional support
  - LocalRouter uses prefix matching (text/*, image/*, etc.) with exact-match custom overrides
metrics:
  duration: ~25 minutes
  completed_date: "2026-07-02"
status: complete
---

# Phase 9 Plan 3: Path-Aware Token Tracking and Local Routing

## One-Liner

Path-aware token tracking (PathTracker), enhanced restoration (RestoreEngine), content-type based local routing (LocalRouter), and integration with the existing ContentTypeDispatcher — all built TDD with 96 new tests.

## Objective

Add path-aware token tracking so each `[TYPE_N]` token remembers its JSON path,
extend `RestoreEngine` with path-aware restoration, and create `LocalRouter` for
intelligent content-type based routing decisions. Wire everything into the existing
multimodal pipeline.

## Tasks Completed

### Task 1: PathTracker — 15 tests

**Commits:**
- `6f8dd4a` — test(09-03): add PathTracker tests
- `2b2ce1f` — feat(09-03): implement PathTracker

PathTracker records which JSON path each token came from. Stores as `dict[str, list[str]]`
mapping entity_key → list of paths with duplicate path detection. Supports `track`,
`get_path`, `get_all`, `clear` methods. Dot-notation paths like
`messages.0.tool_calls.0.function.arguments`.

### Task 2: RestoreEngine — 30 tests

**Commits:**
- `9c398a2` — test(09-03): add RestoreEngine tests
- `574d1b0` — feat(09-03): implement RestoreEngine

RestoreEngine extends the existing token restoration with path awareness.
- `restore_with_paths()`: text-level token replacement with case-insensitive and bracket-optional matching
- `restore_response_with_paths()`: recursive dict restoration with path awareness
- Partial token safety (incomplete tokens like `[EM` are left unchanged)
- Backslash/escape safety in replacement values
- Compatible with TailBuffer for streaming (supported via `restore_with_paths`)

### Task 3: LocalRouter — 37 tests

**Commits:**
- `bca88aa` — test(09-03): add LocalRouter tests
- `ee3a7a9` — feat(09-03): implement LocalRouter

LocalRouter provides content-type based routing decisions:
- `RouteDecisionType` enum: `FORWARD`, `ROUTE_LOCAL`, `BLOCK`
- `RouteDecision` dataclass with `decision`, `reason`, `content_type`
- Default rules: text/*, application/json, multipart/* → FORWARD;
  image/*, audio/*, video/*, application/octet-stream → ROUTE_LOCAL
- Custom exact-match overrides via config dict
- Charset/boundary parameter stripping
- Fallback to `ROUTE_LOCAL` for unknown types

### Task 4: Integration — 14 tests

**Commits:**
- `5607432` — test(09-03): add integration tests for PathTracker + LocalRouter
- `1f28d5f` — feat(09-03): integrate LocalRouter into ContentTypeDispatcher

Integration wiring:
- ContentTypeDispatcher now accepts optional `LocalRouter` for unknown content types
- Unknown type routing uses LocalRouter instead of hardcoded `ROUTE_LOCAL`
- Route decision metadata (`route_decision`, `route_reason`) included in analyzer result
- Full pipeline tests: analyze → track paths → restore with path awareness
- PathTracker clears between sessions (privacy invariant)
- LocalRouter and RestoreEngine operate independently

## Test Results

```
tests/multimodal/ + tests/restore/ → 180 passed in 0.54s
```

- **tests/restore/test_path_tracker.py:** 15 tests, all passed
- **tests/restore/test_restore_extensions.py:** 30 tests, all passed
- **tests/multimodal/test_router.py:** 37 tests, all passed
- **tests/restore/test_integration.py:** 14 tests, all passed

## Deviations from Plan

None — plan executed exactly as written. All tasks completed per TDD flow.

### Deviations from Plan

None — plan executed exactly as written.

### Analysis Paralysis

None.

### Auth Gates

None.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

All created files verified:
- [x] `src/anonreq/restore/__init__.py`
- [x] `src/anonreq/restore/path_tracker.py`
- [x] `src/anonreq/restore/engine.py`
- [x] `src/anonreq/multimodal/router.py`
- [x] `tests/restore/__init__.py`
- [x] `tests/restore/test_path_tracker.py`
- [x] `tests/restore/test_restore_extensions.py`
- [x] `tests/restore/test_integration.py`
- [x] `tests/multimodal/test_router.py`

All 8 commits verified (via `git rev-parse --short`):
- [x] `6f8dd4a` test(09-03): add PathTracker tests
- [x] `2b2ce1f` feat(09-03): implement PathTracker
- [x] `9c398a2` test(09-03): add RestoreEngine tests
- [x] `574d1b0` feat(09-03): implement RestoreEngine
- [x] `bca88aa` test(09-03): add LocalRouter tests
- [x] `ee3a7a9` feat(09-03): implement LocalRouter
- [x] `5607432` test(09-03): add integration tests
- [x] `1f28d5f` feat(09-03): integrate LocalRouter into ContentTypeDispatcher

All tests pass:
- total/multimodal/ + tests/restore/: **96 tests, 0 failures, 0 errors**
