---
phase: 06-advanced-property-based-tests
plan: 03
subsystem: testing
tags: [property-tests, disconnect, checksum, hypothesis]
requires:
  - phase: 06-advanced-property-based-tests
    provides: shared test strategies, conftest fixtures
provides:
  - TEST-07E-H: disconnect property tests (tokenization, restoration, provider stream, timeout race)
  - TEST-05: locale checksum invalidation property tests (6 national ID formats)
affects: [phase-06-5, phase-07]
tech-stack:
  added: []
  patterns: [asgi-disconnect-simulation, checksum-invalidation-property-tests]
key-files:
  created:
    - tests/property/test_disconnect.py
    - tests/property/test_locale_checksum.py
  modified: []
requirements-completed: [TEST-05, TEST-07]
duration: ~10min
completed: 2026-07-02
status: complete
---

# Phase 6 Plan 03: Disconnect Handling + Locale Checksum Summary

## Disconnect Tests (TEST-07E-H)
- 28 property tests across 4 disconnect scenarios (tokenization, restoration, provider stream, timeout race)
- Verifies cleanup_session() called exactly once, 0 orphaned Valkey mappings
- Verifies partial restoration never emitted, upstream cancelled

## Locale Checksum Tests (TEST-05)
- Invalid checksum national IDs never flagged as valid detections
- Covers all 6 formats: Steuer-ID, BSN, NIR, CPF, CNPJ, Codice Fiscale
- Near-valid (single digit changed) IDs also not flagged
- Valid checksum regression guard

## Self-Check: PASSED
- 28/28 property tests pass
- All created files exist and are committed
