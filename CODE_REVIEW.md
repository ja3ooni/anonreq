# CODE_REVIEW.md — AnonReq Gateway

**Date:** 2026-07-17
**Reviewer:** opencode automated review
**Scope:** Full codebase review of `src/anonreq/`

---

## 1. Project Overview

**What it does:** AnonReq is a self-hosted AI security and anonymization gateway for regulated enterprises. It sits between enterprise applications and LLM APIs, detects/replaces PII with `[TYPE_N]` tokens, forwards sanitized requests, restores tokens in responses, and provides enterprise-tier AI traffic governance, DLP, SOC/SIEM integration, and compliance controls.

**Tech stack:** Python 3.12, FastAPI, Pydantic Settings v2, httpx, Redis/Valkey (async), Presidio Analyzer, prometheus-client, structlog, SQLAlchemy/Alembic, MinIO, cryptography, pytest/Hypothesis, Docker Compose.

**Maturity level:** Alpha (v0.1.0). Substantial implementation (~52,100 LOC across 346 source files in 111 modules), 286 test files, 28 config files, multiple enterprise phases implemented through Phase 26. However, many type-safety overrides exist (mypy `disable_error_code` lists are extensive), 52 ruff lint issues remain, and the codebase shows signs of rapid phased development without consolidation passes.

---

## 2. Code Quality Findings

### Critical

| # | Finding | File | Line |
|---|---------|------|------|
| C-1 | **Policy engine swallows startup failure differently** — If policy engine init fails, the app raises the exception and shuts down. But the `except Exception` block at line 399 logs `error=str(exc)` which may contain internal details. More importantly, this catch-all means *any* import error (including typos) in the policy module kills the entire gateway at startup with no way to run in degraded mode. | `src/anonreq/main.py` | 399 |
| C-2 | **Monolithic lifespan function** — The `create_app()` lifespan is ~440 lines of imperative setup code (lines 249-719). This is extremely difficult to test, maintain, or reason about. Each phase added new `try/except` blocks, creating deeply nested initialization with inconsistent error handling. | `src/anonreq/main.py` | 249-719 |
| C-3 | **`PolicyMiddleware` constructs a `ProcessingContext` with hardcoded `tenant_id="default"`** — This bypasses the entire tenant isolation model. Every request through the policy middleware gets `tenant_id="default"` regardless of the authenticated principal's tenant. | `src/anonreq/middleware/policy.py` | 35-38 |
| C-4 | **API key comparison is not timing-safe** — `verify_api_key()` uses `!=` to compare the bearer token against `settings.API_KEY`. This is vulnerable to timing side-channel attacks. Should use `hmac.compare_digest()`. | `src/anonreq/dependencies.py` | 67 |
| C-5 | **`ProviderStage` error messages leak provider error details** — Error messages include truncated provider response bodies (`error_detail = str(error_body)[:200]`), which may contain internal paths, stack traces, or PII from the upstream provider. | `src/anonreq/pipeline/provider.py` | 131-138 |

### Warning

| # | Finding | File | Line |
|---|---------|------|------|
| W-1 | **Duplicate `Role.READ_ONLY` alias** — `Role.READ_ONLY = "read_only_auditor"` creates an alias that collides with `READ_ONLY_AUDITOR`. The `_normalize_role_value` function handles `"read_only"` → `READ_ONLY_AUDITOR` mapping, but the enum member itself is redundant and confusing. | `src/anonreq/middleware/rbac.py` | 23 |
| W-2 | **`allowlist_processor` has an incomplete allowlist** — The `ALLOWLIST` in `logging_config.py` does not include `error`, `mode`, `version`, `component`, or `deployment_mode` fields that are frequently logged throughout the codebase. These fields will be silently dropped. | `src/anonreq/logging_config.py` | 36-71 |
| W-3 | **`_redact_value` is not recursive into all container types** — It handles `dict`, `list`, `tuple`, and `set`, but not nested dataclass or Pydantic model instances. If a Pydantic model ends up in a log field, its internals could leak. | `src/anonreq/logging_config.py` | 88-99 |
| W-4 | **`SpanArbiter.merge()` mutates input lists** — The `_source` tag is set directly on the input dicts (`r["_source"] = "regex"`), mutating caller-owned data. The tag is cleaned up at the end, but if an exception occurs between tagging and cleanup, the `_source` key persists. | `src/anonreq/detection/span_arbiter.py` | 52-56 |
| W-5 | **Hardcoded `max_concurrency=10` for Presidio client** — The Presidio client's semaphore is hardcoded at line 341 of `main.py` rather than being configurable via settings. This limits tuning for high-throughput deployments. | `src/anonreq/main.py` | 341 |
| W-6 | **`CacheManager.__init__` creates a redis client but `CacheManager` also has `__new__`-based construction in tests** — The test fixture (`conftest.py:92-94`) bypasses `__init__` via `__new__`, which means any future `__init__` changes could silently break tests. | `tests/conftest.py` | 92-94 |
| W-7 | **`build_pre_provider_pipeline` reconstructs locale infrastructure on every streaming request** — When `locale_negotiator` is `None`, a full `LocaleRegistry` is instantiated. In `chat.py:255-261`, the streaming path passes `None` for locale args, creating fresh instances each time. | `src/anonreq/routing/chat.py` | 255-261 |
| W-8 | **Ruff reports 52 lint issues** — 22 auto-fixable, including import sorting, unnecessary key checks, and nested `if` statements. Not critical but indicates code hygiene gaps. | (multiple) | — |

