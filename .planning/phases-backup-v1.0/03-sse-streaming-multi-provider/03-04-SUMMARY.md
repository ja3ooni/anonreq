---
phase: 03-sse-streaming-multi-provider
plan: 04
subsystem: testing
tags: [hypothesis, streaming, disconnect, load]
requires:
  - phase: 03-01
    provides: TailBuffer, StreamingRestorationStage, SessionCleanup
  - phase: 03-02
    provides: Provider adapter tests
  - phase: 03-03
    provides: Alias routing
provides:
  - Streaming property tests for arbitrary chunks and split tokens
  - Disconnect property tests for cleanup invariants
  - 100-concurrent-disconnect load test
affects: [streaming, testing, disconnect-handling]
tech-stack:
  added: []
  patterns:
    - Hypothesis strategies for token mappings and chunked streams
key-files:
  created:
    - tests/property/test_streaming.py
    - tests/property/test_disconnect.py
    - tests/load/test_disconnect.py
  modified:
    - tests/conftest.py
    - pyproject.toml
key-decisions:
  - "Reasoning leak property assumes generated reasoning is distinct from visible text to avoid false positives."
  - "The load marker is registered in pyproject.toml."
patterns-established:
  - "Property tests collect TailBuffer output plus final flush and compare restored final text."
requirements-completed: [TEST-07]
duration: 1h
completed: 2026-07-01
status: complete
---

# Phase 03 Plan 04: Streaming Property Tests + Disconnect Load Test Summary

Streaming and disconnect invariants are now covered by Hypothesis plus a 100-session concurrent cleanup test.

## Performance

- **Duration:** 1h
- **Started:** 2026-07-01
- **Completed:** 2026-07-01
- **Tasks:** 3/3
- **Files modified:** 6

## Accomplishments

- Added TEST-07A through TEST-07E property coverage for chunking, token splits, buffer bounds, timing invariance, and reasoning blocking.
- Added STREAM-07A through STREAM-07D disconnect cleanup property tests.
- Added load test proving 100 concurrent disconnect cleanups leave zero orphaned mappings.

## Task Commits

The scoped commit for this plan could not complete because local git invoked `git fetch` against GitHub and network access is restricted. Files are present in the workspace.

## Files Created/Modified

- `tests/property/test_streaming.py` - Streaming property invariants.
- `tests/property/test_disconnect.py` - Disconnect cleanup invariants.
- `tests/load/test_disconnect.py` - 100 concurrent disconnect cleanup test.
- `tests/conftest.py` - Shared Hypothesis strategies.
- `pyproject.toml` - `load` marker registration.

## Decisions Made

The installed Hypothesis/pytest integration does not support `--hypothesis-max-examples`; max examples are set in test decorators for this environment.

## Deviations from Plan

The command-line `--hypothesis-max-examples=1000` phase-gate form is unavailable in this environment. The property tests run with decorator settings and pass.

**Total deviations:** 1 tooling deviation.
**Impact on plan:** Coverage exists and passes; the exact CLI override documented in the plan is not supported by the installed plugin.

## Issues Encountered

Initial reasoning property produced a false positive when Hypothesis generated identical visible text and reasoning payloads. Fixed by requiring distinct reasoning content for the leak test.

## Verification

- `PYTHONPATH=src pytest tests/property/test_streaming.py tests/property/test_disconnect.py -q` → 9 passed.
- `PYTHONPATH=src pytest tests/load/test_disconnect.py -q -m load` → 1 passed.
- Focused suite: `PYTHONPATH=src pytest tests/unit/streaming tests/unit/routing tests/unit/providers/test_adapters.py tests/property tests/load/test_disconnect.py -q -m 'not slow'` → 70 passed.

## Self-Check: PASSED
