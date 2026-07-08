# Phase 11, Plan 01: Immutable Audit Trail — Summary

**Status:** Complete
**Date:** 2026-07-02
**Tests:** 29/29 passing

## Files Created/Modified

### Models & Config
- `src/anonreq/models/audit.py` — AuditEvent dataclass, DailyAnchor dataclass, AuditEventModel ORM, Base, compute_event_hash
- `config/audit.yaml` — Audit retention and chain anchor configuration
- `src/anonreq/config.py` — Added `DATABASE_URL` and `ANCHOR_SIGNING_KEY` settings

### Alembic Migration
- `alembic/env.py` — Async Alembic configuration with asyncpg
- `alembic/versions/001_create_audit_event_table.py` — Creates `audit_event` table with SHA-384 hash chain columns + indexes
- `alembic/script.py.mako` — Migration template
- `alembic.ini` — Alembic configuration

### Services
- `src/anonreq/services/audit_chain.py` — AuditChainService with:
  - `store_event()` — Atomic hash chain insertion with `FOR UPDATE` (PostgreSQL)
  - `verify_chain()` — Full chain integrity walk
  - `get_events()` — Paginated query with event_type filter
  - `get_latest_event()` — Gets most recent event for prev_hash
  - **Append-only**: no update/delete methods
- `src/anonreq/services/chain_anchor.py` — ChainAnchorService with:
  - `compute_daily_anchor()` — SHA-384 root hash of all daily event hashes
  - `store_anchor()` — PostgreSQL + optional MinIO archive
  - `verify_anchor()` — Recomputes and verifies stored anchor
  - `run_daily_anchor()` — One-call compute+sign+store
  - `get_anchor_status()` — Latest anchor metadata

### API Routes
- `src/anonreq/routes/governance.py` — Governance endpoints (`/v1/governance/status`, `/v1/governance/audit/events`, `/v1/governance/audit/verify`)

### App Wiring
- `src/anonreq/main.py` — Database engine + AuditChainService + ChainAnchorService initialized in lifespan, governance router registered

### Dependencies
- `pyproject.toml` — Added sqlalchemy[asyncio], asyncpg, alembic, aiosqlite, minio

### Tests
- `tests/test_audit_chain.py` — 17 tests covering hash computation, chain linking, verification, tamper detection, append-only enforcement, pagination, type filtering
- `tests/test_chain_anchor.py` — 12 tests covering daily anchor computation, HMAC signing, storage, verification, tamper detection, status reporting

## Key Decisions
- **Integer PK** instead of BigInteger for SQLite compatibility during unit tests
- **Dialect-aware SQL** for `FOR UPDATE` and date extraction (`CAST(... AS date)` for PostgreSQL, `DATE()` for SQLite)
- **SQLite in-memory** for unit tests (aiosqlite), asyncpg for production
- **Hash field excluded** from `compute_event_hash()` to prevent circular dependency

## Verification
```
alembic upgrade 001 --sql   → valid PostgreSQL DDL (up + down)
compute_event_hash()         → 96-char SHA-384 hex
All audit chain imports OK   → AuditChainService, ChainAnchorService
No update/delete methods     → append-only API verified
```
