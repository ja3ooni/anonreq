# Coding Conventions

**Analysis Date:** 2026-07-18

## Naming Patterns

**Files:**
- Snake_case for all Python modules: `processing_context.py`, `span_arbiter.py`, `classifier.py`
- One primary class per file; file named after that class in snake_case
- Test files: `test_<module>.py` for unit tests at `tests/` root, `test_<feature>.py` inside domain test subdirectories
- Config files: YAML with lowercase kebab-case: `enterprise-policy.yaml`, `mnpi_recognizers.yaml`

**Functions:**
- snake_case: `verify_api_key()`, `build_pipeline()`, `load_provider_registry()`
- Private/internal helpers prefixed with underscore: `_extract_request_id()`, `_make_error_body()`, `_find_stage_by_name()`
- Boolean-returning functions use `is_`/`has_` prefix: `has_errors()`

**Classes:**
- PascalCase: `PipelineManager`, `ClassificationEngine`, `SpanArbiter`, `TailBuffer`
- Abstract base classes use `ABC` suffix implicitly via inheritance: `PipelineStage(ABC)`
- Pydantic models: `ChatRequest`, `ProcessingContext`, `ClassificationResult`
- Enums: `StrEnum` or `Enum` with UPPER_CASE values: `FailureMode`, `ClassificationAction`

**Variables:**
- snake_case: `token_mappings`, `text_nodes`, `entity_counts`
- Constants: UPPER_SNAKE_CASE: `MAX_EXAMPLES`, `TOKEN_PATTERN`, `ACTION_PRECEDENCE`, `ALLOWLIST`
- Module-level singletons: lowercase: `settings = Settings()`, `security = HTTPBearer(auto_error=True)`

**Type Hints:**
- Python 3.12 union syntax: `str | None`, `dict[str, Any]`, `list[dict[str, Any]]`
- Never use `Optional[]` or `Union[]` — always use `X | None` and `X | Y`
- Type annotations on all function signatures (required by mypy strict)

## Code Style

**Formatting:**
- Ruff 0.15+ with `line-length = 100`, `target-version = "py312"`
- Config: `pyproject.toml [tool.ruff]`
- Enabled rule sets: `E`, `F`, `I`, `N`, `W`, `UP`, `B`, `SIM`, `ARG`, `PT`, `RUF`
- `B008` ignored (allows `Depends()` in function signatures — FastAPI pattern)

**Linting:**
- Ruff for linting and import sorting
- mypy strict mode enabled with `pydantic.mypy` and `sqlalchemy.ext.mypy.plugin`
- `# noqa: E501` used sparingly for intentionally long lines (YAML field descriptions, strategy definitions)
- `# noqa: RUF002` used on docstrings containing Unicode characters (e.g., `2⁻³²`)

**Import Organization:**
- `from __future__ import annotations` at top of every module (enables `X | None` syntax at runtime)
- stdlib first, then third-party, then `anonreq.*`, then `tests.*`
- Sorted by isort (Ruff `I` rules)
- Lazy imports inside functions/fixtures to avoid slow test collection: `from fastapi import FastAPI` inside fixture body

**Path Aliases:**
- None. All imports use full `anonreq.*` paths from `src/` root (configured via `pythonpath = ["src"]` in `pyproject.toml`)

## Type Hints

**Strictness:**
- mypy `strict = true` globally (`pyproject.toml [tool.mypy]`)
- `show_error_codes = true` for actionable error output
- Plugins: `pydantic.mypy`, `sqlalchemy.ext.mypy.plugin`
- Missing import stubs suppressed via `[[tool.mypy.overrides]]` for third-party packages (fastapi, pydantic, sqlalchemy, httpx, structlog, etc.)

**Pydantic Models:**
- All API models use `model_config = {"extra": "ignore"}` for forward compatibility with OpenAI API changes
- `Field()` with `min_length`, `validation_alias`, `description` used for validation and env var mapping
- `field_validator` for custom validation: `validate_api_key_length`
- Settings use `pydantic-settings` v2 with `BaseSettings` and `SettingsConfigDict(env_prefix="ANONREQ_")`

**Dataclasses:**
- `ProcessingContext` and `RequestContext` use stdlib `@dataclass` (not Pydantic) for internal state containers
- Typed with `Any` for fields that vary by stage (e.g., `audit_metadata: dict[str, Any]`)
- `field(default_factory=dict)` and `field(default_factory=list)` for mutable defaults

