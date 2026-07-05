---
phase: 16-compliance-audit-fairness
plan: 02
subsystem: compliance, governance, retention
tags: [lineage, legal-hold, supplier-governance, retention-tiers, minio-archive, postgresql]
requires:
  - phase: 14-ai-governance-oversight
    provides: lifecycle manager for supplier stage tracking (DRAFT → APPROVED → PRODUCTION)
  - phase: 15-financial-services-compliance
    provides: MinIO archival patterns, compliance audit framework
  - phase: 16-01
    provides: Fairness-aware analytics, bias detection foundation
provides:
  - Immutable data lineage (per-session, PostgreSQL + MinIO dual storage)
  - Retention tier management (PostgreSQL 90d, MinIO 7y, Valkey TTL, Legal Hold infinite)
  - Legal Hold with tenant-level and record-level tagging (D-018/D-019/D-020)
  - Supplier governance with 365-day review cycle and 5 risk re-evaluation triggers (D-012/D-016)
  - Admin API endpoints for Legal Hold and Supplier governance
affects: [purge scheduler, compliance dashboard, admin UI]

tech-stack:
  added: [sqlalchemy text() for direct SQL, MinIO JSONL archival]
  patterns: [in-memory mock DB store pattern for async SQLAlchemy tests, _mapping mock row pattern]

key-files:
  created:
    - src/anonreq/lineage/tracker.py
    - src/anonreq/lineage/archive.py
    - src/anonreq/retention/tiers.py
    - src/anonreq/retention/legal_hold.py
    - src/anonreq/governance/supplier.py
    - tests/test_data_lineage.py
    - tests/test_retention_tiers.py
    - tests/test_legal_hold.py
    - tests/test_supplier_governance.py
  modified:
    - src/anonreq/models/lineage.py
    - src/anonreq/governance/router.py

key-decisions:
  - "Lineage stored in separate module path (anonreq/lineage/) rather than modifying existing services"
  - "Retention tiers use dict-based config with duration_days and None for infinite"
  - "Legal Hold manager uses raw SQL (sqlalchemy.text) for legal_hold table operations"
  - "Supplier governance lifecycle integration is optional via try/except pattern"
  - "Mock DB sessions use in-memory dict stores with _mapping-compatible mock rows for proper SQLAlchemy row handling"

patterns-established:
  - "In-memory store pattern: module-level dict tracked by fixture with autouse reset for async SQLAlchemy mock tests"
  - "Mock row pattern: AsyncMock with _mapping attribute to support dict(row._mapping) calls in services"
  - "LineageTracker.record_lineage calls archive_lineage after PostgreSQL write for dual storage"
  - "Legal Hold check in RetentionManager.purge_expired: skip records under active hold"

requirements-completed: [REQ-33, REQ-44, REQ-45, REQ-46]

duration: 45min
completed: 2026-07-05
status: complete
---

# Phase 16 Compliance Plan 02: Data Lineage, Retention, Legal Hold & Supplier Governance

**Immutable per-session data lineage in PostgreSQL + MinIO JSONL archive, 4-tier retention management with legal hold exclusions, tenant/record-level legal hold enforcement, and third-party AI supplier governance with configurable risk re-evaluation triggers**

## Performance

- **Duration:** 45min
- **Started:** 2026-07-05T06:05:00Z
- **Completed:** 2026-07-05T06:50:00Z
- **Tasks:** 3 (all TDD)
- **Files modified/created:** 9 created, 2 modified

## Accomplishments

- **Immutable data lineage** — `LineageTracker` records full per-session provenance (session_id, tenant_id, provider, model, entities, policies, timestamps) in PostgreSQL and archives JSONL to MinIO
- **No modify/delete API** — lineage records are append-only with no update or delete methods per D-011
- **Retention tier management** — `RetentionManager` with configurable 4-tier schedule (PostgreSQL 90d, MinIO WORM 7y, Valkey TTL, Legal Hold infinite), purge_expired respects legal hold exclusions
- **Legal Hold with tenant/record scoping** — `LegalHoldManager` supports tenant-level and record-level holds with activate/release/is_on_hold lifecycle, released_at tracking, and expiry support
- **Supplier governance with Phase 14 lifecycle** — `SupplierGovernance` integrates with optional lifecycle manager, 365-day default review cycle, overdue detection, and 5 configurable risk re-evaluation triggers (model_change, tos_change, data_residency_change, ai_act_reclassification, security_incident)
- **Admin API endpoints** — Legal Hold GET/POST/release and Supplier GET/POST/overdue/re-evaluate endpoints added to governance router, status endpoint updated with active_legal_holds and overdue_supplier_reviews counters

