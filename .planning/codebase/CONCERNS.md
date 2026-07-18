# Codebase Concerns

**Analysis Date:** 2026-07-18

## Tech Debt

**Duplicate Settings classes (`config/__init__.py` vs `core/config.py`):**
- Issue: Two independent `Settings(BaseSettings)` classes exist — one in `src/anonreq/config/__init__.py` (primary, 225 lines, used by `main.py` and all modules) and another in `src/anonreq/core/config.py` (34 lines, minimal, also reads `ANONREQ_` prefix). The `core/config.py` version defines a separate `DeploymentMode` StrEnum and different fields.
- Files: `src/anonreq/config/__init__.py:27`, `src/anonreq/core/config.py:12`
- Impact: Confusion about which Settings is used; the `core/config.py` version may shadow or duplicate configuration. Both instantiate module-level `settings = Settings()`.
- Fix approach: Determine which is canonical (likely `config/__init__.py`), delete or merge `core/config.py`, and audit all imports.

**`governance/router.py` is a god-router (859 lines, 42 functions):**
- Issue: A single file handles governance CRUD, risk assessment, legal holds, supplier governance, DSAR workflows, breach notifications, and approvals across two routers.
- Files: `src/anonreq/governance/router.py`
- Impact: High cognitive load, merge conflicts, hard to test individual domains in isolation.
- Fix approach: Split into domain-specific routers (`governance/crud.py`, `governance/risk.py`, `governance/dsar.py`, `governance/breach.py`, `governance/approval.py`) and compose them in `main.py`.

**`models/governance.py` is a god-model (465 lines, 27+ classes):**
- Issue: Pydantic models, SQLAlchemy ORM models, enums, and validators for governance records, review cycles, risk assessments, model inventory, provider inventory, AML webhooks, and incident records all live in one file.
- Files: `src/anonreq/models/governance.py`
- Impact: Any governance model change touches a massive file; hard to find relevant classes.
- Fix approach: Split into `models/governance_records.py`, `models/governance_risk.py`, `models/governance_inventory.py`, `models/governance_incidents.py`.

**`AppState` is a god-object (50+ nullable fields):**
- Issue: `src/anonreq/state.py` defines an `AppState` dataclass with 50+ optional fields covering every subsystem. Every bootstrap function mutates it; every handler reads from it.
- Files: `src/anonreq/state.py:74-167`
- Impact: No type safety on field access order, easy to forget initialization, hard to test subsets of state.
- Fix approach: Consider subsystem-specific state containers (`PolicyState`, `AuditState`, etc.) with typed accessors, or use a registry pattern.

**`requirements-dev.txt` does not include all dev dependencies from `pyproject.toml`:**
- Issue: `requirements-dev.txt` includes `aiosqlite==0.22.1` but omits `hypothesis`, `respx`, `fakeredis`, `ruff`, and `mypy` which are in `pyproject.toml` `[project.optional-dependencies] dev`.
- Files: `requirements-dev.txt`, `pyproject.toml:62-70`
- Impact: Reproducible builds via `requirements-dev.txt` will be incomplete; `uv sync --all-extras` is required.
- Fix approach: Regenerate `requirements-dev.txt` from `pyproject.toml` or deprecate it in favor of `uv.lock`.

**`requirements.txt` includes `python-multipart` and `greenlet` not in `pyproject.toml`:**
- Issue: `requirements.txt` lists `python-multipart==0.0.20` and `greenlet==3.5.3` which are transitive dependencies not declared in `pyproject.toml` `[project] dependencies`.
- Files: `requirements.txt:21-22`, `pyproject.toml:23-43`
- Impact: Dependency list is inconsistent between the two files; `uv.lock` is the only reliable source of truth.
- Fix approach: Declare `python-multipart` explicitly in `pyproject.toml` (FastAPI needs it for form data); `greenlet` is likely a transitive dep of SQLAlchemy.

## Known Bugs

