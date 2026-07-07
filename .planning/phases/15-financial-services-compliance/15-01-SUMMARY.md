---
phase: 15-financial-services-compliance
plan: 01
subsystem: detection
tags: [mnpi, presidio, restricted-names, minio, worm, sec-17a-4, tdd]

requires:
  - phase: 04-multi-locale-detection-compliance-presets
    provides: Detection pipeline with Presidio integration, locale-based recognizer bundles, exclusion list
  - phase: 13-ai-firewall-dlp
    provides: DLP audit logger, policy enforcement patterns
provides:
  - MNPI Presidio recognizer bundle (ticker symbols, deal codenames, tenant restricted names)
  - Hot-reloadable tenant restricted-names list manager
  - MinIO WORM bucket integration for SEC 17a-4 MNPI audit retention
  - MnpiAuditEvent model (SHA-256 hashes only, no raw values)
affects:
  - 15-financial-services-compliance (future plans: MRM, DORA, AML)
  - policy-enforcement (MNPI policy actions: anonymize, flag, block, quarantine)

tech-stack:
  added:
    - minio>=7.2.0 (already in dependencies)
  patterns:
    - YAML-configurable Presidio recognizer with MNPIConfig dataclass
    - Hot-reload via file mtime polling with thread safety (threading.Lock)
    - MinIO WORM bucket with COMPLIANCE retention for regulatory compliance
    - TDD: test-first with RED/GREEN/REFACTOR per plan-level TDD enforcement

key-files:
  created:
    - src/anonreq/detection/recognizers/__init__.py
    - src/anonreq/detection/recognizers/mnpi.py
    - src/anonreq/detection/pipeline.py
    - src/anonreq/config/restricted_names.py
    - src/anonreq/storage/__init__.py
    - src/anonreq/storage/minio.py
    - config/mnpi_recognizers.yaml
    - config/restricted_names.yaml
    - tests/test_mnpi_recognizer.py
    - tests/test_restricted_names.py
    - tests/test_storage_minio.py
  modified:
    - src/anonreq/detection/__init__.py
    - src/anonreq/models/detection.py
    - src/anonreq/models/audit.py
    - src/anonreq/pipeline/detection.py
    - src/anonreq/routing/chat.py
    - src/anonreq/config.py → src/anonreq/config/__init__.py (package conversion)

key-decisions:
  - MNPIRecognizer is standalone (not extending Presidio EntityRecognizer) because the existing codebase uses Presidio via HTTP client, not Python SDK — matches existing detection architecture
  - RestrictedNamesManager uses mtime-based polling rather than inotify for portability (Docker compat)
  - MinIO client lazily initialized to avoid startup failures when MinIO is not yet configured
  - Only SHA-256 hashes stored in audit events per T-15-01-01; raw values never persisted