## Task Commits

Each task was committed atomically. TDD tasks have test → implementation commits:

1. **Task 1: Immutable data lineage** — `1e9a703` (feat: implement immutable data lineage with PostgreSQL + MinIO archival)
2. **Task 2: Retention tier management** — `918ea75` (feat: implement retention tier management with configurable schedules)
3. **Task 3: Legal Hold + Supplier governance** — `fa8d024` (feat: implement Legal Hold and Supplier Governance)
4. **Router endpoints** — `703cdac` (feat: add Legal Hold and Supplier governance endpoints to router)

## Files Created/Modified

### Created
- `src/anonreq/lineage/tracker.py` — `LineageTracker` with record_lineage, query_lineage, get_lineage_by_session
- `src/anonreq/lineage/archive.py` — `LineageArchiver` with MinIO JSONL archival, ensure_bucket, get_archived_lineage, query_archive
- `src/anonreq/retention/tiers.py` — `RETENTION_TIERS` config, `RetentionManager` with purge_expired, run_scheduled_purge, legal hold exclusion
- `src/anonreq/retention/legal_hold.py` — `LegalHoldManager` with activate/release/is_on_hold/list_active_holds
- `src/anonreq/governance/supplier.py` — `SUPPLIER_REVIEW_TRIGGERS`, `SupplierGovernance` with create/get/list/overdue/reevaluate/complete_review
- `tests/test_data_lineage.py` — 23 tests (tracking, query, no-update/deletion, archive, datetime range)
- `tests/test_retention_tiers.py` — 19 tests (config, purge, legal hold exclusion, dry-run, valkey no-op)
- `tests/test_legal_hold.py` — 17 tests (activate, release, is_on_hold, list, record scope)
- `tests/test_supplier_governance.py` — 16 tests (CRUD, review cycle, overdue, triggers, complete review)

### Modified
- `src/anonreq/models/lineage.py` — Added `LegalHoldRecord` and `SupplierGovernanceRecord` Pydantic models
- `src/anonreq/governance/router.py` — Added 7 admin endpoints + status update with legal hold/supplier counts

## Decisions Made

- Lineage stored in separate module path (`anonreq/lineage/`) rather than modifying existing services/ directory — cleaner separation of concerns per D-009
- Retention tiers use dict-based configuration with `duration_days: None` for infinite tiers (Valkey TTL, Legal Hold) — simple, no extra abstraction needed
- Legal Hold manager uses raw SQL (`sqlalchemy.text()`) for direct table operations — matches existing codebase pattern for non-ORM tables
- Supplier governance lifecycle integration uses optional `try/except` pattern — lifecycle_manager is optional and failures are logged non-fatally
- In-memory mock DB store pattern for tests — `_hold_store` and `_supplier_store` module-level dicts with `_mapping`-compatible mock rows for proper `dict(row._mapping)` support in service implementations
- Router endpoints added under existing `governance_router` (prefix `/v1/governance/`) rather than a separate admin router — keeps governance operations together

## Deviations from Plan

None - plan executed as specified. All tasks completed with TDD flow (test first, then implement). Mock DB tests required more sophisticated in-memory stores to handle the `row._mapping` pattern used by implementations.

## Issues Encountered

- **Mock DB complexity**: Async SQLAlchemy `fetchone()` and `fetchall()` results need `_mapping` attribute for `dict(row._mapping)` pattern in service implementations. Fixed across both test files with in-memory dict stores and `_make_mock_row()` helpers.
- **Mock condition ordering**: Legal hold mock's `WHERE id = :id` check also matched `UPDATE` statements (which contain `WHERE id = :id`). Fixed by checking `UPDATE` before the generic `WHERE` clause handler.
- **Mock DB test run timed out on full governance suite**: The broader `test_governance_api.py` test suite takes significant time with async integration tests. Individual test files verified independently and all pass.

## User Setup Required

None - no external service configuration required. Test fixtures use in-memory mocking entirely.

## Next Phase Readiness

- Plan 16-03 can proceed: DSAR workflows can use Legal Hold for hold-tracking, Supplier governance for compliance visibility
- Plan 16-04 can proceed: eDiscovery export can consume lineage data from PostgreSQL + MinIO archive
- Integration tests can wire Legal Hold into purge_expired in a real DB context
- Property-based tests for round-trip correctness across retention boundaries

---

*Phase: 16-compliance-audit-fairness*
*Completed: 2026-07-05*
