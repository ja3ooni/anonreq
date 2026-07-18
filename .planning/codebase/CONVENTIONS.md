# Coding Conventions

**Analysis Date:** 2026-07-17

## Naming Patterns

**Files:**
- `snake_case.py` for all Python modules (e.g., `regex_detector.py`, `presidio_client.py`, `tail_buffer.py`)
- Test files: `test_{module_name}.py` for unit tests (e.g., `test_detection.py`, `test_tail_buffer.py`)
- Property test files: `test_{domain}_invariants.py` or `test_{feature}.py` in `tests/property/` (e.g., `test_locale_invariants.py`, `test_fail_secure.py`)
- Integration test files: `test_{feature}.py` in `tests/integration/` (e.g., `test_e2e_round_trip.py`)
- YAML config files: `snake_case.yaml` (e.g., `mnpi_recognizers.yaml`, `financial_crime_words.yaml`)

**Functions:**
- `snake_case` for all function and method names (e.g., `luhn_checksum()`, `find_high_risk_word_positions()`, `_extract_request_id()`)
- Private functions prefixed with single underscore: `_make_error_body()`, `_negotiate_and_merge()`, `_parse_topology()`
- Async functions use `async def` with no special naming prefix beyond `snake_case`
- Bootstrap functions follow `bootstrap_{domain}()` naming: `bootstrap_locale_detection()`, `bootstrap_policy_engine()`, `bootstrap_soc_services()`
- Helper functions in tests use descriptive `snake_case`: `make_delta()`, `collect()`, `_ai_request()`, `_build_pipeline()`, `_make_proc_ctx()`

**Variables:**
- `snake_case` for all variables (e.g., `request_id`, `entity_type`, `raw_pii`)
- Module-level constants: `UPPER_SNAKE_CASE` (e.g., `ENTITY_SPECIFICITY`, `TIER_1_ENTITIES`, `MAX_EXAMPLES`, `_LUHN_VALIDATED`, `_RETRY_STOP_SECONDS`)
- Type-annotated throughout with `variable: Type = value` style
- Short-lived variables use brief but clear names: `rid`, `det`, `ex`

**Types:**
- Type annotations via `from __future__ import annotations` at top of every module (288 of 349 source modules)
- Custom types defined with `type` alias or imported from `typing`
- `Any` used sparingly, mostly in generic dict return types and fixture declarations
- Complex types use `list[dict[str, Any]]` rather than `List[Dict[str, Any]]` (Python 3.12 style)
- `re.Pattern` quoted in forward-reference style when used in class attributes: `dict[str, "re.Pattern"]`

**Classes:**
- `PascalCase` for all classes (e.g., `RegexDetector`, `ExclusionList`, `ContextBooster`, `PresidioClient`, `TailBuffer`)
- Exception classes: `PascalCase` with `Error` suffix (e.g., `PresidioTimeoutError`, `PipelineAbortError`, `DependencyUnavailableError`)
- Dataclass pattern: `@dataclass(frozen=True)` for immutable value objects (e.g., `_ParsedTopology`, `SecretSnapshot`, locale `EntityType`), `@dataclass` for mutable state containers (e.g., `AppState` in `src/anonreq/state.py`)
- Protocol classes for dependency contracts (e.g., `SecretSource` in `src/anonreq/secrets/store.py`)
- `@dataclass(slots=True)` for performance-critical classes (e.g., `JWKSCache`, `OIDCVerifier` in `src/anonreq/auth/oidc.py`)

## Code Style

**Formatting:**
- No formatter is configured in the repository (per CLAUDE.md: "No linter/formatter is configured in this repo")
- Code is hand-formatted with consistent 4-space indentation
- Line lengths vary but generally stay under 100 characters
- `# noqa: E501` used for lines that exceed 100 chars (e.g., `src/anonreq/config/__init__.py:74`)
- Blank lines: two between top-level definitions, one between methods in a class, one around section-comment blocks

**Linting:**
- Ruff is configured in `pyproject.toml`: target Python 3.12, line-length 100
- Ruff rule selection: `["E", "F", "I", "N", "W", "UP", "B", "SIM", "ARG", "PT", "RUF"]` with `ignore = ["B008"]`
- Ruff and mypy configured in `pyproject.toml` (Phase 23 engineering hygiene)
- `.ruff_cache/` and `.mypy_cache/` in `.gitignore`
- mypy configured with `strict = true`, `python_version = "3.12"`, plugins for pydantic and sqlalchemy
- `# type: ignore[union-attr]` and `# type: ignore[method-assign]` used inline for type-checker overrides
- `# noqa: F811` used in a single place for structlog re-import in `exceptions.py`
- 52 ruff lint issues fixed in commit `ada5d1e`

## Import Organization