### Info

| # | Finding | File | Line |
|---|---------|------|------|
| I-1 | **`_network_proxy_autostart_enabled()` re-imports `os`** — `os` is already imported at the module level (line 18). The local import on line 141 is redundant. | `src/anonreq/main.py` | 141 |
| I-2 | **README directory structure is stale** — Shows `config.py` as a single file (`src/anonreq/config.py`), but the actual structure is a `config/` package with `__init__.py`. Several other directories listed in README don't match the actual structure. | `README.md` | 49-51 |
| I-3 | **`health.py` references `check_presidio` from `startup_checks`** — This creates a circular conceptual dependency (health endpoint imports startup checks which imports health checks). The function should live in a shared health module. | `src/anonreq/health.py` | 16 |
| I-4 | **`admin/auth.py` returns `str | None` from `get_admin_api_key`** — An `async` function that just returns a config value. The `async` is unnecessary and adds overhead. | `src/anonreq/admin/auth.py` | 85-87 |

---

## 3. Architecture Review

### Strengths

1. **Well-defined pipeline pattern** — The `PipelineManager` with `PipelineStage` base class is clean and extensible. Stages are registered in order, each can abort the pipeline, and the fail-secure invariant is enforced at the manager level.

2. **Token contract is rigorously defined** — The `[TYPE_N]` token format, reverse-offset replacement, deduplication, and case-insensitive/bracket-optional restoration are well-specified and tested with property-based tests.

3. **Log allowlist is a strong security pattern** — The `ALLOWLIST` approach (deny by default, allow known fields) is excellent for preventing PII leakage through logs. The `redact_secret_substrings_processor` adds defense-in-depth.

4. **Fail-secure error handling** — The exception hierarchy (`AnonReqError` → `PipelineAbortError`, `PipelineBlockedError`, etc.) with the global exception handler ensures no internal details leak to clients.

5. **Ephemeral secret management** — The `RuntimeSecretStore` with context-var scoping for per-request secret isolation is well-designed.

6. **Good property-based test coverage** — 15 property test files covering streaming invariants, fail-secure, locale checksums, compliance, and fairness.

### Concerns

1. **God object: `main.py`** — At 839 lines, `create_app()` is doing too much. The lifespan function alone is ~440 lines handling 15+ initialization concerns. This should be decomposed into init modules per domain (cache, detection, policy, SOC, trust center, etc.).

2. **`app.state` as a typeless bag** — All runtime state is attached to `app.state` without typing or documentation. There's no `AppState` model. Components access `app.state.pdp`, `app.state.pep`, `app.state.soc_normalizer`, etc. via `getattr` with no type checking. This is a maintenance hazard.

3. **Mixed async patterns** — `CacheManager` uses `redis.asyncio`, `ProviderStage` uses lazy `httpx.AsyncClient`, `PresidioClient` uses lazy `httpx.AsyncClient` with semaphore. There's no unified client lifecycle management — clients are created lazily and closed manually.

4. **Configuration proliferation** — 28 YAML config files in `config/`, plus 50+ env vars, plus Alembic, plus Docker Compose env vars. Many are loaded with hardcoded paths (`config/enterprise-policy.yaml`, `config/slo.yaml`, `config/webhook.yaml`, etc.) that aren't configurable.

5. **`PolicyMiddleware` doesn't integrate with auth** — It constructs its own `ProcessingContext` with hardcoded tenant, bypassing the authenticated principal. This means policy enforcement is effectively single-tenant.

6. **Streaming rebuilds entire pipeline per request** — `_stream_chat_completions` calls `build_pre_provider_pipeline()` on every request, creating fresh `ClassificationEngine`, `ExclusionList`, `SpanArbiter`, etc. objects. This is wasteful and may have subtle state bugs.

