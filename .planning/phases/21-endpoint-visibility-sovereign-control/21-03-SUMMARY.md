---
phase: 21-endpoint-visibility-sovereign-control
plan: 03
subsystem: voice
tags: [voice, audio-sanitization, sliding-window-detection, timeline-mapping, prometheus]
requires:
  - phase: 21-02
    provides: voice connectors, AudioChunk, VoiceConfig, STTEngine, TranscriptBuffer
provides:
  - Sliding-window transcript detector with overlap and cross-window carryover
  - Transcript entity to audio millisecond range mapping
  - PCM audio muting and beep masking for sensitive speech ranges
  - Text transcript tokenization with [TYPE_N] placeholders
  - VoicePipeline orchestrating connector, STT, detection, sanitization, metrics, and audit events
affects: [phase-21, voice, metrics]
tech-stack:
  added: []
  patterns: [voice-pipeline-orchestrator, conservative-audio-range-mapping, metadata-only-audit]
key-files:
  created:
    - src/anonreq/voice/detector.py
    - src/anonreq/voice/timeline.py
    - src/anonreq/voice/pipeline.py
    - tests/test_voice_detector.py
    - tests/test_voice_sanitizer.py
    - tests/test_voice_pipeline.py
  modified:
    - src/anonreq/voice/sanitizer.py
key-decisions:
  - "Timeline mapping uses a uniform character-distribution approximation plus a 50ms safety margin to reduce under-redaction risk."
  - "Audio sanitization operates on in-memory PCM bytes for the new pipeline while retaining the prior numpy chunk sanitizer compatibility path."
  - "Voice audit events intentionally exclude raw text/audio/content fields."
patterns-established:
  - "VoicePipeline yields either sanitized audio bytes or tokenized text from the same connector/STT/detector flow."
  - "Prometheus voice metrics are registered defensively to avoid duplicate collector errors in tests."
requirements-completed:
  - APPL-01/Req58
duration: 20 min
completed: 2026-07-05
status: complete
---

# Phase 21 Plan 03: Audio Stream Sanitization Summary

**Sliding-window voice PII detection with millisecond audio-frame mapping, mute/beep masking, text tokenization, and latency-tracked VoicePipeline orchestration**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-05T15:07:00Z
- **Completed:** 2026-07-05T15:27:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added `TimelineMapper` for transcript character offsets to conservative millisecond audio ranges.
- Added `SlidingWindowDetector` with configurable 500ms windows, 125ms overlap, context carryover, duplicate suppression, and pending entity tracking.
- Extended `AudioSanitizer` with byte-level PCM muting, configurable beep masking, range merging, and retained numpy chunk compatibility.
- Added `TextSanitizer` for `[TYPE_N]` placeholder replacement in transcript text.
- Added `VoicePipeline` to orchestrate connector chunks through STT, detection, audio/text sanitization, Prometheus latency/active-stream metrics, and metadata-only audit events.

## Task Commits

No task commits were created. The repository had substantial pre-existing dirty and untracked changes before this plan, and the subagent produced code without reaching its summary/commit close-out. Files and summary are left in place for later scoped commit/reconciliation.

## Files Created/Modified

- `src/anonreq/voice/timeline.py` - Character-offset to audio-frame timestamp mapping.
- `src/anonreq/voice/detector.py` - Sliding-window transcript detector and entity timeline localization.
- `src/anonreq/voice/sanitizer.py` - PCM mute/beep sanitization and text tokenization.
- `src/anonreq/voice/pipeline.py` - End-to-end voice stream processing pipeline.
- `tests/test_voice_detector.py` - Windowing, overlap, and timeline mapping tests.
- `tests/test_voice_sanitizer.py` - Mute, beep, overlapping ranges, and text tokenization tests.
- `tests/test_voice_pipeline.py` - Full pipeline, latency, audit, and output mode tests.

## Decisions Made

- Added a 50ms safety margin to entity audio ranges. The plan explicitly prioritizes preventing residual speech leakage, so conservative redaction is preferable to precise but fragile mapping.
- Kept the older `sanitize_chunk(np.ndarray, DetectionTimestamp)` API in `AudioSanitizer` while adding the planned byte-oriented `sanitize()` API, avoiding a compatibility break for any existing sketch code.
- Metrics are registered through a small helper that reuses existing collectors from the Prometheus registry, preventing duplicate registration errors in repeated test imports.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Subagent did not reach summary close-out**
- **Found during:** Plan close-out
- **Issue:** The Wave 3 subagent wrote code and tests but did not return or create `21-03-SUMMARY.md`.
- **Fix:** Closed the stalled subagent, verified the implementation locally, inspected the new files, and wrote this summary.
- **Files modified:** `.planning/phases/21-endpoint-visibility-sovereign-control/21-03-SUMMARY.md`
- **Verification:** Focused voice tests passed locally.
- **Committed in:** Not committed due dirty-tree constraint.

**2. [Rule 2 - Missing Critical] Preserved existing sanitizer compatibility**
- **Found during:** Task 2 implementation review
- **Issue:** The repository already had an early numpy-based `AudioSanitizer.sanitize_chunk()` sketch. Replacing it outright could break existing callers.
- **Fix:** Added planned byte-level mute/beep methods and retained `sanitize_chunk()` compatibility.
- **Files modified:** `src/anonreq/voice/sanitizer.py`
- **Verification:** New sanitizer and pipeline tests pass.
- **Committed in:** Not committed due dirty-tree constraint.

---

**Total deviations:** 2 auto-fixed (1 execution close-out issue, 1 compatibility preservation).  
**Impact on plan:** Functional scope remains aligned with Plan 21-03.

## Issues Encountered

- No functional test failures remained after local verification.
- Commits were deferred because the working tree already contained unrelated and cross-wave changes.

## Verification

- `pytest tests/test_voice_detector.py tests/test_voice_sanitizer.py tests/test_voice_pipeline.py tests/test_voice_connectors.py tests/test_voice_stt.py tests/test_voice_transcript.py -q` → 38 passed.
- Artifact line counts meet plan minimums: `detector.py` 200 lines, `timeline.py` 62 lines, `sanitizer.py` 211 lines, `pipeline.py` 171 lines.
- Audio mute path zeros PCM bytes in entity ranges; beep path writes non-zero sine-wave PCM samples.
- VoicePipeline records latency and emits `voice_latency_exceeded` when over the 150ms budget.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 21-04. Voice ingestion and sanitization are in place; remaining phase work can add MCP/tool governance and firewall validation.

---
*Phase: 21-endpoint-visibility-sovereign-control*
*Completed: 2026-07-05*