**Order:**
1. `from __future__ import annotations` — first import in every module
2. Standard library modules (`re`, `typing`, `pathlib`, `enum`, `asyncio`, `json`, `logging`, `hmac`, `contextlib`)
3. Third-party packages (`pytest`, `hypothesis`, `yaml`, `httpx`, `structlog`, `fastapi`, `redis.asyncio`, `sqlalchemy`, `cryptography`)
4. Local application imports (`from anonreq.detection.regex_detector import RegexDetector`)
5. Test imports from `tests.` package (in test files): `from tests.property.conftest import inject_failure`

**Path Aliases:**
- No custom path aliases or `PYTHONPATH` manipulation in source code
- `pyproject.toml` sets `pythonpath = ["src"]` for pytest, so imports are `from anonreq.xxx import YYY`
- Test package imports use `from tests.conftest import ...` and `from tests.property.strategies import ...`

**Imports within Type Annotations:**
- `TYPE_CHECKING` guards are used in newer modules (e.g., `src/anonreq/state.py`, `src/anonreq/cache/health.py`, `src/anonreq/pipeline/detection.py`, `src/anonreq/secrets/reloader.py`, `src/anonreq/providers/adapter.py`, `src/anonreq/governance/forwarding_guard.py`, `src/anonreq/detection/provider.py`)
- Older modules import types directly without `TYPE_CHECKING` guard
- Forward references using string literals for self-referential types: `"ExclusionList"`, `"re.Pattern"`

**Lazy Imports:**
- Used in conftest files to avoid slow test collection (~40-180s overhead avoided)
- Used in bootstrap functions for optional dependencies (e.g., `src/anonreq/bootstrap/services.py` lazily imports detection, policy, audit, etc.)
```python
@pytest.fixture
def app():
    from fastapi import FastAPI
    return FastAPI()
```

## Error Handling

**Patterns:**
- Custom exception hierarchy rooted at `AnonReqError` in `src/anonreq/exceptions.py`:
  - `DependencyUnavailableError` (503) — dependency unreachable
  - `PipelineAbortError` (500) — pipeline execution aborted
  - `PipelineBlockedError` (451) — DLP/DND policy block
  - `OutboundDLPError` (451) — outbound DLP violation
  - `AuthenticationError` (401) — invalid API key
- Global exception handler `global_exception_handler()` catches all unhandled exceptions and returns OpenAI-compatible error envelopes
- `http_exception_handler()` handles FastAPI `HTTPException` specifically
- Fail-secure principle: any pipeline error → HTTP 5xx, never forward unsanitized data
- Error bodies include `message`, `type`, `code`, `request_id` — no stack traces, no internal details
- Pipeline errors propagate via `ctx.fail_secure()` pattern in `ProcessingContext`
- Guard pattern for fail-secure at pipeline stage boundaries:
```python
async def fail_execute(ctx: Any) -> Any:
    ctx.fail_secure(
        PipelineAbortError(status_code=500, message="Detection stage failed", ...)
    )
    return ctx
```
- Provider error messages are generic (no internal details leaked) — security fix applied 2026-07-17 (`src/anonreq/pipeline/provider.py`)

**Timing-Safe Comparisons:**
- `hmac.compare_digest()` used for all API key comparisons (security fix applied 2026-07-17):
  - `src/anonreq/dependencies.py:69` — main API key verification
  - `src/anonreq/admin/auth.py:71` — admin API key verification
  - `src/anonreq/services/lineage.py` — lineage verification
  - `src/anonreq/license/validator.py` — license key verification

**Bootstrap Error Handling:**
- Domain bootstrap functions (`src/anonreq/bootstrap/services.py`) catch exceptions, log with `log.error()` + `exc_info=True`, close dependencies, then re-raise
- Lifespan startup aborts on any bootstrap failure (fail-secure)
```python
async def bootstrap_policy_engine(app: FastAPI, cache_manager: Any) -> None:
    try:
        # ... initialization ...
        log.info("Policy engine initialised", component="lifespan")
    except Exception:
        log.error("Failed to initialise policy engine", component="lifespan", exc_info=True)
        await cache_manager.close()
        raise
```

**Pattern for exception classes:**
```python
class DependencyUnavailableError(AnonReqError):
    def __init__(self, dependency: str, request_id: str | None = None) -> None:
        self.dependency = dependency
        super().__init__(
            message=f"{dependency} unavailable",
            error_type="service_unavailable",
            status_code=503,
            code="dependency_unavailable",
            request_id=request_id,
        )
```

## Logging

**Framework:** `structlog` for structured JSON logging

**Loggers:**
- Module-level logger via `log = get_logger()` (structlog) — preferred for newer modules
- Module-level logger via `logger = logging.getLogger(__name__)` — used in older modules
- `structlog.get_logger("anonreq.module.name")` with explicit component names for some modules
- In pipeline code, `structlog.contextvars.bind_contextvars(request_id=...)` ties logs to requests