**CLAUDE.md incorrectly claims `sqlalchemy` is not declared in `pyproject.toml`:**
- Symptoms: CLAUDE.md line 55 states "`sqlalchemy` (and alembic) are imported by `main.py` and the audit services but are *not* declared in `pyproject.toml`".
- Files: `CLAUDE.md:55`, `pyproject.toml:38`
- Trigger: Anyone reading CLAUDE.md will believe sqlalchemy is undeclared, when it IS declared as `"sqlalchemy>=2.0.0"`.
- Workaround: This documentation bug is harmless but misleading. The REAL undeclared dependency is `alembic`.

**`alembic` CLI package is undeclared in all dependency manifests:**
- Symptoms: `alembic/env.py` imports `from alembic import context` but `alembic` is not in `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, or `uv.lock`.
- Files: `alembic/env.py:13`, `pyproject.toml` (missing)
- Trigger: Running `alembic upgrade head` in a fresh environment will fail with `ModuleNotFoundError`.
- Workaround: Install `alembic` manually or add it to `pyproject.toml` dev dependencies.

**STATE.md stale/conflicting (acknowledged by AGENTS.md):**
- Symptoms: AGENTS.md explicitly states "Some `.planning/STATE.md` body text is stale/conflicting." STATE.md says "Phase 31 of 32" with milestone v2.0, while AGENTS.md says phases are complete "through Phase 21 (plus 6.5 production-readiness checkpoint)".
- Files: `.planning/STATE.md`, `AGENTS.md:12-14`
- Trigger: Using STATE.md for planning decisions will produce incorrect phase context.
- Workaround: Prefer `ROADMAP.md` and phase-specific `.planning/phases/` directories for current state.

## Security Considerations

**`fail_open` configuration allows overriding fail-secure default:**
- Risk: `ANONREQ_PROXY_FAIL_OPEN` env var and `TopologyConfig.fail_open_policy` allow the transparent proxy to pass traffic on certificate pinning detection failure and firewall errors instead of blocking.
- Files: `src/anonreq/deployment/modes.py:41`, `src/anonreq/proxy/transparent_proxy.py:59-108`, `src/anonreq/firewall/pipeline.py:150`
- Current mitigation: Default is `False`; only applies to proxy/firewall layer, not the core API pipeline.
- Recommendations: Document this override prominently in deployment guides; consider adding an audit log entry when fail-open is active; add a metric to track fail-open passthrough events.

**Fire-and-forget async tasks without error handling:**
- Risk: `asyncio.create_task` and `asyncio.ensure_future` are used without storing references or adding exception callbacks in several places, meaning exceptions from these tasks are silently swallowed.
- Files: `src/anonreq/governance/router.py:97`, `src/anonreq/services/breach_detector.py:168`
- Current mitigation: Internal tasks only; failures are non-critical (audit events, webhook notifications).
- Recommendations: Store task references and add `add_done_callback` for exception logging; add structured logging for task failures.

**Dual Settings instantiation risk:**
- Risk: Both `config/__init__.py:200` and `core/config.py:34` instantiate `settings = Settings()` at import time. If `core/config.py` is imported instead of `config/__init__.py`, a different settings object with different fields will be used.
- Files: `src/anonreq/config/__init__.py:200`, `src/anonreq/core/config.py:34`
- Current mitigation: `main.py` imports from `config` package; `core/config.py` appears to be unused at runtime.
- Recommendations: Delete `core/config.py` or convert it to an internal module.

## Performance Bottlenecks

**`governance/router.py` sequential DB operations:**
- Problem: Multiple governance endpoints perform sequential database queries without connection pooling optimization.
- Files: `src/anonreq/governance/router.py` (various endpoints)
- Cause: Each endpoint opens a fresh session via `get_db()` dependency.
- Improvement path: Use `async_sessionmaker` with connection pooling (already initialized in `bootstrap/services.py`); consider batch queries for list endpoints.

**`models/governance.py` SQLAlchemy column definitions at import time:**
- Problem: `GovernanceRecordModel` and related ORM models define columns at class body level, which executes at import time.
- Files: `src/anonreq/models/governance.py:267-340`
- Cause: Standard SQLAlchemy pattern, but 27+ classes in one file means slow import.
- Improvement path: Split models into separate files; consider lazy initialization for rarely-used models.

## Fragile Areas

**Bootstrap sequence in `bootstrap/services.py` (484 lines, 12 sequential awaits):**
- Files: `src/anonreq/bootstrap/services.py`, `src/anonreq/main.py:295-305`
- Why fragile: 12 sequential async bootstrap calls during startup; any single failure aborts the entire startup. Order dependencies between bootstrap functions are implicit.
- Safe modification: Add explicit dependency declarations between bootstrap functions; test each bootstrap function in isolation.
- Test coverage: Only 4 test files touch bootstrap; no integration test for the full bootstrap sequence.

**Pipeline manager sequential execution:**
- Files: `src/anonreq/pipeline/manager.py`
- Why fragile: Stages execute strictly in registration order with early-abort on error; a misordered registration silently breaks the fail-secure invariant.
- Safe modification: Always add tests that verify stage ordering and error propagation.
- Test coverage: Well-tested via property tests in `tests/property/test_fail_secure.py`.

**Provider adapter translation layer:**
- Files: `src/anonreq/providers/anthropic.py` (428 lines), `src/anonreq/providers/gemini.py` (406 lines), `src/anonreq/providers/ollama.py` (351 lines)
- Why fragile: OpenAI-schema → provider-specific translation involves complex nested dict manipulation; edge cases in tool_calls, streaming, and image content are high-risk.
- Safe modification: Test against real provider API response samples; property test round-trip correctness.
- Test coverage: Only 1 test file (`tests/unit/providers/`) for 8 source files.

## Scaling Limits

**Module count (60 subpackages under `src/anonreq/`):**
- Current capacity: 52,731 total lines across 60 subpackages.
- Limit: Import time grows linearly with module count; startup time may exceed acceptable thresholds.
- Scaling path: Consider lazy imports for rarely-used enterprise modules (CASB, RAG, multimodal, voice, endpoint); profile startup time.

**`AppState` field count (50+ fields):**
- Current capacity: Works for current feature set.
- Limit: Adding more subsystems will make the dataclass unwieldy; IDE autocompletion degrades.
- Scaling path: Transition to typed subsystem containers.

## Dependencies at Risk

**`presidio-analyzer` version drift:**
- Risk: `pyproject.toml` declares `>=2.2.35` but `requirements.txt` pins `2.2.363`. Presidio is a critical PII detection dependency; breaking API changes between versions could silently break detection.
- Impact: Core anonymization pipeline depends on Presidio for NER detection.
- Migration plan: Pin to exact version in `pyproject.toml`; add integration tests that validate Presidio response format.

**Optional dependencies (`minio`, `pyarrow`, `reportlab`, `onnxruntime`, `whisper`) are fragile:**
- Risk: These are imported conditionally with `# type: ignore[import-not-found]` and bare `try/except ImportError` blocks. Silent degradation if installed versions are incompatible.
- Files: `src/anonreq/rag/vector_connector.py:115,198,249`, `src/anonreq/voice/stt.py:6-7`, `src/anonreq/services/audit_exporter.py:326`
- Impact: Compliance exports, RAG governance, and voice features may silently fail.
- Migration plan: Add version compatibility checks at import time; log warnings when optional deps are missing.

