---
phase: 04-multi-locale-detection-compliance-presets
plan: 03
subsystem: compliance
tags: [compliance, presets, startup-validation, audit]
requires:
  - phase: 04-multi-locale-detection-compliance-presets
    provides: LocaleBundle and RecognizerTier models
provides:
  - CompliancePreset model and six preset YAML files
  - PresetEngine with merge and startup validation
  - GET /v1/compliance/presets endpoint
affects: [startup, health, audit, detection]
tech-stack:
  added: []
  patterns: [non-weakening-overlays, startup-hard-fail]
key-files:
  created:
    - src/anonreq/compliance/
    - config/compliance/
    - src/anonreq/routes/compliance.py
    - tests/unit/compliance/
    - tests/integration/test_compliance_startup.py
  modified:
    - src/anonreq/config.py
    - src/anonreq/main.py
    - src/anonreq/routing/chat.py
key-decisions:
  - "Compliance presets are overlays that add or strengthen detection requirements."
  - "Startup validation treats operator-disabled mandated types as hard violations."
patterns-established:
  - "Active compliance presets are exposed in audit metadata as comma-separated IDs."
requirements-completed: [COMP-01, COMP-02, COMP-03, COMP-04, COMP-05, AUDT-01]
duration: 35min
completed: 2026-07-01
status: complete
---

# Phase 4 Plan 03: Compliance Preset Engine Summary

**Compliance presets with non-weakening merge semantics, startup validation, and preset listing API**

## Accomplishments

- Added six preset YAML files: GDPR, LGPD, PDPA, POPIA, Privacy Act AU, and PIPEDA.
- Implemented `PresetEngine`, `merge_presets`, and `validate_effective_config`.
- Added hard-fail startup validation support for operator-disabled mandatory entity types.
- Added protected `GET /v1/compliance/presets`.

## Deviations from Plan

The startup validation model explicitly represents disabled entity types. This matches the requirement more precisely than treating missing base types as violations, because presets are overlays that legitimately add mandatory types.

## Issues Encountered

None blocking.

## User Setup Required

Set `ANONREQ_ACTIVE_PRESETS=gdpr` or a comma-separated preset list to activate startup validation and audit metadata for hosted deployments.

## Next Phase Readiness

Phase 4 locale and compliance foundations are ready for Phase 6 checksum property expansion and Phase 5 observability.