**Patterns:**
```python
log.info("AnonReq starting in %s mode", active_mode.value,
         component="lifespan", mode=active_mode.value)
logger.warning("MNPI config not found; MNPI detection disabled",
               extra={"config_path": config_path})
logger.exception("Failed to load MNPI recognizers")
```

- `extra={...}` for structured context with stdlib logging
- `component` field to identify the origin within the application (used extensively: `"lifespan"`, `"health_check"`, `"startup_checks"`, `"policy_middleware"`, etc.)
- Structured fields use `snake_case` keys: `request_id`, `cache_health`, `failure_type`
- No PII values ever logged — field allowlist enforced by `logging_config.py`
- ALLOWLIST expanded (2026-07-17) to include fields actually used: `path`, `tenant_id`, `content_type`, `elapsed_ms`, `count`, `attempt`, `bucket`, `extra`, `file_name`, `max_locales`, `part_name`, `data`, `ttl`, `error`, `mode`, `version`, `component`, `deployment_mode`

## Comments

**When to Comment:**
- Module-level docstrings describe purpose, requirements cross-references (e.g., "Per D-38", "Per Phase 15"), and threat model coverage
- Class docstrings with `Usage::` examples showing code snippets
- Method docstrings follow Google-style with `Args:`, `Returns:`, `Raises:` sections
- Section comments in test files: horizontal rules (`# ----`) to separate test groups
- Inline comments only for non-obvious logic (e.g., Luhn validation, de-duplication strategy)
- Requirement/ticket references throughout: `# Per D-32, D-34`, `# Phase 17: MITM proxy setup`, `# Plan 13-04, Task 2`
- Design decisions documented with `# Design decisions:` prefix

**Docstring Patterns:**
- Not applicable (Python project)
- Docstrings use triple double-quotes `"""..."""` throughout
- Google-style docstring format with explicit `Args:` / `Returns:` / `Raises:` sections

**Example docstring pattern:**
```python
def detect(self, text: str) -> list[dict[str, Any]]:
    """Run all patterns on the given text and return detections.

    Args:
        text: The text to scan for PII.

    Returns:
        List of detection dicts, each with:
        - ``entity_type``: The type of detected entity.
        - ``start``: Character offset where the entity starts.
        - ``end``: Character offset where the entity ends.
        - ``score``: Always ``1.0`` for regex detections (D-38).
        - ``source``: Always ``"regex"`` (D-39).
    """
```

## Function Design

**Size:**
- Most functions are 10-50 lines
- Helper/pure functions are under 20 lines
- `create_app()` in `main.py` is 465 lines (reduced from 672) — decomposed via bootstrap pattern
- Bootstrap functions in `src/anonreq/bootstrap/services.py` are 30-80 lines each
- Test helper functions are typically 3-10 lines
- Property test functions are 15-40 lines

**Parameters:**
- 0-3 parameters preferred; 4+ used only for configuration objects
- Optional parameters use `| None = None` pattern with `if x is not None` guards
- Default values provided for configurable behavior (e.g., `config_path`, `timeout`, `max_concurrency`)
- `draw` parameter in `@st.composite` strategies: `def my_strategy(draw: Any) -> ...`

**Return Values:**
- List returns: empty list `[]` for no results, never `None` (e.g., `return []` when no detections)
- Dict returns: typed with `dict[str, Any]` for flexible detection schemas
- Bool returns for predicates: `is_excluded()`, `is_mcp()`, `is_within_proximity()`
- None returns used sparingly: `test_known_provider_detected_consistently` checks `result is not None`
- Context manager returns via `@contextlib.asynccontextmanager` with `yield`

## Module Design

**Exports:**
- `__init__.py` files re-export key classes with `__all__` lists
- Internal implementation details not re-exported
- Pattern in `__init__.py`:
```python
from anonreq.detection.regex_detector import RegexDetector
from anonreq.detection.regex_patterns import PATTERNS, luhn_checksum, ENTITY_SPECIFICITY

__all__ = [
    "RegexDetector",
    "PATTERNS",
    "luhn_checksum",
    "ENTITY_SPECIFICITY",
]
```

**Barrel Files:**
- Package-level `__init__.py` files serve as barrel exports for public API
- `tests/__init__.py` is empty (marker file)
- `tests/property/conftest.py` contains shared fixtures, not re-exported through `__init__`

**Module docstrings:**
- Every module has a docstring describing purpose, cross-referencing requirements
- Includes references to specific requirement IDs (e.g., D-32, D-38, TOKN-01)
- Threat model references for security-relevant code: `# Threat model: T-13-02-01`
- Design note comments for non-obvious decisions:
```
# Design decisions:
# - @given tests use suppress_health_check=[HealthCheck.function_scoped_fixture]
```

