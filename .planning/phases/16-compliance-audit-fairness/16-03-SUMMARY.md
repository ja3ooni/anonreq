---
phase: 16-compliance-audit-fairness
plan: 03
subsystem: compliance, dsar, breach-notification
tags: [dsar, erasure, restriction, breach-notification, gdpr, dora, regulator-queue, template-engine]
requires: [16-02]
provides: [dsar-workflow, subject-erasure, processing-restriction, breach-automation]
affects: [governance-router]
tech-stack:
  added: []
  patterns: [async-mock-dict-store, string-template-variable-substitution, db+valkey-dual-service]
key-files:
  created:
    - src/anonreq/models/dsar.py: DsarRequest, DsarRequestType, DsarResult, SubjectStatus models
    - src/anonreq/dsar/workflow.py: DsarWorkflow with submit/verify/fulfill/list
    - src/anonreq/dsar/erasure.py: DataErasureService with scan/delete Valkey mappings
    - src/anonreq/dsar/restriction.py: DataRestrictionService with restrict/is_restricted/remove_restriction
    - src/anonreq/models/breach.py: BreachTemplate, BreachNotification, RegulatorQueueItem models
    - src/anonreq/breach/templates.py: BreachTemplateManager with get_template, render_template, custom override
    - src/anonreq/breach/notifications.py: BreachNotifier with send, queue, retry
    - tests/test_dsar.py: 24 tests for DSAR workflow, erasure, restriction
    - tests/test_breach_notifications.py: 18 tests for breach templates, notifications, models
  modified:
    - src/anonreq/governance/router.py: 10 new DSAR + Breach endpoints added (32 total routes)
decisions:
  - Breach notification templates use `{{variable_name}}` syntax converted to string.Template `$variable_name` for rendering
  - DSAR endpoints follow /v1/governance/dsar/* path convention consistent with existing /v1/governance/legal-holds and /v1/governance/suppliers
  - Breach endpoints follow /v1/governance/breach/* path convention
  - Erasure service uses Valkey SCAN + DELETE pattern (same as Phase 15 AML model erasure)
  - Restriction service stores in `subject_restriction` table with reason and restricted_by metadata
metrics:
  duration: 12min
  completed_date: "2026-07-05"
  tasks: 3
  files_created: 9
  tests_added: 42
status: complete
---

# Phase 16 Plan 03: DSAR Workflows & Breach Notifications Summary

**One-liner:** DSAR request workflow (submit/verify/fulfill), subject data erasure via Valkey, processing restriction management, and breach notification automation with multi-framework templates (GDPR, UK DPA, DORA).

## Architecture

### DSAR Workflow (`/v1/governance/dsar/*`)

```
POST   /v1/governance/dsar/requests               — submit
GET    /v1/governance/dsar/requests                — list (filtered)
GET    /v1/governance/dsar/requests/{id}           — get status
POST   /v1/governance/dsar/requests/{id}/fulfill   — fulfill
POST   /v1/governance/dsar/erasure/{subject_id}    — erase data
GET    /v1/governance/dsar/erasure/{subject_id}    — check erasure
POST   /v1/governance/dsar/restriction/{subject_id} — restrict processing
GET    /v1/governance/dsar/restriction/{subject_id} — check restriction
DELETE /v1/governance/dsar/restriction/{subject_id} — remove restriction
GET    /v1/governance/dsar/restrictions            — list restricted subjects
```

The DSAR system comprises three cooperating services:

1. **DsarWorkflow** — SQLAlchemy-backed request lifecycle (ACCESS, ERASURE, RECTIFICATION, RESTRICTION, PORTABILITY types). Supports submit with notes, identity verification, fulfillment with full metadata capture, and filtered listing.

2. **DataErasureService** — Valkey-backed erasure using SCAN to find all `anonreq:{subject_id}:*` keys and DELETE them in batch. Stores erasure records in `subject_erasure` table for auditability. Idempotent — already-erased subjects return `True`.

3. **DataRestrictionService** — SQLAlchemy-backed restriction records in `subject_restriction` table. Prevents processing of restricted subjects. Supports remove, check, and list operations.

### Breach Notifications (`/v1/governance/breach/*`)

```
POST   /v1/governance/breach/notify     — send notifications
GET    /v1/governance/breach/queue      — get notification queue
POST   /v1/governance/breach/retry      — retry failed
GET    /v1/governance/breach/templates  — list templates
POST   /v1/governance/breach/templates  — set custom template
```

The breach notification system comprises two services:

1. **BreachTemplateManager** — In-memory template registry with default templates per framework/region:
   - `gdpr/eu` — GDPR Breach Notification (72h regulator deadline)
   - `gdpr/uk` — UK DPA Breach Notification  
   - `dora/eu` — DORA ICT Incident Notification

   Templates use string.Template (`$variable_name`) syntax. `render_template()` validates required variables are present and returns `(subject, body)` tuples.

2. **BreachNotifier** — Orchestrates notification sending. Creates BreachNotification records, queues RegulatorQueueItem for regulatory bodies, and supports retry of failed notifications. Returns notification counts per send operation.

## Implementation Details

- **Mock patterns**: Test DsarWorkflow uses in-memory dict store with autouse fixtures. Mock DB sessions order conditions for UPDATE/DELETE before generic WHERE clauses.
- **Template rendering**: `{{variable_name}}` in defaults converted to `$variable_name` for string.Template compatibility. Missing required variables raise `KeyError` with descriptive message.
- **Dual-service pattern**: DSAR erasure combines Valkey (data deletion) + SQLAlchemy (audit records). Restriction uses SQLAlchemy only.
- **Router integration**: All 10 new endpoints follow the governance router prefix (`/v1/governance/`) and emit audit events via `_emit_sync`.

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

```
42 passed (24 DSAR + 18 breach) in 0.75s
```

Combined with existing 16-02 test suites:
```
75 passed (17 legal hold + 16 supplier + 24 DSAR + 18 breach) in 1.83s
```

## Known Stubs

None.

## Threat Flags

No new security-relevant surface beyond the declared DSAR and breach notification endpoints. All endpoints are authenticated through the existing governance router middleware (metadata-only audit, no PII in logs).

## Self-Check: PASSED

- [x] `src/anonreq/models/dsar.py` — exists
- [x] `src/anonreq/dsar/workflow.py` — exists
- [x] `src/anonreq/dsar/erasure.py` — exists
- [x] `src/anonreq/dsar/restriction.py` — exists
- [x] `src/anonreq/models/breach.py` — exists
- [x] `src/anonreq/breach/templates.py` — exists
- [x] `src/anonreq/breach/notifications.py` — exists
- [x] `tests/test_dsar.py` — exists
- [x] `tests/test_breach_notifications.py` — exists
- [x] Commit `9cb212c` — exists: `feat(16-03): DSAR workflow, erasure, restriction, and breach notifications`
- [x] All 42 tests pass