## Error Handling

**Exception Hierarchy:**
```text
AnonReqError (base)
├── DependencyUnavailableError (503)
├── PipelineAbortError (500)
│   ├── PipelineBlockedError (451)
│   └── OutboundDLPError (451)
└── AuthenticationError (401)
```

**Fail-Secure Pattern:**
- Every exception returns an OpenAI-compatible error envelope: `{"error": {"message": str, "type": str, "code": str, "request_id": str}}`
- `global_exception_handler` catches all unhandled exceptions and returns generic 500 with no internals
- `ctx.fail_secure(error)` is the canonical pipeline abort mechanism — appends error to `ctx.errors`, checked by `has_errors()` before each stage
- No stack traces, request bodies, header content, env var values, file paths, or dependency URLs in error responses
- Request IDs propagated through error envelopes for trace correlation

**Error Propagation:**
- Pipeline stages raise `PipelineAbortError` or call `ctx.fail_secure()`
- `PipelineManager.run()` catches all exceptions per stage, records via `ctx.fail_secure()`, and breaks
- Global handler formats `AnonReqError` subclasses with structured body; everything else gets generic 500

**File:** `src/anonreq/exceptions.py`

## Logging

**Framework:** `structlog` with stdlib integration and JSON rendering

**Field Allowlist:**
- Strict allowlist (`ALLOWLIST` frozenset) in `src/anonreq/logging_config.py`
- ~85 allowed field names covering metadata only (request_id, status_code, duration_ms, entity_counts, etc.)
- Non-allowlisted fields silently dropped by `allowlist_processor`
- Secret redaction via `redact_secret_substrings_processor` (regex-based, handles `sk-*`, `Bearer *`, `api_key=*` patterns)

**What Gets Logged:**
- Pipeline stage start/complete/failed events: `"pipeline.stage.start"`, `"pipeline.stage.complete"`
- Error events with `error_type` and `request_id`
- Audit metadata (decision IDs, matched rules, compliance presets, locale)
- Prometheus metrics via `prometheus-client` counters

**What NEVER Gets Logged:**
- Raw request/response bodies
- Raw PII entity values
- Token mappings
- API keys or secrets
- Internal URLs or file paths

**Logger Pattern:**
```python
from structlog import get_logger
logger = get_logger("anonreq.pipeline")
logger.info("pipeline.stage.start", stage=stage.name, request_id=ctx.request_id)
```

**File:** `src/anonreq/logging_config.py`

## Configuration Patterns

**Settings Loading:**
- `pydantic-settings` `BaseSettings` with `SettingsConfigDict(env_prefix="ANONREQ_", extra="ignore")`
- Module-level singleton: `settings = Settings()` — instantiated at import time (fail-secure startup)
- Required vars validated at import: `API_KEY` (min 32 chars), `VALKEY_URL`, `PRESIDIO_URL`
- Optional vars have documented defaults: `HOST="0.0.0.0"`, `PORT=8080`, `LOG_LEVEL="INFO"`

**YAML Configuration:**
- External config in `config/` directory: policies, providers, locales, compliance, DLP, SLO, fairness
- Loaded via `yaml.safe_load()` to prevent code injection
- Hot-reloadable via `watchdog` for some config files

**Environment Variables:**
- All prefixed with `ANONREQ_`
- `.env` file supported (for local dev only)
- Required vars set via `os.environ.setdefault()` in test `conftest.py` before any Settings import

**File:** `src/anonreq/config/__init__.py`

## Module Organization

**Package Structure:**
- `src/anonreq/` root package with `src/` layout (setuptools `packages.find where=["src"]`)
- Domain-specific subpackages: `pipeline/`, `detection/`, `tokenization/`, `cache/`, `policy/`, `governance/`, etc.
- Each subpackage has `__init__.py` with exports and docstrings
- Flat module layout within subpackages (no deep nesting beyond 2 levels)

**`__init__.py` Pattern:**
- Re-exports public API: `models/__init__.py` imports all model classes and defines `__all__`
- Subpackage `__init__.py` provides convenience imports
- Not all subpackages have `__init__.py` re-exports — some rely on explicit imports

