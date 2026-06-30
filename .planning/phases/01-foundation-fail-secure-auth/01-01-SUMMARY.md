---
phase: 01-foundation-fail-secure-auth
plan: 01
subsystem: project-scaffold-config
tags: [scaffold, config, pydantic-settings, build-system, test-infrastructure]
requires: []
provides: [pyproject.toml, requirements.txt, requirements-dev.txt, config.py, conftest.py]
affects: [all-phase-1-plans]
tech-stack:
  added:
    - Python 3.12+ with setuptools build system
    - pydantic-settings v2 for env var loading
    - pyyaml safe_load for provider registry
    - pytest with asyncio auto mode
    - httpx AsyncClient for test fixtures
  patterns:
    - Env var prefix `ANONREQ_` for all configuration
    - Module-level singleton `settings = Settings()` for fail-secure startup
    - `extra="ignore"` to silently drop unknown env vars
    - `yaml.safe_load()` prevents code injection from YAML
    - Monorepo layout: `src/` package with `tests/` mirror
key-files:
  created:
    - pyproject.toml — build system, deps, pytest/coverage config
    - requirements.txt — pinned production deps
    - requirements-dev.txt — pinned dev deps
    - .env.example — documents all 7 env vars
    - config/providers.yaml — provider registry stub
    - src/anonreq/__init__.py — package docstring
    - src/anonreq/__about__.py — version = "0.1.0"
    - src/anonreq/models/__init__.py — models sub-package
    - src/anonreq/config.py — Pydantic Settings + YAML loader
    - tests/__init__.py — test suite init
    - tests/conftest.py — shared fixtures
    - tests/test_config.py — 22 config tests
  modified: []
decisions:
  - "Module-level settings singleton fails fast at import time (D-10)"
  - "yaml_file dropped from SettingsConfigDict — pydantic-settings v2 ignores it without explicit YAML source configuration; load_provider_registry() handles YAML loading separately (D-16)"
  - "Host+Port are optional with defaults 0.0.0.0:8080 for Docker-first deployment"
duration: 12m
completed_date: "2026-06-30"
status: complete
---

# Phase 1 Plan 1: Project Scaffold & Configuration Module Summary

Established the Python project scaffold and configuration management layer for the AnonReq gateway. Creates build system, pinned dependency files, package layout under `src/anonreq/`, the hybrid Pydantic Settings + YAML configuration module, and shared test infrastructure.

## Objective Fulfilled

> Create a working Python project with `python -c "from anonreq.config import settings"` succeeding after `pip install -e .` and `pytest tests/test_config.py -x` passing.

- ✅ `pip install -e ".[dev]"` completes without errors
- ✅ `ANONREQ_API_KEY=... ANONREQ_VALKEY_URL=... ANONREQ_PRESIDIO_URL=... python3 -c "from anonreq.config import settings"` succeeds
- ✅ `pytest tests/test_config.py -x --tb=short` — 22 passed
- ✅ All 12 files created

## Task Results

### Task 1: Create project scaffold (auto)

Created 9 scaffold files establishing the project structure:
- **pyproject.toml**: setuptools build system, name=anonreq, version=0.1.0, all Phase 1 deps declared
- **requirements.txt / requirements-dev.txt**: pinned exact versions from pip freeze
- **.env.example**: documents 3 required + 4 optional env vars
- **config/providers.yaml**: empty stub with `yaml.safe_load()` contract
- **Package layout**: `src/anonreq/` with `__init__.py`, `__about__.py`, `models/__init__.py`
- **tests/__init__.py**: test suite entry point
- **Commit**: `ba1cd90`

### Task 2 (RED → GREEN): Configuration module (auto, tdd=true)

