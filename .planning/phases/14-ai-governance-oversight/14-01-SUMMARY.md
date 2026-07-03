---
phase: 14-ai-governance-oversight
plan: 01
subsystem: governance
tags: governance, risk, pydantic, sqlalchemy, alembic, pii, compliance

requires:
  - phase: 11-operational-observability-compliance
    provides: PostgreSQL async engine, Base ORM model, audit trail infrastructure

provides:
  - GovernanceRecord model with named officers (governance/risk/compliance/security) per D-001
  - ReviewCycle scheduling with 90-day default interval and overdue detection per D-002/D-003
  - 6-dimension risk assessment framework (privacy, security, bias, explainability, fairness, safety) per D-006/D-007
  - Severity + likelihood scoring methodology (normalized 0-1) per D-008
  - Config-change-triggers-reassessment flag on entity type config changes per D-009
  - Alembic migration 002 for governance_record, review_cycle, and risk_assessment tables

affects:
  - Phase 14-02 (oversight approval queue and kill-switch)
  - Phase 14-03 (object lifecycle management)
  - Phase 14-04 (transparency reports)
  - Phase 18 (agent/tool call governance — consumes governance records)

tech-stack:
  added: []
  patterns:
    - SQLAlchemy async ORM with Pydantic serialization layer
    - JSON-column storage for officers and risk dimensions (PostgreSQL)
    - Alembic migrations for governance schema
    - In-memory SQLite (aiosqlite) for unit testing governance CRUD

key-files:
  created: []
  modified:
    - src/anonreq/models/governance.py
    - src/anonreq/governance/__init__.py
    - src/anonreq/governance/records.py
    - src/anonreq/governance/reviews.py
    - src/anonreq/governance/risk.py
    - src/anonreq/governance/router.py
    - src/anonreq/main.py
    - alembic/versions/002_create_governance_tables.py

key-decisions:
  - "Per-tenant governance records with 4 named officer roles (D-001)"
  - "90-day review cycle default, configurable per tenant (D-002)"
  - "6 fixed risk dimensions + tenant extensions (hybrid model per D-006)"
  - "Severity * likelihood / 25 scoring normalized to 0-1 range (D-008)"
  - "Config changes affecting entity types trigger reassessment flag (D-009)"
  - "JSON-column storage for officers and risk dimensions in PostgreSQL"
  - "Alembic migration 002 for governance tables with foreign keys to Phase 11"

requirements-completed:
  - REQ-27
  - REQ-28
  - REQ-35
  - REQ-29

duration: 0 min (pre-existing)
completed: 2026-07-03
status: complete
---

# Phase 14 Plan 01: Governance Record Model, CRUD, Review Cycles & Risk Assessment

**Governance foundation — record model with 4 officer roles, 90-day review cycle with overdue detection, 6-dimension risk assessment with config-change reassessment triggering**

## Performance

- **Duration:** 0 min (code and tests pre-existing)
- **Started:** 2026-07-03T07:18:55Z
- **Completed:** 2026-07-03T07:20:00Z
- **Tasks:** 2 (already implemented, verified only)
- **Files modified:** 9

## Accomplishments

- **Task 1 — Verified existing governance record model + CRUD + endpoints:** Tests confirm `create_governance_record` stores all 4 officer fields, `get_governance_record` returns by tenant_id, `update_governance_record` modifies officers and sets updated_at, `list_governance_records` paginates correctly. Review cycle scheduling defaults to 90 days; overdue detection surfaces past-due reviews. GET /v1/governance/records and GET /v1/governance/status return correct governance data. 16 tests pass.

- **Task 2 — Verified existing risk assessment framework with 6 dimensions:** Tests confirm `create_risk_assessment` stores 6 core dimensions (privacy, security, bias, explainability, fairness, safety) with severity + likelihood scoring. `overall_risk_score` computed as weighted average across all dimensions (severity * likelihood / 25, normalized 0-1). `flag_reassessment` correctly sets `reassessment_required=True`. `check_config_triggers_reassessment` detects entity-type-related config field changes (entity_types, detection, recognizer, etc.) and auto-flags reassessment. Extension dimensions stored alongside core. 20 tests pass.