**Key Structural Patterns:**
- `config/` — application settings (singleton)
- `core/` — deployment-mode-specific settings
- `models/` — Pydantic models and dataclasses
- `pipeline/` — sequential stage execution (base class + manager + concrete stages)
- `routes/` and `api/` — FastAPI routers
- `middleware/` — ASGI middleware (classification, firewall, RBAC, mTLS, response headers)
- `services/` — cross-cutting service implementations

**File:** `src/anonreq/` directory structure

## Async Patterns

**async/await:**
- All route handlers are `async def`
- Pipeline stages use `async def execute(self, ctx: ProcessingContext) -> ProcessingContext`
- Cache operations use `fakeredis.aioredis` (async) in tests, `redis.asyncio` in production
- Database operations use `SQLAlchemy` async (`asyncpg`/`aiosqlite`)

**Async Context Managers:**
- `inject_failure()` in tests uses `@contextlib.asynccontextmanager` for failure injection with cleanup
- `httpx.AsyncClient` used with `async with` for test HTTP clients
- `ASGITransport` for testing FastAPI apps without a running server

**pytest-asyncio:**
- `asyncio_mode = "auto"` — all async test functions run automatically without `@pytest.mark.asyncio`
- Exception: `@pytest.mark.asyncio` used explicitly in some property tests inside classes (class-scoped)

**Async Fixtures:**
- `@pytest_asyncio.fixture` for async fixtures that need `await`
- `async def cache_manager()` yields after `await fake_redis.aclose()` teardown

## API Design

**Router Organization:**
- Feature-specific routers: `admin_router`, `chat_router`, `governance_router`, etc.
- Routers included in main app via `app.include_router()`
- Dependencies injected at router level: `dependencies=[Depends(auth_context)]`

**Response Models:**
- OpenAI-compatible wire format: `ChatCompletionResponse`, `ChatCompletionChoice`
- Error responses: `{"error": {"message", "type", "code", "request_id"}}`
- `model_config = {"extra": "ignore"}` on all API models for forward compatibility

**Dependency Injection:**
- `HTTPBearer(auto_error=True)` for auth extraction
- `Depends(verify_api_key)` for API key validation
- `Depends(get_request_context)` for request context population
- `Depends(auth_context)` as composite dependency (auth + context)
- Route handlers receive `RequestContext` via dependency injection

**File:** `src/anonreq/dependencies.py`

## Documentation

**Docstring Style:**
- Google-style docstrings with `Args:`, `Returns:`, `Raises:` sections
- Module-level docstrings describe purpose, design references (e.g., "Per D-22 through D-28")
- Threat model coverage documented in module docstrings (e.g., "Threat model coverage: T-01-03-01")
- Class docstrings include `Attributes:` sections with field descriptions
- `"""Triple-quoted"""` for all docstrings

**Inline Comments:**
- Design decision rationale in comments: `# Per D-24: conditions are ANDed`
- `# noqa: E501` for intentionally long lines
- `# type: ignore[...]` used sparingly with specific ignore codes

**Comment Style:**
- Block comments explain "why", not "what"
- Section dividers with `# ──── Section Name ────────` visual separators
- TODO/FIXME usage minimal; mostly references to requirement IDs (D-XX, REQ-XX)

## File Naming

**Source Files:**
- `snake_case.py`: `processing_context.py`, `span_arbiter.py`, `tail_buffer.py`
- `__init__.py` for package directories
- `__about__.py` for version info

**Test Files:**
- `test_<module>.py` at `tests/` root for legacy/flat tests
- `tests/unit/<domain>/test_<module>.py` for structured unit tests
- `tests/integration/test_<feature>.py` for integration tests
- `tests/property/test_<invariant>.py` for property-based tests
- `tests/load/test_<scenario>.py` for load tests
- `tests/firewall/`, `tests/policy/`, `tests/multimodal/` etc. for domain test directories
- `conftest.py` at `tests/`, `tests/property/`, `tests/unit/providers/` levels

**Config Files:**
- YAML with descriptive names: `enterprise-policy.yaml`, `financial_crime_words.yaml`, `prompt-security-rules.yaml`
- Locale configs in `config/locales/` with BCP 47 codes: `en.yaml`, `fr-FR.yaml`, `pt-BR.yaml`
- Compliance presets in `config/compliance/`: `gdpr.yaml`, `lgpd.yaml`

---

*Convention analysis: 2026-07-18*
