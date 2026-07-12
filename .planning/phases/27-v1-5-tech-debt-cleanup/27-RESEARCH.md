# Phase 27: v1.5 Tech Debt Cleanup - Research

**Researched:** 2026-07-12
**Domain:** Repository cleanup (dead test files, config default flip, documentation correction)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**HYG-01: Broken test files**
- D-01: Delete `tests/test_agent_approval.py` and `tests/test_agent_policy.py` outright — do not exclude via CI `--ignore`, do not skip-mark, do not quarantine.
- D-02: Confirmed via `git log --oneline main -- src/anonreq/agent/approval.py` and `.../policy.py` (both empty output) — `anonreq.agent.approval`, `.policy`, `.inspector`, `.registry` never existed anywhere in `main`'s history. These are aspirational tests for a feature that was never built, not tests for code that regressed. Safe to delete with no functional loss.
- D-03 (explicit non-goal): Do NOT implement `anonreq.agent.approval`/`.policy`/`.inspector`/`.registry`. Building an agent-approval/policy feature is new scope and belongs in its own future phase if ever prioritized — not part of this cleanup.

**Trust Center default**
- D-04: Flip `config/trust_center.yaml` from `enabled: false` to `enabled: true`.
- D-05: Rationale carried forward from Phase 24's CONTEXT.md (D9): Trust Center was designed as a public, no-auth compliance portal ("Public Access... No API key required"). Shipping it off by default contradicts that design intent — the feature is effectively invisible unless an operator already knows to flip a YAML flag they have no reason to look for.
- D-06: No other Phase 24 behavior changes — rate limiting (60 RPM/IP), fail-closed-503, and aggregate-only responses (Phase 24 D8, D10, D11) are unaffected by this default flip.

**HYG-02 doc correction**
- D-07: Correct `.planning/phases/23-engineering-hygiene/23-01-SUMMARY.md` — remove or rewrite the "staged rollout" claim so it matches the actual implementation: a single global `strict = true` mypy block with per-module `ignore_missing_imports` overrides for untyped third-party packages, and a single global ruff rule set. No functional code change.
- D-08 (explicit non-goal): Do NOT build real per-directory/incremental strictness staging. That would be new scope (a genuine ruff/mypy rollout mechanism), not a documentation fix.

### Claude's Discretion
- Exact wording of the corrected SUMMARY.md language (D-07) — no specific phrasing was dictated, just "make it match reality."
- Whether to add a one-line comment in `config/trust_center.yaml` near `enabled: true` noting it can be disabled by operators who want it off — reasonable addition, not required by the discussion.

### Deferred Ideas (OUT OF SCOPE)
- Agent approval/policy feature (`anonreq.agent.approval`, `.policy`, `.inspector`, `.registry`) — if this capability is ever wanted, it needs its own phase with real requirements, not resurrection of these orphaned tests. Explicitly out of scope here (D-03).
- Real staged ruff/mypy rollout mechanism — per-directory or incremental strictness. Explicitly out of scope here (D-08); today's global-strict config works and isn't broken, just under-documented previously.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HYG-01 | CI/CD test workflow must go green on every push/PR | Confirmed the two broken test files are the sole collection blocker; deletion is sufficient, no other CI config references them |
| HYG-02 | ruff + mypy enforce quality in CI, documented accurately | Confirmed exact current pyproject.toml `[tool.ruff]`/`[tool.mypy]` config to ground the corrected SUMMARY.md wording |
| TRUST-01 | Public `/v1/trust/*` endpoints reachable by default | Confirmed single-gate architecture (`config/trust_center.yaml: enabled`) with no secondary env-var/license gate blocking reachability after the flip |
</phase_requirements>

## Summary