## Missing Critical Features

**No linter/formatter enforced in CI:**
- Problem: CLAUDE.md explicitly states "No linter/formatter is configured in this repo" despite `ruff` and `mypy` being declared as dev dependencies in `pyproject.toml`. There are 100+ `# noqa` directives and 23 `# type: ignore` directives.
- Blocks: Consistent code style across contributors; preventing accidental regressions in type safety.

**No `alembic` dependency declared:**
- Problem: Alembic migrations are a production requirement for PostgreSQL governance tables, but `alembic` package is not in any dependency file.
- Blocks: Clean deployment from fresh install; CI/CD migration pipelines.

## Test Coverage Gaps

**`src/anonreq/core/` — 1 source file, 0 test files:**
- What's not tested: `core/config.py` Settings class (though it may be dead code).
- Files: `src/anonreq/core/config.py`
- Risk: Low (likely unused), but contributes to confusion about canonical config.
- Priority: Low

**`src/anonreq/deployment/` — 2 source files, 0 test files:**
- What's not tested: `deployment/modes.py` — `DeploymentMode`, `TopologyConfig`, `get_deployment_config()`, and `mode_from_env()`.
- Files: `src/anonreq/deployment/modes.py`
- Risk: Medium — deployment mode selection affects which pipeline stages run; incorrect mode could bypass anonymization.
- Priority: Medium

