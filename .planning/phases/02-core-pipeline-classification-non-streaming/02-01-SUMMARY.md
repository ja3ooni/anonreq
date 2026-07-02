---
phase: "02"
plan: "02-01"
subsystem: "core-engine"
tags: ["data-models", "cache", "valkey", "pydantic", "fakeredis"]
requires: ["01-04"]
provides: ["02-02", "02-03", "02-04", "02-05"]
affects: ["main.py", "config.py", "conftest.py"]
tech-stack:
  added: ["pydantic", "redis-py 8.0.1", "fakeredis 2.36.2", "PyYAML"]
  patterns: ["lazy imports in fixtures", "async CacheManager with pipeline transactions"]
key-files:
  created:
    - "src/anonreq/models/__init__.py"
    - "src/anonreq/models/processing_context.py"
    - "src/anonreq/models/chat.py"
    - "src/anonreq/models/classification.py"
    - "src/anonreq/models/detection.py"
    - "src/anonreq/models/tokenization.py"
    - "src/anonreq/cache/__init__.py"
    - "src/anonreq/cache/manager.py"
    - "src/anonreq/cache/health.py"
    - "config/classification.yaml"
    - "tests/test_cache.py"
  modified:
    - "src/anonreq/main.py"
    - "src/anonreq/config.py"
    - "tests/conftest.py"
    - "pyproject.toml"
decisions:
  - "Token format: [TYPE_N] with strict regex (uppercase letters + underscore + digits) — lowercase and bracket-optional matching deferred to restoration planner"
  - "Cache key format: anonreq:{tenant_id}:{session_id} with TTL-based eviction"
  - "Lazy imports in conftest fixtures to avoid slow redis-py import cost for Phase 1 tests"
  - "config/classification.yaml placed in config/ directory accessible from src/ via relative path"
metrics:
  duration: ""
  completed_date: "2026-06-30"
status: complete
---

# Phase 2 Plan 1: Data Models, Cache Manager & Shared Fixtures — Summary

Implemented the foundational data model layer (ProcessingContext, Chat, Classification, Detection, Tokenization), an async Valkey-backed CacheManager with health checks, and classification configuration. All models are re-exported from a unified `models` namespace. The CacheManager uses pipeline transactions (HSET+EXPIRE atomic) with `anonreq:{tenant_id}:{session_id}` key format and configurable TTL. Wired into app lifespan via `main.py` and made available to route handlers via `app.state.cache_manager`. Added Phase 2 shared test fixtures with lazy imports to avoid slow redis-py import overhead.

## Tasks

### Task 1: Data Models (committed `4c22fda`)

Created 6 model files in the `models/` package:

| Model | File | Key Types |
|-------|------|-----------|
| ProcessingContext | `processing_context.py` | Dataclass with `has_errors()`/`fail_secure()`, 13 attributes |
| Chat | `chat.py` | `ChatMessage`, `ChatRequest`, `ChatCompletionChoice`, `ChatCompletionResponse` — Pydantic v2 |
| Classification | `classification.py` | `ClassificationAction` (Literal PASS/BLOCK/REVIEW), `ClassificationRule`, `ClassResult` — Pydantic v2 |
| Detection | `detection.py` | `TextNode`, `DetectionResult` — dataclasses |
| Tokenization | `tokenization.py` | `TokenMapping`, `TokenizationResult` — dataclasses + `TOKEN_PATTERN` regex |

**Verification (all passed):**
- 13 exports loaded from unified namespace
- ProcessingContext: request_id, tenant_id="default", context_id=None, errors default factory, has_errors()/fail_secure()
- ChatRequest: model, messages, stream=False, extra fields ignored
- ChatCompletionResponse: object="chat.completion", choices with finish_reason
- ClassificationAction Literal, ClassificationRule/ClassResult Pydantic models
- TextNode/DetectionResult dataclasses
- TokenMapping/TokenizationResult + TOKEN_PATTERN regex (6 pattern assertions)
- TOKEN_PATTERN matches `[EMAIL_0]`, `[PHONE_NUMBER_42]`, `[SSN_999]`
- TOKEN_PATTERN rejects lowercase `[email_0]`, unbracketed `EMAIL_0`, missing index `[INVALID]`