This is a 3-item mechanical cleanup phase with no new code paths. All three items were independently verified against the live repository state (not just the audit's claims), and all three are confirmed safe, isolated, single-purpose changes with no hidden blast radius beyond what CONTEXT.md already scoped. One material discrepancy was found and must be surfaced to the planner: the literal phrase **"staged rollout" does not currently appear anywhere in `23-01-SUMMARY.md`** (or in `23-01-PLAN.md`, or `CONTEXT.md` for Phase 23) — despite both the milestone audit and Phase 27's own CONTEXT.md (D-07) asserting it needs to be "removed or rewritten." The underlying overstatement the audit is pointing at is real (see "State of the Art" below), but the planner should treat D-07 as "add/strengthen accurate wording about mypy's actual per-module override strategy" rather than "delete an existing sentence," since there is no matching sentence to delete verbatim.

**Primary recommendation:** Execute all three items as straightforward file operations — two `rm`, one single-line YAML edit, one prose edit — in a single wave with no dependencies between them. No test files need modification for the trust_center flip (verified no test asserts the YAML-loaded default). No CI workflow file needs updating for the test deletions (verified no filename references exist). No coverage-gate risk from the deletions (both files currently error at collection, contributing zero to the coverage numerator or denominator today).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Test suite composition (delete dead test files) | Test tooling (pytest / CI) | — | Pure test-tree hygiene; no runtime tier involved |
| Trust Center default-enabled flag | Config / Startup (YAML loaded at FastAPI lifespan) | API tier (router gate) | `config/trust_center.yaml` is read once at `main.py` lifespan startup into `app.state.trust_center_enabled`; the API router's `trust_center_enabled` dependency reads that state per-request |
| Documentation accuracy correction | Docs / Planning artifacts | — | No runtime tier; `.planning/` is a project-history artifact, not shipped code |

## Item 1: Delete broken agent test files (HYG-01 / D-01, D-02)

**Exact files to delete:**
- `tests/test_agent_approval.py`
- `tests/test_agent_policy.py`

**Verification performed:**
- `uv run pytest tests/test_agent_approval.py tests/test_agent_policy.py --collect-only -q` reproduces exactly the audit's claim: `ModuleNotFoundError: No module named 'anonreq.agent.approval'` and `'anonreq.agent.policy'` respectively. [VERIFIED: local pytest run]
- `ls src/anonreq/agent/` confirms only `config.py`, `mcp_parser.py`, `metrics.py`, `result_sanitizer.py`, `schema.py`, `tool_inspector.py` exist — no `approval.py`, `policy.py`, `inspector.py`, `registry.py`. [VERIFIED: filesystem]
- `ls src/anonreq/middleware/` confirms `anonreq.middleware.agent` (imported by `test_agent_policy.py`'s `TestAgentMiddleware` class) also does not exist — only `classification.py`, `content_type.py`, `firewall_inbound.py`, `firewall_outbound.py`, `policy.py`, `rbac.py`, `response_headers.py`. [VERIFIED: filesystem] This is an *additional* non-existent import beyond what CONTEXT.md's code_context section listed (it named `anonreq.agent.policy`/`.registry` but did not call out that `anonreq.middleware.agent` — imported deep inside a test method, not at module top — is also missing). It does not change the disposition (file is still 100% dead), but the planner/executor should not be surprised if grep-for-imports tooling flags a third missing module inside this file.

**Do these files test anything real beyond the non-existent modules?**
No. Read both files in full:
- `tests/test_agent_approval.py` (224 lines): every test method exercises `ToolApprovalQueue` (from `anonreq.agent.approval`) or `ToolResultInspector`/`InspectionResult`/`SensitivityLevel` (from `anonreq.agent.inspector`). No test in this file touches any existing, shipped module. The `CacheManager` import (`anonreq.cache.manager`) is real and exists, but it is only used as a constructor dependency to instantiate the non-existent `ToolApprovalQueue` — it is not itself under test.
- `tests/test_agent_policy.py` (374 lines): every test method exercises `ToolPermitRegistry`/`ToolPolicyEvaluator`/`ToolPolicyDecision`/`ToolPermission`/`ToolPermissionLevel` (from `anonreq.agent.policy`) or `ToolPermit` (from `anonreq.agent.registry`), or `AgentMiddleware` (from `anonreq.middleware.agent`, imported inline in the `TestAgentMiddleware` class). All four modules are non-existent.

Conclusion: **no functional loss** from deletion — both files are 100% dead weight, confirming D-02's conclusion with direct file-content evidence in addition to the git-log evidence CONTEXT.md already cites.

**CI workflow references (`.github/workflows/test.yml`):**
`grep -rn "test_agent_approval\|test_agent_policy" .github/` returns nothing. The workflow invokes pytest broadly (`pytest tests/ -x -v --ignore=tests/load -m "not load"`) with no per-file references. **No CI config changes are needed** beyond the deletion itself — this is a strictly smaller change than CONTEXT.md's "Files to modify" list implies (that list only names `config/trust_center.yaml` and the SUMMARY.md; it correctly does NOT list `.github/workflows/test.yml`, and this research confirms that omission is correct, not an oversight).

**Coverage-gate risk (`pyproject.toml` `[tool.coverage.report] fail_under = 60`):**
Both files currently **fail at collection** (`ModuleNotFoundError`), meaning pytest-cov (when run with `--cov=anonreq`) never executes a single line of these files' bodies today — they contribute **zero lines to the coverage numerator, and since `[tool.coverage.run] source = ["anonreq"]` scopes coverage measurement to the `anonreq` package itself (not `tests/`), test file line count never enters the coverage denominator either.** Deleting these two files therefore has **no possible effect on the measured coverage percentage** — the 60% hard-block gate (Phase 23 CONTEXT.md D10, mirrored in current `pyproject.toml`) is unaffected in either direction. This closes the exact concern raised in the research brief.

Secondary finding (out of scope, flag only): `pytest-cov` is not declared as a dependency anywhere in `pyproject.toml` (`[project.optional-dependencies] dev` has no `pytest-cov` entry), nor found in `requirements*.txt`/`uv.lock` via grep. Yet `.github/workflows/test.yml`'s "Coverage report" step invokes `uv run pytest tests/ --cov=anonreq ...`. This is a pre-existing gap unrelated to D-01/D-02 (CI presumably works because `uv sync --extra dev` resolves it transitively via some other dev dependency, or CI has been silently failing this specific step — not verified further since it is out of this phase's scope per the CONTEXT.md boundary). **Not a planner action item for this phase** — noted only so it isn't mistaken for something these test deletions caused.

**Additional files needing matching updates beyond CONTEXT.md's list:** None found. CONTEXT.md's "Files to delete" list (the two test files) is complete and accurate.

## Item 2: Flip Trust Center default to enabled (TRUST-01 / D-04, D-05, D-06)

**Exact file and change:**
- `config/trust_center.yaml`, line 1: `enabled: false` → `enabled: true`

**Gate architecture verified (no secondary gate):**
- `src/anonreq/main.py` (lifespan startup, ~line 596-627): reads `config/trust_center.yaml` via `yaml.safe_load()`, constructs `TrustCenterConfig(**trust_yaml)` (which is `TrustCenterSettings` imported under an alias — see below), and sets `app.state.trust_center_enabled = trust_settings.enabled` directly from the parsed YAML value. [VERIFIED: source read]
- `src/anonreq/trust_center/config.py`: `TrustCenterSettings` is a `pydantic_settings.BaseSettings` subclass with `enabled: bool = False` as its **Python class default** (used only as a fallback if the YAML key is absent/malformed) — `model_config = SettingsConfigDict(extra="ignore")` has no `env_prefix` set, so there is no `ANONREQ_TRUST_CENTER_ENABLED`-style env var wired to override this field in current code. [VERIFIED: source read]
- `src/anonreq/trust_center/router.py`: the only enforcement point is the `trust_center_enabled` FastAPI dependency (line 21-24), which reads `request.app.state.trust_center_enabled` and raises `404` if falsy. This is applied via `dependencies=[Depends(trust_center_enabled), Depends(_check_rate)]` on all four routes (`/status`, `/compliance`, `/metrics`, `/security`). **This is the single gate.** No license check, no feature flag, no separate env var override exists anywhere in the request path. [VERIFIED: source read]

Conclusion: flipping the one YAML line is **sufficient and complete** to make the endpoints reachable — no other file needs a matching change for reachability.

**Rate limiter and fail-closed-503 independence (D-06) verified:**
- `TrustCenterRateLimiter` (in `src/anonreq/trust_center/service.py`, ~line 187-213) implements a fixed 60-requests-per-current-minute-bucket check, entirely independent of the `enabled` flag — it is wired as its own `Depends(_check_rate)` dependency, constructed unconditionally at lifespan startup (`app.state.trust_center_rate_limiter = TrustCenterRateLimiter(cache_manager)`, executed inside the same `try` block regardless of `trust_settings.enabled`'s value). [VERIFIED: source read]
- Fail-closed-503 behavior: each route handler (`get_trust_service`, `get_rate_limiter`) raises `HTTPException(503, "service_unavailable")` if the corresponding `app.state` attribute is `None` — this is unconditional service-availability handling, not gated by the `enabled` flag. [VERIFIED: source read]
- Both mechanisms require **zero changes** for this phase — D-06 is confirmed accurate.

**Test file impact (`tests/test_trust_center.py`) — the critical check requested:**
Searched the full file for any assertion tied to the *shipped YAML config's* default value (as opposed to the Python class default). Result: **no test loads `config/trust_center.yaml` from disk or asserts about it.** Specifically:
- `test_default_values` (line 32-39) does `s = TrustCenterSettings()` — constructing the settings object with **no arguments**, asserting `s.enabled is False`. This tests the **Python class default** (`enabled: bool = False` in `config.py`), which is a defensive fallback for when the YAML is absent/unparseable — it is intentionally NOT changed by this phase (only the shipped YAML file's value changes) and should **remain `False`**. Do not touch this assertion.
- All integration tests (`test_disabled_gate_returns_404`, etc.) construct `TrustCenterSettings(enabled=True)` explicitly or set `app.state.trust_center_enabled` directly on a fixture app — none of them read the real `config/trust_center.yaml` file from the repo.

**Conclusion: `tests/test_trust_center.py` requires NO changes.** This directly answers (and closes) the research question — there is no test asserting `enabled: false` is the shipped default; the one test that mentions a `False` default is testing the code's fallback constant, which is a separate, correct, and unrelated concept from the YAML file's value, and must not be conflated or edited.

**Additional files needing matching updates beyond CONTEXT.md's list:** None found. `config/trust_center.yaml` is the only file requiring a change for this item. (CONTEXT.md's optional discretionary addition — a one-line comment near `enabled: true` — remains a reasonable, non-required addition per D-06's Claude's Discretion section.)

## Item 3: Correct the "staged rollout" claim (HYG-02 / D-07, D-08)

**Important discrepancy found — read before planning this item:**

The literal phrase **"staged rollout" does not appear anywhere** in the current text of:
- `.planning/phases/23-engineering-hygiene/23-01-SUMMARY.md` (full file read, 84 lines)
- `.planning/phases/23-engineering-hygiene/23-01-PLAN.md` (full file read, 208 lines)
- `.planning/phases/23-engineering-hygiene/CONTEXT.md` (full file read, 90 lines)

`grep -rn "staged" .planning/phases/23-engineering-hygiene/` returns zero matches. Both the milestone audit (`.planning/v1.5-MILESTONE-AUDIT.md`, "HYG-02 SUMMARY.md claims a 'staged rollout'...") and Phase 27's own CONTEXT.md D-07 assert this phrase exists and needs to be "removed or rewritten," but it is not present in the file as it stands today. Two possibilities: (a) the audit paraphrased/summarized an impression from the SUMMARY's prose rather than quoting it verbatim, or (b) the phrase was already edited out between the audit and now. Either way, **the planner cannot literally "find and replace" a sentence that isn't there.**

**What IS actually in `23-01-SUMMARY.md` today (verbatim, lines 40-52):**
> "Ruff and mypy configured in pyproject.toml and verified passing cleanly across the codebase with type-safe cache health checks"
>
> ## Accomplishments
> - Verified ruff check passes with zero violations across `src/` and `tests/`.
> - Resolved type-checking error in `src/anonreq/cache/health.py` by introducing type-safe handling of `save_value` as a string or list of strings.
> - Fixed `tests/test_cache.py` cache manager fixture to mock config operations and closure state in `FakeRedis` so the pytest suite passes successfully.

This text does not literally claim a "staged rollout" — but the audit's underlying concern (per `v1.5-MILESTONE-AUDIT.md`: "pyproject.toml shows a single global strict block with no staging mechanism") is about a **broader impression** that could be drawn from the phase's `CONTEXT.md` D8/D10 language ("mypy strictness level" / "Coverage enforcement level... 70% soft ceiling, 60% hard block") plus the generic phrasing "configured... and verified passing cleanly" without specifying *how* strictness is actually achieved (global block + per-module overrides, not incremental rollout). D-07's actual intent, confirmed by its own text ("remove or rewrite... so it matches the actual implementation: a single global `strict = true` mypy block with per-module `ignore_missing_imports` overrides"), is best satisfied by **adding an accurate, explicit sentence describing the real mechanism** to `23-01-SUMMARY.md`, since there's no inaccurate sentence to literally delete.

**What is actually configured today, verified against live `pyproject.toml` (lines 82-128) — use this to ground the corrected wording:**

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "ARG", "PT", "RUF"]
ignore = ["B008"]

[tool.mypy]
python_version = "3.12"
strict = true
show_error_codes = true
disable_error_code = ["type-arg"]
plugins = ["pydantic.mypy", "sqlalchemy.ext.mypy.plugin"]

[[tool.mypy.overrides]]
module = ["fastapi.*", "pydantic.*", "sqlalchemy.*", ...]   # 12 third-party packages
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["anonreq.governance.*"]
disable_error_code = [...9 codes...]

[[tool.mypy.overrides]]
module = ["anonreq.retention.*"]
disable_error_code = [...5 codes...]

[[tool.mypy.overrides]]
module = ["anonreq.dsar.*"]
disable_error_code = [...5 codes...]

[[tool.mypy.overrides]]
module = ["anonreq.breach.*"]
disable_error_code = [...5 codes...]

[[tool.mypy.overrides]]
module = ["anonreq.cache.*", "anonreq.proxy.*", ... 18 more first-party packages ...]
disable_error_code = [...13 codes...]

[[tool.mypy.overrides]]
module = ["anonreq.providers.*"]
disable_error_code = ["override"]

[[tool.mypy.overrides]]
module = ["anonreq.api.*", ... 12 more first-party packages ...]
disable_error_code = [...16 codes...]
```

Accurate facts to state in the corrected SUMMARY.md text (per Claude's Discretion on exact wording):
1. **ruff**: a single global rule set (`E, F, I, N, W, UP, B, SIM, ARG, PT, RUF`) applied uniformly to `src/` and `tests/` — no per-directory or per-module variation, no staging.
2. **mypy**: `strict = true` is a single global setting applied to the whole `src/` tree — there is no incremental/staged rollout (e.g., no per-package opt-in schedule, no "strict mode enabled for module X in month 1, module Y in month 2" mechanism). What *does* vary per-module is **error-code suppression** (`disable_error_code` overrides / `ignore_missing_imports` for untyped third-party stubs) — this is a permanent pragmatic carve-out for specific packages/subsystems (Phase 24-26 additions like `anonreq.governance.*`, `anonreq.retention.*`, `anonreq.dsar.*`, `anonreq.breach.*`, and a large shared-override block for many other first-party packages), not a rollout schedule that will later be tightened.
3. Note for the planner: the `[[tool.mypy.overrides]]` blocks visible in `pyproject.toml` today are considerably larger than what `23-01-PLAN.md` originally specified (which only listed the third-party `ignore_missing_imports` block). The additional first-party override blocks (`anonreq.governance.*`, `anonreq.cache.*`, etc.) were clearly added later, in Phases 24-26, not in Phase 23's original work — the corrected SUMMARY.md text should describe the mechanism generically ("per-module overrides exist for both untyped third-party packages and select first-party subsystems") rather than implying Phase 23 alone produced the current full override list, to avoid introducing a new inaccuracy while fixing the old one.

**Additional files needing matching updates beyond CONTEXT.md's list:** None — this is a single-file prose edit to `23-01-SUMMARY.md`. `23-01-PLAN.md` and Phase 23's `CONTEXT.md` do not contain the disputed claim and do not need touching (confirmed by full read of both).

## Don't Hand-Roll

Not applicable — no new code is being written in this phase. All three items are deletions, a config value flip, and a documentation edit.

## Common Pitfalls

### Pitfall 1: Editing `tests/test_trust_center.py`'s `test_default_values` by mistake
**What goes wrong:** An executor sees `assert s.enabled is False` in the trust center test file and assumes it must flip to `True` to match the new "enabled by default" behavior.
**Why it happens:** Conflating the YAML file's shipped default with the Python class's fallback default — they are two different things that happen to currently share the same value coincidentally (both `False` before this phase).
**How to avoid:** This test constructs `TrustCenterSettings()` with zero arguments and no YAML involved — it is testing the dataclass/BaseSettings field default, which is a safety fallback for missing/corrupt config and should stay `False` regardless of what the shipped YAML says. Leave this test untouched.
**Warning signs:** Any diff touching `tests/test_trust_center.py` in this phase should be treated as a red flag and double-checked against this research — the correct diff for this phase's test suite is empty for this file.

### Pitfall 2: Trying to find and delete a "staged rollout" sentence that doesn't exist
**What goes wrong:** An executor searches `23-01-SUMMARY.md` for the phrase "staged rollout" per the audit's/CONTEXT.md's wording, finds nothing, and either gives up or invents a deletion that doesn't correspond to real content.
**Why it happens:** The audit's phrasing is a paraphrase of an impression, not a verbatim quote from the file.
**How to avoid:** Treat D-07 as "add accurate detail about the real mypy/ruff mechanism to the existing Accomplishments/summary prose," grounded in the actual `pyproject.toml` content documented above, rather than searching for literal text to remove.

### Pitfall 3: Assuming the mypy override blocks in current `pyproject.toml` are all Phase 23 work
**What goes wrong:** Corrected doc text implies Phase 23 built the full current override list (7 `[[tool.mypy.overrides]]` blocks covering ~35 first-party subpackages), when Phase 23's own plan only specified the third-party `ignore_missing_imports` block.
**Why it happens:** Looking only at current `pyproject.toml` state without cross-referencing what `23-01-PLAN.md` actually scoped.
**How to avoid:** Describe the mechanism generically (global strict + per-module override pattern) without claiming Phase 23 alone authored every override currently present.

## Environment Availability

No external tool/service dependencies for this phase — all three items operate on files already present in the repository (test files, a YAML config, a markdown doc). `uv run pytest --collect-only` was used locally to reproduce/confirm the collection failure; this is already a documented project command (see root `CLAUDE.md`), not a new dependency.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv / pytest | Verifying test deletion doesn't break collection | Yes | project-standard (see `CLAUDE.md`) | — |
| pytest-cov | CI coverage step (`.github/workflows/test.yml`) | Not declared in `pyproject.toml`/lockfile (pre-existing gap, out of scope) | — | Not this phase's concern; flagged for awareness only |

**Missing dependencies with no fallback:** None blocking this phase.
**Missing dependencies with fallback:** None applicable.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x (`pytest>=9.0` in `pyproject.toml` dev deps), `asyncio_mode = "auto"` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_trust_center.py -q` |
| Full suite command | `uv run pytest tests/ --ignore=tests/load -m "not load"` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HYG-01 | Full suite collects and runs with zero `ModuleNotFoundError`s after deleting the two broken files | smoke / collection | `uv run pytest tests/ --collect-only -q --ignore=tests/load` | ✅ (existing test tree; verification is absence of the two deleted files, not a new test) |
| TRUST-01 | `/v1/trust/*` endpoints return 200 (not 404) when app starts with the shipped `config/trust_center.yaml` | integration | `uv run pytest tests/test_trust_center.py -q` (existing suite; no new test needed — this phase doesn't change router/service logic, only the config default) | ✅ `tests/test_trust_center.py` |
| HYG-02 | Documentation text accuracy | manual-only (no automated test possible for prose content) | N/A — reviewed by human/planner reading the corrected `23-01-SUMMARY.md` against `pyproject.toml` | N/A |

### Sampling Rate
- **Per task commit:** run the affected file's quick command (e.g., `uv run pytest tests/test_trust_center.py -q` after the YAML flip; `uv run pytest tests/ --collect-only -q --ignore=tests/load` after the deletions).
- **Per wave merge:** full suite (`uv run pytest tests/ --ignore=tests/load -m "not load"`) — expect the previously-documented pre-existing flake `tests/policy/test_property.py::test_tenant_isolation` (Hypothesis timing) to still be present; it is unrelated to this phase (see milestone audit "Test Suite Signal") and should not block this phase's commits.
- **Phase gate:** full suite green (modulo the known pre-existing flake) before `/gsd-verify-work`.

### Wave 0 Gaps
None — existing test infrastructure (`tests/test_trust_center.py`, the full pytest collection mechanism) already covers all three phase requirements. No new test files are needed for a deletion, a one-line config flip already covered by existing tests, or a documentation edit.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Trust Center is intentionally no-auth by design (Phase 24 D9) — unchanged by this phase |
| V3 Session Management | No | Not applicable to this phase's changes |
| V4 Access Control | Marginal | Trust Center's only access control is the `enabled` gate (404 when off) plus rate limiting — both already implemented and verified unaffected (D-06); this phase changes the *default value* of the gate, not the gate mechanism itself |
| V5 Input Validation | No | No new input paths introduced |
| V6 Cryptography | No | Not applicable |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Enabling a previously-off public endpoint surface increases exposure | Information Disclosure | Already mitigated by existing design: aggregate-only responses (Phase 24 D11), rate limiting (60 RPM/IP, D-06 confirms unaffected), fail-closed-503 (D-06 confirms unaffected). This phase does not need to add new mitigations — it activates an already-hardened feature. |
| Deleting test files could mask a future real regression if the deleted names are ever reused for legitimate modules | Tampering (process risk, not code risk) | D-03 explicitly forbids resurrecting `anonreq.agent.approval/.policy/.inspector/.registry` in this phase; if a future phase builds this capability for real, it must write new tests against real code, not resurrect these files, since these tests encode an API shape that was never implemented or reviewed |

No new threat surface is introduced by this phase; it either removes dead code paths or activates an already-reviewed, already-hardened feature via a default-value change.

## Sources

### Primary (HIGH confidence)
- Direct file reads: `tests/test_agent_approval.py`, `tests/test_agent_policy.py`, `src/anonreq/trust_center/config.py`, `src/anonreq/trust_center/router.py`, `src/anonreq/trust_center/service.py`, `src/anonreq/main.py` (lifespan block), `config/trust_center.yaml`, `tests/test_trust_center.py`, `pyproject.toml`, `.github/workflows/test.yml`, `.planning/phases/23-engineering-hygiene/{CONTEXT.md,23-01-PLAN.md,23-01-SUMMARY.md}`
- Live command execution: `uv run pytest tests/test_agent_approval.py tests/test_agent_policy.py --collect-only -q` (reproduced the exact `ModuleNotFoundError`s)
- `ls src/anonreq/agent/`, `ls src/anonreq/middleware/` (confirmed non-existent modules)
- `grep` across `.github/`, `.planning/phases/23-engineering-hygiene/` (confirmed no CI references, confirmed "staged" phrase absent)

### Secondary (MEDIUM confidence)
- `.planning/v1.5-MILESTONE-AUDIT.md` — source of the original findings driving this phase; treated as directional but not verbatim-accurate for the "staged rollout" quote (see Item 3 discrepancy note)

### Tertiary (LOW confidence)
- None

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pytest-cov` resolves transitively in CI via some other dev dependency (not independently verified how) | Item 1, coverage-gate risk note | Low — this is flagged as out-of-scope/pre-existing, not a claim this phase's plan depends on |

**If this table is empty:** N/A — one low-risk assumption logged above; it does not affect any of the three locked decisions or their planning.

## Open Questions

1. **Should the corrected `23-01-SUMMARY.md` wording go in the existing "Accomplishments" bullets, or a new subsection?**
   - What we know: D-07 only requires the text to become accurate; Claude's Discretion covers exact phrasing.
   - What's unclear: Whether the planner prefers editing the top-line summary sentence (line 40) vs. adding to "Accomplishments" (lines 50-53) vs. both.
   - Recommendation: Planner should treat this as a single small-diff task — edit the summary line and/or add one Accomplishments bullet describing the actual mypy override mechanism (see verbatim `pyproject.toml` facts in Item 3 above) — either location satisfies D-07's intent.

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new stack, this is a cleanup phase
- Architecture: HIGH — every claim in this document was verified by direct file read or command execution against the live repository, not inferred
- Pitfalls: HIGH — all three pitfalls are grounded in specific file/line evidence gathered during this research session

**Research date:** 2026-07-12
**Valid until:** Effectively indefinite for this phase's scope (file deletions/config flip/doc edit do not go stale) — but should be re-verified if any of the three target files change again before this phase executes.
