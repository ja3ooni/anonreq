---
phase: 04-multi-locale-detection-compliance-presets
plan: 02
subsystem: locale
tags: [locale-header, recognizer-merge, pipeline]
requires:
  - phase: 04-multi-locale-detection-compliance-presets
    provides: LocaleRegistry and locale bundles
provides:
  - LocaleNegotiator for X-AnonReq-Locale
  - RecognizerMerger for universal plus locale-specific recognizers
  - LocaleNegotiationStage in the pipeline
affects: [routing, detection, audit]
tech-stack:
  added: []
  patterns: [pre-detection-negotiation, deterministic-merge]
key-files:
  created:
    - src/anonreq/locale/negotiator.py
    - src/anonreq/locale/merger.py
    - src/anonreq/pipeline/stages.py
    - tests/unit/locale/test_negotiator.py
    - tests/unit/locale/test_merger.py
    - tests/integration/test_locale_detection.py
  modified:
    - src/anonreq/routing/chat.py
    - src/anonreq/main.py
key-decisions:
  - "Locale header parsing caps at 10 entries and drops unknown entries in multi-locale requests."
  - "Recognizer merging sorts locale bundles for deterministic order-independent output."
patterns-established:
  - "Locale negotiation stores effective locale metadata on ProcessingContext.audit_metadata."
requirements-completed: [LOCL-02, LOCL-03, LOCL-04, LOCL-05, AUDT-01]
duration: 35min
completed: 2026-07-01
status: complete
---

# Phase 4 Plan 02: Locale Negotiation Summary

**Deterministic `X-AnonReq-Locale` negotiation and universal-plus-locale recognizer merging before detection**

## Accomplishments

- Added header parsing for single and comma-separated locale codes.
- Added fallback behavior for no locale and mixed valid/unknown multi-locale headers.
- Added deterministic recognizer merging with highest confidence threshold winning.
- Wired locale negotiation into non-streaming and streaming pre-provider pipeline paths.

## Deviations from Plan

None - plan executed within intended architecture.

## Issues Encountered

None blocking.

## User Setup Required

None.

## Next Phase Readiness

Ready for compliance preset overlays and startup validation.