patterns-established:
  - MNPI detection runs after core Presidio pipeline as a separate scan (no arbitration needed since entity types don't overlap)
  - config.py → config/ package pattern enables submodule organization for config-related code
  - YAML-backed configuration with sane defaults and graceful degradation on missing/corrupt files

requirements-completed: [REQ-37, REQ-38, REQ-39]

duration: 2h 30min
completed: 2026-07-04
status: complete
---

# Phase 15 Plan 01: MNPI Detection & SEC 17a-4 Retention Summary

**MNPI Presidio recognizer (tickers, deal codenames, restricted names) + hot-reloadable tenant restricted-names list + MinIO WORM bucket for SEC 17a-4 MNPI audit compliance**

## Performance

- **Duration:** 2h 30min
- **Started:** 2026-07-04T16:30:00Z
- **Completed:** 2026-07-04T19:00:00Z
- **Tasks:** 3
- **Files modified:** 12 created, 6 modified

## Accomplishments

- MNPIRecognizer detects NYSE/NASDAQ ticker symbols (1-4 uppercase, optional .suffix), deal codenames (Project/Operation/Initiative + Name), and tenant restricted names
- RestrictedNamesManager provides YAML-configurable tenant-specific restricted names with case-insensitive matching and mtime-based hot-reload
- MinioWormBucket creates/manages `anonreq-mnpi-audit` WORM bucket with COMPLIANCE retention mode, 7-year object lock for SEC 17a-4
- All detection is in-memory (T-15-01-01); audit events store only SHA-256 hashes
- config.py converted to config/ package for submodule organization
- 61 tests across 3 test suites — all passing

## Task Commits

Each task was committed atomically (TDD tasks with separate RED/GREEN commits):

1. **Task 1: MNPI Presidio recognizer bundle (TDD)**
   - `2c0310a` — test(15-01): add failing test for MNPI recognizer bundle (RED)
   - `c998658` — feat(15-01): implement MNPI Presidio recognizer bundle (GREEN)

2. **Task 2: Tenant restricted-names list with hot-reload (TDD)**
   - `db1f2d6` — test(15-01): add failing test for restricted names manager (RED)
   - `2fc22b9` — feat(15-01): implement RestrictedNamesManager with hot-reload (GREEN)
   - `26e335e` — feat(15-01): integrate RestrictedNamesManager into detection pipeline

3. **Task 3: MinIO WORM bucket for SEC 17a-4 MNPI audit retention**
   - `ff6905d` — feat(15-01): implement MinIO WORM bucket for SEC 17a-4 MNPI audit retention

**Plan metadata:** Pending (after SUMMARY.md creation)

## TDD Gate Compliance

- Task 1: ✅ RED gate (`2c0310a`) → GREEN gate (`c998658`)
- Task 2: ✅ RED gate (`db1f2d6`) → GREEN gate (`2fc22b9`)
- Task 3: Non-TDD, no gate required

## Files Created/Modified

### Created (12 files)

| File | Description |
|------|-------------|
| `src/anonreq/detection/recognizers/__init__.py` | Recognizers subpackage init |
| `src/anonreq/detection/recognizers/mnpi.py` | MNPIRecognizer, MNPIConfig, create_mnpi_bundle |
| `src/anonreq/detection/pipeline.py` | MNPI pipeline integration (load_mnpi_recognizers, merge_mnpi_detections) |
| `src/anonreq/config/restricted_names.py` | RestrictedNamesManager with hot-reload and thread safety |
| `src/anonreq/storage/__init__.py` | Storage subpackage init |
| `src/anonreq/storage/minio.py` | MinioWormBucket, create_mnpi_worm_bucket |
| `config/mnpi_recognizers.yaml` | MNPI recognizer configuration (ticker patterns, codename conventions) |
| `config/restricted_names.yaml` | Sample tenant restricted-names list (acme-corp, bigbank) |
| `tests/test_mnpi_recognizer.py` | 17 tests: ticker detection, deal codenames, policy actions, bundle creation |
| `tests/test_restricted_names.py` | 22 tests: load, match, hot-reload, thread safety, edge cases |
| `tests/test_storage_minio.py` | 22 tests: bucket creation, store/retrieve, retention, factory |

### Modified (6 files)

| File | Change |
|------|--------|
| `src/anonreq/detection/__init__.py` | Added recognizers subpackage reference |
| `src/anonreq/models/detection.py` | Added MNPI_TICKER, MNPI_DEAL, MNPI_RESTRICTED_NAME entity types |
| `src/anonreq/models/audit.py` | Added MnpiAuditEvent dataclass (SHA-256 hashes only) |
| `src/anonreq/pipeline/detection.py` | DetectionStage accepts mnpi_recognizers, runs post-core MNPI scan |
| `src/anonreq/routing/chat.py` | build_pre_provider_pipeline loads RestrictedNamesManager + MNPI recognizers |
| `src/anonreq/config.py → config/__init__.py` | Converted to package for submodule support |

## Decisions Made

- **Standalone recognizer pattern:** MNPIRecognizer does not extend Presidio's `EntityRecognizer` class because the existing codebase uses Presidio via HTTP client (`PresidioClient`), not the Python SDK. This matches the existing detection architecture where regex detection runs locally and NER runs via HTTP.
- **mtime-based hot-reload:** RestrictedNamesManager uses file modification time polling rather than inotify/fswatch for portability across Docker environments. Polling is triggered explicitly via `reload()` rather than a background thread, keeping the API surface minimal.
- **Lazy MinIO client:** `MinioWormBucket` lazily initializes the MinIO client on first use, allowing the application to start without a running MinIO instance. The factory function `create_mnpi_worm_bucket()` reads from env vars with sensible defaults.
- **Hash-only audit:** `MnpiAuditEvent` stores only `detected_value_hash` (SHA-256), never raw detected values. The model has no field for storing plaintext MNPI, making it impossible to accidentally persist sensitive data.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `config.py` → `config/` package conversion required for submodule**
- **Found during:** Task 2 (RestrictedNamesManager implementation)
- **Issue:** Plan referenced `src/anonreq/config/restricted_names.py`, but `config.py` existed as a module file, shadowing any `config/` package directory
- **Fix:** Converted `config.py` to `config/__init__.py` package with all existing exports preserved
- **Files modified:** src/anonreq/config.py (deleted), src/anonreq/config/__init__.py (created identically)
- **Verification:** All existing `from anonreq.config import settings` imports continue to work
- **Committed in:** `2fc22b9` (Task 2 GREEN commit)

**2. [Rule 3 - Blocking] `minio.Retention` uses string mode, not `RetentionMode` enum**
- **Found during:** Task 3 (MinIO WORM bucket verification)
- **Issue:** minio>=7.2.0 `Retention` dataclass takes `mode: str`, not a `RetentionMode` enum — import error on startup
- **Fix:** Changed `from minio.retention import Retention, RetentionMode` to `from minio.retention import Retention`, used `mode="COMPLIANCE"` string literal
- **Files modified:** src/anonreq/storage/minio.py
- **Verification:** Module imports correctly, all tests pass
- **Committed in:** `ff6905d` (Task 3 commit, pre-commit fix)

**3. [Rule 3 - Blocking] Logging format mismatch with standard `logging` module**
- **Found during:** Task 3 (MinIO test execution)
- **Issue:** `logger.error("msg", bucket=x, error=y)` uses structlog-style extra kwargs but logger was `logging.getLogger()`, causing `TypeError`
- **Fix:** Changed to standard `logging` printf-style: `logger.error("MNPI WORM bucket setup failed: %s - %s", bucket, exc)`
- **Files modified:** src/anonreq/storage/minio.py
- **Verification:** All 22 MinIO tests pass
- **Committed in:** `ff6905d` (Task 3 commit, pre-commit fix)

---

**Total deviations:** 3 auto-fixed (3 Rule 3 - blocking)
**Impact on plan:** All fixes were necessary for code to function. No scope creep — each fix was directly related to the task's implementation matching the actual runtime environment.

## Issues Encountered

- **pytest timeout/hang when collecting test files:** Initially, running `pytest` for MinIO test file hung indefinitely. Root cause was unclear — clearing `.pytest_cache` and using `.venv/bin/python3 -m pytest` (instead of an aliased `pytest`) resolved it. Likely a stale cache or `PYTHONPATH` issue with the config.py → config/ package conversion.

## Known Stubs

- `src/anonreq/detection/pipeline.py` `merge_mnpi_detections()` function is defined but not yet called in the pipeline flow — it's available for future use when explicit merge logic is needed. Currently MNPI detections are merged directly in `DetectionStage.execute()` via `ctx.detections.extend(mnpi_results)`.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| `threat_flag: new_minio_client` | `src/anonreq/storage/minio.py` | New MinIO client instantiation at `_get_client()` — uses env var credentials with configurable secure mode. Credential exposure is limited to in-memory usage. |
| `threat_flag: yaml_file_read` | `src/anonreq/config/restricted_names.py` | `yaml.safe_load()` per T-15-01-03 prevents code injection. File path is fixed at construction time, not user-controllable. |

## Next Phase Readiness

- MNPI detection ready for policy integration (action mapping: anonymize, flag, block, quarantine)
- RestrictedNamesManager ready for admin UI integration (POST /v1/admin/config/restricted-names/reload endpoint)
- MinIO WORM bucket ready for pipeline integration (store events after MNPI detection)
- All 3 test suites (61 tests) passing — foundation for MRM, DORA, and AML plans

---

## Self-Check: PASSED

- ✅ All 11 created files exist
- ✅ All 5 modified files exist  
- ✅ All 6 commits present in git log
- ✅ All 61 tests pass (17 MNPI + 22 restricted-names + 22 MinIO)

---

*Phase: 15-financial-services-compliance*
*Plan: 01*
*Completed: 2026-07-04*
