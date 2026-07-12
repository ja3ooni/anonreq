<Phase 27: v1.5 Tech Debt Cleanup - Pattern Map>
**Mapped:** 2026-07-12
**Files analyzed:** 4
**Analogs found:** 2 / 2

## File Classification
| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
| :--- | :--- | :--- | :--- | :--- |
| `config/trust_center.yaml` | config | N/A (Static config) | `config/trust_center.yaml` | Exact (Self) |
| `.planning/phases/23-engineering-hygiene/23-01-SUMMARY.md` | doc | N/A (Prose document) | `.planning/phases/23-engineering-hygiene/23-01-SUMMARY.md` | Exact (Self) |

*Note: `tests/test_agent_approval.py` and `tests/test_agent_policy.py` are targeted for deletion and do not require code patterns to copy from.*

## Pattern Assignments

### config/trust_center.yaml
- **Role:** config
- **Data Flow:** N/A (Static config)
- **Imports:** None
- **Auth:** None
- **Core Pattern:** YAML key-value configuration. The `enabled` flag gates API routers from exposing Trust Center endpoints.
- **Error Handling / Validation:** Validated via Pydantic model validation on application startup.
  ```python
  # Loaded in src/anonreq/main.py:
  import yaml
  trust_config_path = "config/trust_center.yaml"
  with open(trust_config_path) as f:
      trust_yaml = yaml.safe_load(f) or {}
  trust_settings = TrustCenterConfig(**trust_yaml)
  app.state.trust_center_settings = trust_settings
  app.state.trust_center_enabled = trust_settings.enabled
  ```
  And evaluated via FastAPI dependency:
  ```python
  # Gate in src/anonreq/trust_center/router.py:
  async def trust_center_enabled(request: Request) -> bool:
      if not getattr(request.app.state, "trust_center_enabled", False):
          raise HTTPException(
              status_code=status.HTTP_404_NOT_FOUND,
              detail="Trust Center is not enabled",
          )
      return True
  ```
- **Testing:** `tests/test_trust_center.py` does not read `config/trust_center.yaml` from disk. The fallback defaults defined on `TrustCenterSettings` class must remain `False`. Therefore, no tests need modification when changing the YAML default value.
- **Target Edit:**
  ```yaml
  enabled: true
  ```

### .planning/phases/23-engineering-hygiene/23-01-SUMMARY.md
- **Role:** doc
- **Data Flow:** N/A (Prose document)
- **Imports:** None
- **Auth:** None
- **Core Pattern:** Prose updates describing type check/linter rollout configuration mechanisms.
- **Error Handling / Validation:** N/A
- **Testing:** N/A
- **Target Edit:**
  Clarify that rather than a "staged rollout" over time, engineering hygiene is enforced globally via:
  1. **Ruff**: A single global rule set (`E, F, I, N, W, UP, B, SIM, ARG, PT, RUF`) applied across `src/` and `tests/`.
  2. **Mypy**: Global `strict = true` enforced on the `src/` tree, with specific first-party (e.g., `anonreq.governance.*`, `anonreq.retention.*`, etc.) and third-party modules utilizing `[[tool.mypy.overrides]]` blocks for `disable_error_code` suppression or `ignore_missing_imports`.

## Shared Patterns
- **Configuration Parsing:** Standard YAML loading during FastAPI startup inside lifespan handler in `src/anonreq/main.py`.
- **Typing Strictness:** Mypy is configured globally with `strict = true` in `pyproject.toml` with module-specific `[[tool.mypy.overrides]]` blocks for first-party packages (e.g. `anonreq.governance.*`) and third-party packages to disable specific error codes or ignore missing imports.
- **Linter Rules:** Ruff rules are configured globally in `pyproject.toml` targeting Py312 (`E`, `F`, `I`, `N`, `W`, `UP`, `B`, `SIM`, `ARG`, `PT`, `RUF` selected; `B008` ignored) applied uniformly.

## No Analog Found
Not applicable. All target modified files exist in-place and represent their own exact analogs. Deleted files (`tests/test_agent_approval.py` and `tests/test_agent_policy.py`) do not require analogs as they are being removed.
</Phase 27: v1.5 Tech Debt Cleanup - Pattern Map>
