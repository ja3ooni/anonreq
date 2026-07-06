# Coding Conventions

**Analysis Date:** 2026-07-06

## Naming Patterns

**Files:**
- `snake_case.py` for all Python modules (e.g., `regex_detector.py`, `presidio_client.py`, `tail_buffer.py`)
- Test files: `test_{module_name}.py` for unit tests (e.g., `test_detection.py`, `test_tail_buffer.py`)
- Property test files: `test_{domain}_invariants.py` or `test_{feature}.py` in `tests/property/` (e.g., `test_locale_invariants.py`, `test_fail_secure.py`)
- YAML config files: `snake_case.yaml` (e.g., `mnpi_recognizers.yaml`, `financial_crime_words.yaml`)

**Functions:**
- `snake_case` for all function and method names (e.g., `luhn_checksum()`, `find_high_risk_word_positions()`, `_extract_request_id()`)
- Private functions prefixed with single underscore: `_make_error_body()`, `_negotiate_and_merge()`
- Async functions use `async def` with no special naming prefix beyond `snake_case`
- Helper functions in tests use descriptive `snake_case`: `make_delta()`, `collect()`, `_ai_request()`

**Variables:**
- `snake_case` for all variables (e.g., `request_id`, `entity_type`, `raw_pii`)
- Module-level constants: `UPPER_SNAKE_CASE` (e.g., `ENTITY_SPECIFICITY`, `TIER_1_ENTITIES`, `MAX_EXAMPLES`, `_LUHN_VALIDATED`)
- Type-annotated throughout with `variable: Type = value` style
- Short-lived variables use brief but clear names: `rid`, `det`, `ex`

**Types:**
- Type annotations via `from __future__ import annotations` at top of every module
- Custom types defined with `type` alias or imported from `typing`
- `Any` used sparingly, mostly in generic dict return types and fixture declarations
- Complex types use `list[dict[str, Any]]` rather than `List[Dict[str, Any]]` (Python 3.12 style)
- `re.Pattern` quoted in forward-reference style when used in class attributes: `dict[str, "re.Pattern"]`

**Classes:**
- `PascalCase` for all classes (e.g., `RegexDetector`, `ExclusionList`, `ContextBooster`, `PresidioClient`, `TailBuffer`)
- Exception classes: `PascalCase` with `Error` suffix (e.g., `PresidioTimeoutError`, `PipelineAbortError`, `DependencyUnavailableError`)
- Private classes not used; internal implementation is expressed via private functions or nested classes in tests

## Code Style

**Formatting:**
- No formatter is configured in the repository (per CLAUDE.md: "No linter/formatter is configured in this repo")
- Code is hand-formatted with consistent 4-space indentation
- Line lengths vary but generally stay under 100 characters
- Blank lines: two between top-level definitions, one between methods in a class, one around section-comment blocks

**Linting:**
- No linter configured in `pyproject.toml`; `.ruff_cache/` and `.mypy_cache/` are in `.gitignore` suggesting optional local use
- No `eslint`, `ruff`, `flake8`, or `pylint` config files present
- `# type: ignore[union-attr]` and `# type: ignore[method-assign]` used inline for type-checker overrides
- `# noqa: F811` used in a single place for structlog re-import in `exceptions.py`

**Imports:**
- `from __future__ import annotations` is the first import in every module
- Standard library imports first (e.g., `import re`, `from pathlib import Path`)
- Third-party imports second (e.g., `import pytest`, `from hypothesis import ...`, `import yaml`)
- Local application imports third (e.g., `from anonreq.detection.regex_detector import RegexDetector`)
- Groups separated by blank lines
- Lazy imports used in conftest files to avoid slow test collection (~40-180s overhead avoided):
  ```python
  @pytest.fixture
  def app():
      from fastapi import FastAPI
      return FastAPI()
  ```

## Import Organization

**Order:**
1. `from __future__ import annotations`
2. Standard library modules (`re`, `typing`, `pathlib`, `enum`, `asyncio`, `json`, `logging`)
3. Third-party packages (`pytest`, `hypothesis`, `yaml`, `httpx`, `structlog`, `fastapi`)
4. Local application imports (`from anonreq.detection.regex_detector import ...`)
5. Test imports from `tests.` package (in test files): `from tests.property.conftest import inject_failure`

**Path Aliases:**
- No custom path aliases or `PYTHONPATH` manipulation in source code
- `pyproject.toml` sets `pythonpath = ["src"]` for pytest, so imports are `from anonreq.xxx import YYY`
- Test package imports use `from tests.conftest import ...` and `from tests.property.strategies import ...`

**Imports within Type Annotations:**
- `TYPE_CHECKING` guards are NOT used — types from all modules are imported directly
- Forward references using string literals for self-referential types: `"ExclusionList"`, `"re.Pattern"`

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
- Module-level logger via `logger = logging.getLogger(__name__)` or `log = get_logger()`
- `structlog.get_logger()` used in gateway/main modules
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
- `component` field to identify the origin within the application
- Structured fields use `snake_case` keys: `request_id`, `cache_health`, `failure_type`
- No PII values ever logged — field allowlist enforced by `logging_config.py`

## Comments

**When to Comment:**
- Module-level docstrings describe purpose, requirements cross-references (e.g., "Per D-38", "Per Phase 15"), and threat model coverage
- Class docstrings with `Usage::` examples showing code snippets
- Method docstrings follow Google-style with `Args:`, `Returns:`, `Raises:` sections
- Section comments in test files: horizontal rules (`# ----`) to separate test groups
- Inline comments only for non-obvious logic (e.g., Luhn validation, de-duplication strategy)
- Requirement/ticket references throughout: `# Per D-32, D-34`, `# Phase 17: MITM proxy setup`, `# Plan 13-04, Task 2`

**JSDoc/TSDoc:**
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
- `create_app()` in `main.py` is large (~450 lines) — this is the exception (application factory)
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

---

*Convention analysis: 2026-07-06*