7. **No dependency injection framework** — All dependencies are manually wired through `app.state` or function parameters. FastAPI's `Depends()` is used only for auth. A proper DI container or at least typed state models would improve testability.

---

## 4. Security Concerns

### High

| # | Finding | Severity | File |
|---|---------|----------|------|
| S-1 | **Timing-safe comparison missing for API key** | High | `src/anonreq/dependencies.py:67` |
| S-2 | **Admin legacy API key comparison is not timing-safe** | High | `src/anonreq/admin/auth.py:66` |
| S-3 | **Docker Compose runs as `user: root` then drops to `anonreq`** | Medium | `docker-compose.yml:72` |
| S-4 | **Postgres credentials hardcoded in docker-compose** | Medium | `docker-compose.yml:131-133` |
| S-5 | **MinIO default credentials `minioadmin:minioadmin` in docker-compose and .env.example** | Medium | `docker-compose.yml:171-172`, `.env.example:26-29` |
| S-6 | **Provider error body truncation may leak secrets** | Medium | `src/anonreq/pipeline/provider.py:131-133` |

### Medium

| # | Finding | Severity | File |
|---|---------|----------|------|
| S-7 | **`/metrics` endpoint is unauthenticated** — Prometheus scrapers connect on internal networks, but the comment says "secured at network level". If the network boundary is misconfigured, metrics (including request counts, latencies, and entity counts by tenant) are exposed. | Medium | `src/anonreq/main.py:764` |
| S-8 | **PAC file endpoint is unauthenticated** — `pac_router` is included without `Depends(auth_context)`. The PAC file reveals all proxy domains and the gateway's network position. | Medium | `src/anonreq/main.py:804` |
| S-9 | **Trust Center router is unauthenticated and config-gated** — Public access is by design, but `trust_center.yaml` controls enablement. If accidentally enabled in production, compliance evidence is publicly accessible. | Medium | `src/anonreq/main.py:807` |
| S-10 | **License router has no auth** — `license_router` is included without auth dependency. Depending on what it exposes, this could be an information leak. | Medium | `src/anonreq/main.py:801` |
| S-11 | **`open()` without explicit encoding in `providers/registry.py`** — `open(path)` without `encoding="utf-8"` relies on platform default. | Low | `src/anonreq/providers/registry.py:81` |
| S-12 | **`open()` without explicit encoding in `config/__init__.py`** | Low | `src/anonreq/config/__init__.py:222` |

### Low / Informational

- The `httpx.AsyncClient` instances are created without explicit `follow_redirects=False`, meaning SSRF via redirect is possible if a provider URL is attacker-controlled.
- `yaml.safe_load()` is correctly used throughout (no `yaml.load()` with `Loader=yaml.FullLoader`), which is good.
- The `SECRET_BACKEND` default is `"vault"`, but the fallback path creates an empty `RuntimeSecretStore()` which returns `None` for all key lookups. This is fail-secure (provider calls will fail with missing key errors).

---

## 5. Testing Coverage Assessment

### Well tested

- **Tokenization/Restoration:** Property-based tests for round-trip correctness, deduplication, cross-request randomization, case-insensitive/bracket-optional restoration.
- **Streaming:** `TailBuffer` FSM, split token handling, disconnect scenarios, reasoning leak prevention.
- **Fail-secure invariants:** `test_fail_secure.py` with Hypothesis strategies.
- **Locale/checksum:** Locale invariants, checksum validation, locale negotiation.
- **Pipeline integration:** Scan stages, DLP pipeline, tool governance.
- **Admin RBAC:** Role enforcement tests, OIDC admin gate.
- **27 integration tests** covering hot-reload, metrics, startup, compliance, breach, fairness, DSAR, etc.

### Missing or weak

| Gap | Impact |
|-----|--------|
| **No end-to-end test of the full anonymization round-trip** — Tests cover individual stages but there's no integration test that sends a request with PII through the full pipeline and verifies the response is correctly anonymized and restored. | High — Core value proposition unverified end-to-end. |
| **No test for timing-safe API key comparison** | Medium — Security regression possible. |
| **`PolicyMiddleware` tenant isolation untested** — The hardcoded `"default"` tenant is not covered by any test. | High — Tenant isolation is a core requirement (Req 33). |
| **No negative test for malformed Presidio responses** | Medium — Partial `PresidioClient` resilience untested. |
| **No load tests checked in** — `pyproject.toml` defines a `load` marker but `tests/load/` is not in the test paths. | Low — Concurrency behavior unverified. |
| **`CacheManager` Sentinel/Cluster paths untested** — Only standalone Redis is tested via fakeredis. | Medium — Production topology support unverified. |
| **`main.py` lifespan is untested** — No test covers the startup sequence, shutdown sequence, or error paths in the 440-line lifespan. | High — Startup/shutdown bugs could cause data loss. |