## Type Annotations

- 100% of function signatures include type annotations
- Return type `-> None` on all void functions/methods
- `list[dict[str, Any]]` is the most common complex type (used for detection results)
- `from __future__ import annotations` enables PEP 604 style (using `|` instead of `Union`)
- `str | None` used instead of `Optional[str]`
- `Any` used in test fixtures where exact types would create circular dependencies
- `TYPE_CHECKING` guard pattern used in newer modules to avoid circular imports (`src/anonreq/state.py`, `src/anonreq/cache/health.py`, `src/anonreq/pipeline/detection.py`, etc.)

## Application State Pattern

**Typed AppState (introduced post-Phase 27):**
- `src/anonreq/state.py` defines `AppState` dataclass with typed fields for every attribute stored on `app.state`
- `get_app_state(app)` helper returns typed `AppState` (lazy initialization)
- Bootstrap functions in `src/anonreq/bootstrap/services.py` populate `AppState` fields during lifespan startup
- Route handlers and middleware access state via `get_app_state(request.app)` or `get_app_state(app)`
- Pattern:
```python
from anonreq.state import get_app_state

async def some_route(request: Request) -> Response:
    state = get_app_state(request.app)
    cache_manager = state.cache_manager
    pdp = state.pdp
```

**Bootstrap Decomposition:**
- `src/anonreq/bootstrap/services.py` contains domain-specific bootstrap functions:
  - `bootstrap_locale_detection()` — locale, Presidio, detection pipeline
  - `bootstrap_policy_engine()` — PDP, PEP, policy store, rate/spend controls
  - `bootstrap_mitm_proxy()` — CA manager, TLS interceptor, MITM handler
  - `bootstrap_audit_services()` — audit DB engine, audit chain, chain anchor
  - `bootstrap_slo_services()` — SLO engine, webhook client, breach detector
  - `bootstrap_governance_services()` — oversight, lifecycle, transparency, notification, approval
  - `bootstrap_gateway_services()` — AI detector, route table, PAC generator, MCP inspector
  - `bootstrap_soc_services()` — SOC normalizer, MITRE mapper, sink router
  - `bootstrap_deployment_proxy()` — reverse/transparent proxy
  - `bootstrap_trust_center()` — trust center settings and service
  - `bootstrap_compliance_services()` — compliance engine
- Called sequentially in `lifespan()` in `src/anonreq/main.py:295-305`

## HTTP Client Pattern

**SSRF Hardening (applied 2026-07-17):**
- All outbound `httpx.AsyncClient` instances must use `follow_redirects=False`
- 12 instances hardened across: providers (4), SOC sinks (5), presidio client, AML webhook, webhook client
- Pattern:
```python
self._http_client = httpx.AsyncClient(
    timeout=self._timeout,
    follow_redirects=False,
)
```

## Configuration Pattern

**Dual Configuration:**
- Pydantic Settings (`src/anonreq/config/__init__.py`) for runtime config with `ANONREQ_` prefix
- YAML files in `config/` for behavior configuration (policy, classification, compliance presets, etc.)
- `Settings` validates required fields at import time (fail-secure startup)
- API key minimum length validation: `Field(min_length=32)`

**Optional Dependencies (introduced post-Phase 27):**
- `pyproject.toml` defines optional dependency groups:
  - `[storage]` — minio
  - `[exports]` — pyarrow, reportlab
  - `[ml]` — onnxruntime
  - `[voice]` — openai-whisper
  - `[all]` — all of the above
  - `[dev]` — testing and linting tools

## Testing Patterns

**Framework:** pytest with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed)

**Test Structure:**
- `tests/unit/` — unit tests organized by module
- `tests/integration/` — integration tests (e.g., `test_e2e_round_trip.py`)
- `tests/property/` — Hypothesis property tests
- 287 test files, 260 with `test_` prefix
- Config in `pyproject.toml`: `testpaths = ["tests"]`, `pythonpath = ["src"]`

**Fixture Pattern:**
- Module-level `os.environ.setdefault()` in `tests/conftest.py` for Settings singleton
- `cache_manager` fixture uses `CacheManager._from_client()` factory (replaced fragile `__new__` pattern)
- Lazy imports in fixtures to avoid slow collection
- `fakeredis.aioredis.FakeRedis` for cache tests, `respx` for HTTP mocking

**E2E Round-Trip Test Pattern:**
- `tests/integration/test_e2e_round_trip.py` — full pipeline test
- Builds complete pipeline with real stages + mocked provider via respx
- Verifies PII detection → tokenization → mock provider → restoration
- Helper functions: `_build_pipeline()`, `_make_proc_ctx()`

---

*Convention analysis: 2026-07-17*