**`src/anonreq/incidents/` — 2 source files, 0 test files:**
- What's not tested: `incidents/classification.py` — `IncidentClassifier` with severity/type mapping and response time SLAs.
- Files: `src/anonreq/incidents/classification.py`
- Risk: Low — used for incident response routing, not core anonymization.
- Priority: Low

**`src/anonreq/multimodal/` — 8 source files, 1 test file:**
- What's not tested: `dispatcher.py`, `json_analyzer.py`, `multipart_analyzer.py`, `tool_call.py`, `image_scanner.py`, `pdf_scanner.py`, `audio_scanner.py`, `video_scanner.py`.
- Files: `src/anonreq/multimodal/*.py`
- Risk: Medium — multimodal scanning handles PII in non-text content; untested scanners could leak data.
- Priority: Medium

**`src/anonreq/routing/` — 4 source files, 1 test file:**
- What's not tested: `alias_registry.py`, `model_registry.py`, `route_selector.py` (only `chat.py` has direct tests).
- Files: `src/anonreq/routing/*.py`
- Risk: Medium — model alias resolution affects provider routing; incorrect aliases could send data to wrong providers.
- Priority: Medium

**`src/anonreq/services/` — 24 source files, 1 test file:**
- What's not tested: 23 of 24 service modules including `audit_chain.py`, `audit_exporter.py`, `dlp_engine.py`, `oversight.py`, `slo_engine.py`, `breach_detector.py`, `notifications.py`, `retention.py`.
- Files: `src/anonreq/services/*.py`
- Risk: High — these implement core compliance, audit, DLP, and breach response functionality.
- Priority: High

**`src/anonreq/voice/` — 11 source files, well-tested (28 test files):**
- Status: Good coverage. Noted for completeness.
- Files: `src/anonreq/voice/*.py`, `tests/*voice*.py`

**`src/anonreq/middleware/` — 9 source files, 1 unit test file:**
- What's not tested: `classification.py`, `content_type.py`, `firewall_inbound.py`, `firewall_outbound.py`, `policy.py`, `rbac.py`, `response_headers.py` (only `mtls.py` has a unit test).
- Files: `src/anonreq/middleware/*.py`
- Risk: High — middleware is the enforcement boundary; untested middleware could allow unauthorized or unsanitized requests through.
- Priority: High

## Configuration Drift

**`.env.example` missing settings from `config/__init__.py`:**
- Issue: `.env.example` does not document `ANONREQ_SECRET_BACKEND`, `ANONREQ_SECRET_BACKEND_PATH`, `ANONREQ_SECRET_VOLUME_DIR`, `ANONREQ_SECRET_VOLUME_FILE`, `ANONREQ_OIDC_*`, `ANONREQ_MTLS_*`, `ANONREQ_LICENSE_*`, `ANONREQ_ADMIN_API_KEY`, `ANONREQ_ADMIN_ROLE`, `ANONREQ_PROXY_MODE`, `ANONREQ_CA_DIR` (the last two are documented but with different defaults).
- Files: `.env.example`, `src/anonreq/config/__init__.py:136-181`
- Impact: Operators deploying from `.env.example` will not know about OIDC, mTLS, license, or secret backend configuration.
- Fix approach: Update `.env.example` to include all non-secret settings with their defaults and descriptions.