---

## 6. Dependency Health

### Concerns

| Dependency | Issue |
|------------|-------|
| `presidio-analyzer>=2.2.35` | Pulls in `onnxruntime` which is a heavy ML dependency. The `onnxruntime>=1.17.0` pin may conflict with Presidio's own requirements. |
| `openai-whisper>=20231117` | Optional voice dependency in `[voice]` extras. This pulls in `torch` (~2GB). Consider making it a separate install. |
| `redis>=8.0.0` | Redis-py 8.x is a major version bump from 7.x. The `redis.asyncio` API changes should be verified. |
| `reportlab>=4.3.0,<5.0.0` | Upper-bounded at <5.0.0, which is good practice. |
| `pyarrow>=15.0.0` | Very heavy dependency (Arrow C++ bindings) for what appears to be compliance export. Consider if this is truly needed in the core image. |
| `minio>=7.2.0` | MinIO SDK is included in core deps even though object storage is optional. Should be an optional dependency. |
| `h11>=0.16.0` | HTTP/1.1 protocol library. Unclear why this is a direct dependency — likely pulled in by `httpx` or `uvicorn` transitively. |

### Recommendations

- Move `minio`, `pyarrow`, `reportlab`, `onnxruntime`, `soundfile` to optional dependency groups (e.g., `[compliance]`, `[voice]`, `[multimodal]`).
- The `requirements.txt` (used by Docker) and `pyproject.toml` should be kept in sync. Currently they may drift.
- `setuptools<81` is pinned in the Dockerfile builder stage for whisper compatibility — this is a fragile workaround.

---

## 7. Documentation Gaps

| Gap | Details |
|-----|---------|
| **README directory structure is stale** | Shows `config.py` as a single file; actual structure is a `config/` package. Missing directories: `policy/`, `governance/`, `services/`, `proxy/`, `middleware/`, `classification/`, `compliance/`, `locale/`, `secrets/`, `trust_center/`, `soc/`, `multimodal/`, `firewall/`, `discovery/`, `endpoint/`, `mcp/`, `rag/`, `casb/`, `fairness/`, `voice/`, `lineage/`, `breach/`, `dsar/`, `retention/`, `storage/`. |
| **No API documentation** | OpenAPI spec exists at `openapi/openapi.yaml` but there's no rendered API docs (Swagger/ReDoc disabled: `docs_url=None, redoc_url=None` in `main.py:724-725`). |
| **Missing threat model document** | The codebase references threat model items (T-01-03-01, T-02-04-05, etc.) extensively but no consolidated threat model document exists. |
| **`config/` files undocumented** | 28 YAML config files with no schema documentation or examples beyond `policy.example.yaml` and `prompt-security-rules.example.yaml`. |
| **No deployment guide** | `docker/` directory exists but no deployment runbook. `docs/` directory exists but wasn't audited here. |
| **`SECURITY.md` not reviewed** | Present but not read in this review. Should be checked for responsible disclosure instructions. |
| **License router undocumented** | The license validation system (`LicenseValidator`, `require_license()`) has no user-facing documentation. |
| **Mypy strict mode is effectively disabled** | `pyproject.toml:93` sets `strict = true` but 8 module groups have extensive `disable_error_code` lists that suppress most errors. The strict mode provides no value in this configuration. |

---

## Summary of Priority Actions

1. **Fix timing-safe API key comparisons** (S-1, S-2) — Simple one-line fixes with high security value.
2. **Fix `PolicyMiddleware` tenant isolation** (C-3) — Extract tenant from auth context instead of hardcoding `"default"`.
3. **Decompose `main.py` lifespan** (C-2) — Extract init logic into domain-specific bootstrappers.
4. **Stop leaking provider error bodies** (C-5) — Remove or further truncate error details in `ProviderStage`.
5. **Add typed `AppState` model** — Replace freeform `app.state` attribute access with a dataclass/Pydantic model.
6. **Remove duplicate `Role.READ_ONLY`** (W-1) — Clean up the RBAC enum.
7. **Move optional heavy deps to extras** — `minio`, `pyarrow`, `reportlab`, `onnxruntime` should not be in core `dependencies`.
8. **Add end-to-end round-trip test** — Verify the core anonymization→forwarding→restoration flow.
9. **Fix ruff lint issues** — 52 issues, 22 auto-fixable with `ruff check --fix`.
10. **Update README directory structure** — Reflect the actual 111-module architecture.