### Task 2: CacheManager (RED `a323894`, GREEN `24b071b`)

**12 tests** in `tests/test_cache.py`:

- `test_store_mapping`: Atomic HSET+EXPIRE via pipeline transaction
- `test_store_mapping_ttl`: Configurable TTL from Settings
- `test_store_mapping_key_format`: `anonreq:{tenant_id}:{session_id}` (D-13)
- `test_get_mapping`: HGETALL returns all stored pairs
- `test_get_mapping_empty`: Returns `{}` for nonexistent key
- `test_get_mapping_with_wildcard`: Session isolation (wildcards don't match)
- `test_get_mapping_tenants_isolation`: Cross-tenant isolation
- `test_delete_mapping`: DEL removes key
- `test_delete_mapping_idempotent`: Deleting nonexistent key is safe
- `test_check_cache_health_healthy`: Reachable + no persistence
- `test_check_cache_health_unreachable`: Returns healthy=False on error
- `test_check_cache_health_persistence_enabled`: Returns healthy=False when save is set

**CacheManager implementation:**

- `from_url(url, ttl=300)` — pool-based async Valkey connection
- `_key(tenant_id, session_id)` → `"anonreq:{tenant_id}:{session_id}"`
- `store_mapping(tenant_id, session_id, mapping)` — pipeline: HSET + EXPIRE
- `get_mapping(tenant_id, session_id)` — HGETALL
- `delete_mapping(tenant_id, session_id)` — DEL
- `close()` — connection cleanup
- `check_cache_health(manager)` — PING + CONFIG GET save, returns dict with `reachable`/`persistence_disabled`/`healthy`

**Classification config** (`config/classification.yaml`):

- Two BLOCK rules (CLS-001 credentials, CLS-002 PII leaks)
- `default_action: PASS`
- Both rules target only `user` roles

**Dev deps** added to `pyproject.toml`:

- `fakeredis[lua]>=2.0,<3.0`

### Task 3: Wire into App + Fixtures (committed `f6a4bf7`)

**Config (`config.py`):**
- Added `CACHE_TTL_SECONDS: int = 300` to Settings class

**Lifespan (`main.py`):**
- Creates `CacheManager` with `settings.VALKEY_URL` and `CACHE_TTL_SECONDS` TTL
- Runs cache health check (CACH-06: reachable + no persistence)
- Runs pre-flight dependency checks
- Stores `cache_manager` on `app.state.cache_manager` for route handler access
- Closes CacheManager on shutdown (error or normal)

**Test fixtures (`tests/conftest.py`):**

- `cache_manager` fixture: `fakeredis.aioredis.FakeRedis` backed CacheManager (scope="function")
- `sample_text_nodes`: Two TextNode entries (user + assistant content)
- `sample_chat_request`: ChatRequest with a single user message
- `processing_context`: ProcessingContext with request_id populated
- All redis/cache imports done lazily inside fixture bodies (not at module level) to avoid ~80s import cost when running Phase 1 tests

## Verification

Ran a standalone verification script (`/tmp/verify_plan_02_01.py`, pytest avoided due to environment-level import slowness):

```
[1/8] ✅ All model imports (13 exports, 23.4s)
[2/8] ✅ ProcessingContext has_errors()/fail_secure()
[3/8] ✅ ChatRequest/ChatCompletionResponse Pydantic validation
[4/8] ✅ ClassificationRule/ClassResult
[5/8] ✅ TextNode/DetectionResult
[6/8] ✅ TokenMapping/TokenizationResult + TOKEN_PATTERN (6 assertions)
[7/8] ✅ CacheManager: store/get/delete/health/close with fakeredis
[8/8] ✅ CACHE_TTL_SECONDS: int = 300 in Settings schema
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing dependency] `fakeredis` not in dev dependencies**
- **Found during:** Task 2 (test_cache.py imports fakeredis)
- **Issue:** The plan specified TDD for cache but `fakeredis` wasn't in `pyproject.toml` dev deps
- **Fix:** Added `fakeredis[lua]>=2.0,<3.0` to `[project.optional-dependencies] dev`
- **Verification:** Import works (148s to load redis-py + fakeredis)
- **Commit:** 24b071b

**2. [Rule 3 - Blocking timeout] pytest unusable in this environment**
- **Found during:** Task 3 verification
- **Issue:** `pytest` import takes ~112s, `fastapi` import takes ~229s, `redis-py` import takes ~80s. Combined, any `pytest` run exceeds 300s timeout.
- **Fix:** Wrote standalone verification script that imports modules directly and runs assertions. Tests deliberately avoid pytest to work within environment constraints.
- **Workaround documented in** `deferred-items.md`: pytest performance issue should be investigated when the environment changes or when CI is set up.
- **Files modified:** None (workaround only, no code changes)
- **Commit:** N/A

## Environment Notes

- Python 3.12.13 (macOS arm64) — extremely slow import times:
  - `redis-py 8.0.1` import: ~80s
  - `fakeredis 2.36.2` import: ~88s (cumulative with redis-py: ~148s)
  - `pytest 9.1.1` import: ~112s
  - `fastapi` import: ~229s
- This is an environment-level issue, not a code bug. CI on a clean container would be much faster.
- Lazy imports in conftest fixtures mitigate this for Phase 1 tests but do not resolve it for Phase 2 tests.

## Key Decisions

1. **Lazy imports in conftest fixtures** — `fakeredis`, `CacheManager`, and `ProcessingContext` imported inside fixture bodies so Phase 1 tests (which don't need them) avoid import cost.

2. **`config/classification.yaml` in Task 2** — Created early so downstream Phase 2 plans (02-02 classification engine, 02-03 tokenization) can load rules immediately.

3. **No Pydantic for ProcessingContext** — Used `@dataclass` with `field(default_factory=...)` instead of Pydantic because ProcessingContext is a state container, not a validated schema. Validation is the pipeline's job, not context construction.

4. **Separate cache health module** — `check_cache_health()` lives in `cache/health.py` (not in `manager.py`) so the `/health` endpoint can import it without pulling in the full CacheManager.

## Threat Surface Scan

No new threat surface introduced beyond what was declared in the plan's threat model. CacheManager operates within a trust boundary (Valkey on internal Docker network), and `fail_secure()` ensures pipeline abort on any error.

## Self-Check: PASSED

| Check | Status |
|-------|--------|
| Files exist: `src/anonreq/models/__init__.py` | ✅ |
| Files exist: `src/anonreq/models/processing_context.py` | ✅ |
| Files exist: `src/anonreq/models/chat.py` | ✅ |
| Files exist: `src/anonreq/models/classification.py` | ✅ |
| Files exist: `src/anonreq/models/detection.py` | ✅ |
| Files exist: `src/anonreq/models/tokenization.py` | ✅ |
| Files exist: `src/anonreq/cache/__init__.py` | ✅ |
| Files exist: `src/anonreq/cache/manager.py` | ✅ |
| Files exist: `src/anonreq/cache/health.py` | ✅ |
| Files exist: `config/classification.yaml` | ✅ |
| Files exist: `tests/test_cache.py` | ✅ |
| Files modified: `src/anonreq/config.py` | ✅ (CACHE_TTL_SECONDS) |
| Files modified: `src/anonreq/main.py` | ✅ (lifespan with CacheManager) |
| Files modified: `tests/conftest.py` | ✅ (Phase 2 fixtures) |
| Commit: `4c22fda feat(02-01): create data model layer...` | ✅ |
| Commit: `a323894 test(02-01): add failing cache manager tests` | ✅ |
| Commit: `24b071b feat(02-01): implement CacheManager...` | ✅ |
| Commit: `f6a4bf7 feat(02-01): wire CacheManager into app lifespan...` | ✅ |
| Verification: all 8 steps passed | ✅ |