**`alembic.ini` has empty `sqlalchemy.url`:**
- Issue: `alembic.ini:4` has `sqlalchemy.url =` (empty). The URL is dynamically set in `alembic/env.py:25` from `settings.DATABASE_URL`, but the empty ini value is confusing and may cause issues with some Alembic CLI commands.
- Files: `alembic.ini:4`, `alembic/env.py:25`
- Impact: Low — `env.py` overrides it at runtime.
- Fix approach: Add a comment in `alembic.ini` noting the URL is overridden by `env.py`.

## Architectural Risks

**Tight coupling between `bootstrap/services.py` and all subsystems:**
- Files: `src/anonreq/bootstrap/services.py`
- Risk: Every new subsystem requires a new `bootstrap_*` function here, making it the single point of change for all initialization.
- Mitigation: Already using `TYPE_CHECKING` imports in `state.py` to avoid circular imports; bootstrap functions use late imports.

**`state.py` TYPE_CHECKING imports span 40+ modules:**
- Files: `src/anonreq/state.py:18-70`
- Risk: Adding a new module requires updating `state.py` TYPE_CHECKING block. Missing entries cause runtime errors when `AppState` fields are accessed.
- Mitigation: Tests that exercise `get_app_state()` with all field types.

**`noqa` directive proliferation (100+ occurrences):**
- Files: Various across `src/anonreq/`
- Risk: Suppressed lint rules may mask real issues (unused args, long lines, incorrect overrides).
- Breakdown: `E501` (line length) dominates at ~40 occurrences; `B904` (raise without from) has 6; `ARG002/ARG004` (unused args) has 4; `RUF006` (fire-and-forget) has 2.
- Fix approach: Refactor long lines rather than suppressing; add `from e` to `raise` statements; use `_` prefix for intentionally unused args.

## Documentation Gaps

**CLAUDE.md contains incorrect claim about sqlalchemy:**
- Issue: CLAUDE.md:55 says sqlalchemy is "not declared in `pyproject.toml`" but it IS declared at `pyproject.toml:38`.
- Files: `CLAUDE.md:55`
- Impact: Developers may add duplicate dependency declarations or misunderstand the dependency situation.
- Fix approach: Correct CLAUDE.md to state that `alembic` (not `sqlalchemy`) is the undeclared dependency.

**No architecture documentation beyond CLAUDE.md/AGENTS.md:**
- Issue: `docs/` directory exists but no generated or maintained architecture diagram or component responsibility map.
- Files: `docs/` (exists but not audited for architecture docs)
- Impact: New contributors must read source to understand component boundaries.
- Fix approach: Generate architecture docs from codebase analysis or maintain ADRs.

## Performance Concerns

**`governance/router.py` creates async tasks without tracking:**
- Problem: `asyncio.ensure_future(_emit())` at line 97 creates a task without storing the reference; if the task raises, the exception is lost.
- Files: `src/anonreq/governance/router.py:97`
- Impact: Audit event emission failures are silently ignored.
- Fix approach: Store task reference and add `add_done_callback` for logging.

**`services/breach_detector.py` fire-and-forget webhook:**
- Problem: `asyncio.create_task(self._fire_webhook(event))` at line 168 creates an untracked task.
- Files: `src/anonreq/services/breach_detector.py:168`
- Impact: Webhook delivery failures are silently lost; no retry mechanism visible.
- Fix approach: Store task reference; add retry logic or use a task queue.

---

*Concerns audit: 2026-07-18*
