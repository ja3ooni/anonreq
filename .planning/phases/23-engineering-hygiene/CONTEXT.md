# Phase 23 — Engineering Hygiene: Context

## Phase Scope

CI/CD pipeline, code quality enforcement (ruff/mypy), secure Docker defaults.
No new functionality. Three requirements: HYG-01 (CI/CD), HYG-02 (ruff/mypy), HYG-03 (Docker).

## Decisions

### D1. CI/CD Platform
**Decision:** GitHub Actions (existing workflows: `docs-ci.yml`, `docs-nightly.yml`, `release.yml`)
**Rationale:** Repository is GitHub-hosted; no reason to switch.

### D2. Test Workflow Triggers
**Decision:** `pull_request` targeting `main` + `push` to `main`. Load tests excluded (manual trigger only).
**Rationale:** Standard safe CI pattern (duplicate runs on PR+push avoided by GitHub's `on.push` skip for PR branches).

### D3. Python Version Matrix
**Decision:** Single version: 3.12 (matching project constraint)
**Rationale:** Project requires `>=3.12`, no compat concern yet for wider matrix.

### D4. Package Manager
**Decision:** `uv sync --group dev` (as documented in AGENTS.md)
**Rationale:** Existing project convention (`uv run pytest` in testing expectations).

### D5. CI Service Containers
**Decision:** No Docker service containers in CI. Tests use fakeredis (Redis mock) and respx (HTTP mock) for isolation.
**Rationale:** Integration tests that need real Docker services (e.g., Presidio) are already mocked. No CI Docker overhead needed.

### D6. ruff Configuration
**Decision:** Rules `E`, `F`, `I`, `N`, `W`, `UP`, `B`, `SIM`, `ARG`, `PT`, `RUF` with `target-version = "py312"`, `line-length = 100`.
**Rationale:** Matches SPEC §1.2. Config goes in `pyproject.toml` under `[tool.ruff]` (single source of truth).

### D7. ruff Auto-Fix Sweep
**Decision:** Run `ruff check --fix src/ tests/` for auto-fixable violations. For unsafe/non-auto-fixable violations (ARG, SIM, B), fix manually per category then commit.
**Rationale:** User approved "fix findings automatically" for P1 MOTE items. Unsafe fixes get manual review.

### D8. mypy Configuration
**Decision:** `strict = true` with per-module overrides for known-untyped deps:
- `fastapi.*`, `pydantic.*`, `sqlalchemy.*`, `cryptography.*`, `httpx.*`, `structlog.*`, `prometheus_client.*`, `yaml.*`, `jinja2.*`, `reportlab.*`, `minio.*`, `pyarrow.*`, `watchdog.*`
**Rationale:** Strict mode catches real issues. Known-untyped third-party packages get `ignore_missing_imports = True`.

### D9. mypy Violation Fix Strategy
**Decision:** Fix iteratively: add type annotations where feasible, add `# type: ignore[code]` with inline comment for cases where annotation is impractical (e.g., complex dynamic patterns).
**Rationale:** Balances strict enforcement with pragmatism. Inline `type: ignore` allows precise scoping.

### D10. Coverage Threshold
**Decision:** 70% line coverage threshold, enforced in CI as a warning (not blocking) initially. Hard-enforce at 60%.
**Rationale:** Current baseline unknown; soft enforcement avoids blocking CI on day one while nudging upward.

### D11. pre-commit Hooks
**Decision:** No pre-commit config. CI enforces all checks.
**Rationale:** Not listed in SPEC. Reduces local setup friction. Developers run `uv run ruff check` and `uv run mypy` locally.

### D12. Docker Hardening Scope
**Decision:** Remove host port bindings from: `postgres` (5432), `minio` (9000, 9001), `prometheus` (9090), `grafana` (3000). Disable `GF_AUTH_ANONYMOUS_ENABLED`. Keep gateway 8080 exposed. `valkey-exporter` and `postgres-exporter` already have no host ports. Presidio has no host ports.
**Rationale:** Matches SPEC §1.3 exactly.

### D13. CI Dependency Caching
**Decision:** Cache `~/.cache/uv` across CI runs. Use `actions/cache@v4` with hash of `pyproject.toml` as key.
**Rationale:** Speeds up CI by 30-60s per run without complexity.

### D14. Test Selection in CI
**Decision:** Run `uv run pytest tests/ -x -v --ignore=tests/load -m "not load"`. Load tests require explicit workflow dispatch.
**Rationale:** SPEC §1.1: exclude load tests from CI auto-run.

## Gray Areas Resolved

| Gray Area | Resolution |
|---|---|
| Auto-fix or just configure? | Auto-fix safe violations; manual for unsafe ones |
| CI service containers needed? | No — existing tests mock external deps |
| mypy strictness level | `strict = true` with per-module overrides |
| Coverage enforcement level | 70% soft ceiling, 60% hard block |
| pre-commit hooks? | No — CI-only enforcement |
| Which Docker ports to remove | All non-gateway observability + infra ports |
| CI caching | Yes — uv cache with actions/cache@v4 |

## Dependencies

- **Depends on:** Nothing (foundation phase for v1.5)
- **Depended by:** Phases 24, 25, 26 (all require CI passing)
- **Upstream artifacts:** Existing `pyproject.toml`, `docker-compose.yml`, `ruff`/`mypy` CLI tools (new dev deps)

## Risk Notes

- **mypy strict on large codebase:** May surface 100+ violations. Iterative fix with per-category commits prevents unbounded scope creep.
- **Docker hardening breaks local dev workflows:** Engineers using observability profile must pass `--profile observability` explicitly. Document in `CONTRIBUTING.md`.
- **Auto-fix changes large diff:** Review carefully. Commit auto-fixes separately from config changes for clean review.