**RED phase** (commit `bb426a5`):
- Wrote `tests/conftest.py` with `settings_override`, `app`, `test_client` fixtures
- Wrote `tests/test_config.py` with 22 tests covering:
  - Settings loading with correct types
  - API_KEY validation (min 32 chars, boundary test, error message check)
  - Missing required env vars (parametrized × 3 + all-missing)
  - Optional defaults (HOST, PORT, LOG_LEVEL, REQUEST_TIMEOUT_SECONDS)
  - Custom optional var overrides
  - Unknown env vars silently ignored (`extra="ignore"`)
  - URL acceptance (redis://, rediss://, http://, https://)
  - Provider registry loading from YAML
- Tests failed as expected: `ModuleNotFoundError: No module named 'anonreq.config'`

**GREEN phase** (commit `e407009`):
- Implemented `src/anonreq/config.py`:
  - `Settings(BaseSettings)` with `env_prefix="ANONREQ_"`, `extra="ignore"`
  - 3 required fields with `validation_alias` and `min_length` constraints
  - 4 optional fields with documented defaults
  - `@field_validator("API_KEY")` with clear error message
  - Module-level `settings = Settings()` singleton for fail-secure startup
  - `load_provider_registry()` using `yaml.safe_load()`
- Fixed pyproject.toml build backend and conftest module-level env setup
- All 22 tests pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pyproject.toml build backend**
- **Found during:** Task 1 verification (pip install failed)
- **Issue:** `setuptools.backends._legacy._Backend` does not exist in installed setuptools. `pip install -e .` failed with `BackendUnavailable`.
- **Fix:** Changed to `setuptools.build_meta` (the standard setuptools build backend)
- **Files modified:** pyproject.toml
- **Commit:** `e407009`

**2. [Rule 1 - Bug] Added module-level env vars to conftest.py**
- **Found during:** Task 2 GREEN phase (test collection failed)
- **Issue:** The module-level `settings = Settings()` singleton in config.py is instantiated at module import time, which happens during pytest test collection — BEFORE any fixture runs. Tests failed with validation errors because no env vars were set.
- **Fix:** Added `os.environ.setdefault()` calls at module level in conftest.py to ensure required env vars exist before test collection imports config.py
- **Files modified:** tests/conftest.py
- **Commit:** `e407009`

**3. [Rule 1 - Bug] Removed `yaml_file` from SettingsConfigDict**
- **Found during:** Task 2 GREEN phase (pytest warning)
- **Issue:** pydantic-settings v2 ignores `yaml_file` config key unless a `YamlConfigSettingsSource` is explicitly configured. Using it triggers a runtime warning: "Config key `yaml_file` is set in model_config but will be ignored because no YamlConfigSettingsSource source is configured."
- **Fix:** Removed `yaml_file="config/providers.yaml"` from `SettingsConfigDict`. YAML loading is handled separately via `load_provider_registry()` which uses `yaml.safe_load()`.
- **Files modified:** src/anonreq/config.py
- **Commit:** `e407009`

**4. [Rule 1 - Bug] Updated pinned dependency versions**
- **Found during:** Task 1 commit review (initial pinned versions were placeholders)
- **Issue:** Initial requirements.txt had incorrect pinned versions (e.g., fastapi==0.115.0, pydantic-settings==2.5.2) — didn't match actual installed versions.
- **Fix:** Updated with versions from `pip freeze` after successful install
- **Files modified:** requirements.txt, requirements-dev.txt
- **Commit:** `e407009`

## Known Stubs

None. All placeholders (`config/providers.yaml` empty stub, `tests/` init files) are intentional per plan specification.

## Threat Surface Scan

No new threat surface beyond what the plan's threat model covers:
- T-01-01-01: mitigates env var injection via `extra="ignore"` + `field_validator` → ✅ implemented
- T-01-01-02: mitigates YAML code injection via `yaml.safe_load()` → ✅ implemented
- T-01-01-SC: dependency supply chain — all packages verified per RESEARCH.md → ✅ pinned

## Verification Results

```text
=== File verification ===
FOUND: pyproject.toml
FOUND: requirements.txt
FOUND: requirements-dev.txt
FOUND: .env.example
FOUND: config/providers.yaml
FOUND: src/anonreq/__init__.py
FOUND: src/anonreq/__about__.py
FOUND: src/anonreq/models/__init__.py
FOUND: src/anonreq/config.py
FOUND: tests/__init__.py
FOUND: tests/conftest.py
FOUND: tests/test_config.py

=== Test run ===
22 passed in 0.15s

=== Module import ===
Import OK — API_KEY=8a16f9fe... HOST=0.0.0.0 PORT=8080
```

## Success Criteria Checklist

- [x] pyproject.toml declares all Phase 1 dependencies with correct versions
- [x] config.py loads env vars with validation, rejects short API keys and missing required vars
- [x] YAML safe_load prevents code injection from providers.yaml
- [x] .env.example documents all 7 env vars (3 required, 4 optional)
- [x] conftest.py provides settings_override and test_client fixtures
- [x] `pytest tests/test_config.py -x` passes with 22 test cases (>6 required)
- [x] All 12 files created and committed to git

## Self-Check: PASSED

All 12 created files verified present. All 3 commits verified in git log. SUMMARY.md content verified.

| Hash | Type | Message |
|------|------|---------|
| `ba1cd90` | chore | Create project scaffold — pyproject.toml, package layout, dependency files |
| `bb426a5` | test | Add failing test for config module (RED) |
| `e407009` | feat | Implement configuration module with Pydantic Settings (GREEN) |