## Task Commits

Note: Plan 14-01 foundation was implemented as part of earlier governance work. Key commits:

1. **Task 1: Governance record model + CRUD + endpoints** — `2867072` (feat)
2. **Task 2: Risk assessment framework with 6 dimensions** — `2867072` (feat)
3. **Test files** — `33a34bb` (test)

**Plan metadata:** Pending final commit

## Files Created/Modified

From previous work:
- `src/anonreq/models/governance.py` — Pydantic + SQLAlchemy ORM models (GovernanceOfficerRole, GovernanceOfficer, ReviewCycle, GovernanceRecord, RiskDimensionScore, RiskAssessment)
- `src/anonreq/governance/__init__.py` — Re-exports all governance functions and classes
- `src/anonreq/governance/records.py` — Async PostgreSQL CRUD (create/get/update/list)
- `src/anonreq/governance/reviews.py` — Review cycle scheduling, overdue detection, completion
- `src/anonreq/governance/risk.py` — 6-dimension risk assessment, scoring, reassessment flagging
- `src/anonreq/governance/router.py` — FastAPI endpoints: /v1/governance/records, /v1/governance/status, /v1/governance/config/trigger-reassessment
- `src/anonreq/main.py` — Governance routers included with auth; oversight/lifecycle/transparency/notification services initialized
- `alembic/versions/002_create_governance_tables.py` — Migration creating review_cycle, governance_record, risk_assessment tables
- `tests/test_governance_records.py` — 16 tests for CRUD, review cycles, status
- `tests/test_governance_risk.py` — 20 tests for dimensions, CRUD, reassessment, extensions, scoring

## Decisions Made

- Followed plan decisions D-001 through D-009 exactly as specified
- Used JSON-column storage for dynamic officer lists and risk dimension scores (PostgreSQL Text column with JSON serialization)
- SQLAlchemy async ORM with `joinedload` for review_cycle relationship
- Alembic migration 002 adds FK relationships: governance_record → review_cycle, risk_assessment → governance_record
- Risk dimension scoring: severity * likelihood / 25, equally weighted average across all dimensions

## Deviations from Plan

None — plan executed exactly as specified.

### Auto-fixed Issues

None — no deviations needed. Code was already implemented and all tests pass.

---

**Total deviations:** 0
**Impact on plan:** N/A

## Issues Encountered

None

## Self-Check: PASSED

- [x] `src/anonreq/models/governance.py` exists (193 lines, exceeds 80-line minimum)
- [x] `src/anonreq/governance/__init__.py` exists, re-exports all router + functions
- [x] `src/anonreq/governance/records.py` exists (197 lines, exceeds 100-line minimum)
- [x] `src/anonreq/governance/reviews.py` exists (235 lines, exceeds 60-line minimum)
- [x] `src/anonreq/governance/risk.py` exists (306 lines, exceeds 100-line minimum)
- [x] `src/anonreq/governance/router.py` exists (435 lines, exceeds 80-line minimum)
- [x] `tests/test_governance_records.py` exists (371 lines, exceeds 60-line minimum)
- [x] `tests/test_governance_risk.py` exists (428 lines, exceeds 60-line minimum)
- [x] Alembic migration 002 exists with governance tables
- [x] `main.py` includes governance routers with auth
- [x] All 36 tests pass
- [x] Model verification: models import and construct correctly
- [x] Scoring arithmetic: compute_dimension_score(3,2) = 0.24, compute_overall_risk_score([0.24, 0.48]) = 0.36
- [x] Config trigger detection: entity_types field triggers reassessment, rate_limit does not
- [x] Metadata commit in git log: `674a980`

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Governance foundation complete. Ready for Phase 14-02 (Oversight: approval queue, kill-switch), Phase 14-03 (Lifecycle management), and Phase 14-04 (Transparency reports).

---

*Phase: 14-ai-governance-oversight*
*Completed: 2026-07-03*
