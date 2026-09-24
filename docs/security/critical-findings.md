# AnonReq — Critical Findings: Detailed Analysis & Fixes

**Date:** 2026-09-06
**Scope:** the 9 critical/high findings from `CODE_REVIEW.md` and `SECURITY_SCAN.md` (both dated 2026-07-17, self-authored), re-verified against current `main` (last push 2026-08-16).
**Method:** remote read of current `main` sources (`middleware/policy.py`, `dependencies.py`, `admin/auth.py`, `pipeline/provider.py`), repo tree, and test inventory. No code executed.

## Status summary

| # | Finding | Status on current `main` |
|---|---------|--------------------------|
| 1 | Non-timing-safe API key comparison (`dependencies.py`) | ✅ Fixed + regression test (`tests/test_security_regression.py`) |
| 2 | Admin legacy API key comparison (`admin/auth.py`) | ✅ Fixed + regression test (`tests/test_security_regression.py`) |
| 3 | Tenant isolation bypass (`middleware/policy.py`) | ✅ Fixed — fail-secure 503, `ANONREQ_SINGLE_TENANT` opt-in, ordering assertion, `tests/test_tenant_isolation.py` |
| 4 | Provider error details leaked (`pipeline/provider.py`) | ✅ Fixed + regression test (`tests/test_security_regression.py`) |
| 5 | Unauthenticated routers (`/metrics`, PAC, license, trust-center) | ✅ Fixed — `/metrics` auth-by-default + `ANONREQ_METRICS_NO_AUTH` hatch; trust-center `enabled: false`; PAC documented public-by-design (admin custom-rules gated); license already admin-gated, metadata-only |
| 6 | Monolithic lifespan in `main.py` + untyped `app.state` | ✅ Fixed — lifespan delegates to `bootstrap/services.py` + typed `AppState`; added ordering assertion, sabotaged-dependency startup test, prod secrets refusal (`tests/test_startup_failsecure.py`) |
| 7 | Hardcoded/default credentials in compose | ✅ Fixed — pinned images, non-root `anonreq` user, prod-mode default-credential refusal |
| 8 | Scan CRITICAL: live keys in `.env` | ⚠️ Not a repo finding — no `.env` committed (gitignored, untracked); local `.env` key must still be rotated |
| 9 | No end-to-end anonymization round-trip test | ✅ Fixed — `tests/integration/test_e2e_round_trip.py` covers full pipeline + split-token streaming + cache-failure fail-secure |

> See [Report staleness](#report-staleness) for why `CODE_REVIEW.md` / `SECURITY_SCAN.md` overstate current risk.

---

## Finding 1 — Non-timing-safe API key comparison ✅ FIXED

**Was:** `src/anonreq/dependencies.py` compared the bearer token with `!=`, leaking key-prefix information via response-time differences — a practical attack against a network-facing gateway (time many requests, recover the key byte-by-byte).

**Now:** current code uses `hmac.compare_digest(token, settings.API_KEY or "")`. Constant-time and correct, including the `or ""` guard against a `None` setting.

**No code fix needed.** Recommended follow-up only: add a regression test (e.g. in `tests/test_auth.py`) asserting the `compare_digest` path — mock `hmac.compare_digest` and prove verification routes through it — so a future refactor cannot silently reintroduce `!=`.

**Done 2026-09-06:** regression tests added in `tests/test_security_regression.py` (`TestTimingSafeApiKeyComparison` — routes through `compare_digest` + source guard against bare `!=`). All 7 tests pass.

**Verify:** `grep -n "compare_digest" src/anonreq/dependencies.py`.

---

## Finding 2 — Admin legacy API key comparison ✅ FIXED

**Was:** `src/anonreq/admin/auth.py`, same timing-side-channel class as Finding 1, on the higher-privilege admin surface.

**Now:** the legacy fallback path uses `hmac.compare_digest(token, settings.ADMIN_API_KEY or "")`, and the primary path is OIDC/JWT via JWKS (`build_oidc_verifier`). Sound layering: strong default, compatibility fallback.

**No code fix needed.** Residual cleanup note (not a vulnerability): `get_admin_api_key()` is a needless `async` one-liner returning config — harmless overhead, remove `async` when nearby code is touched.

**Done 2026-09-06:** verified already sync (`def get_admin_api_key()` — no `async` remains); regression tests added in `tests/test_security_regression.py` (`TestAdminLegacyKeyComparison` — source guard + wrong-key 401). All pass.

**Verify:** `grep -n "compare_digest" src/anonreq/admin/auth.py`.

---

## Finding 3 — Tenant isolation bypass in `PolicyMiddleware` ✅ FIXED 2026-09-06

**Was (report):** the middleware constructed `ProcessingContext(tenant_id="default")`, bypassing multi-tenancy entirely.

**Was (residual until 2026-09-06):** `_extract_tenant_id()` read `request.state.tenant_id` but fell back to `return "default"` — fail-open for tenancy.

**Fix applied:**
1. `_extract_tenant_id()` now returns `None` when tenant context is missing; `dispatch()` fails secure with HTTP 503 + `X-AnonReq-Blocked: true` (mirroring the PDP/PEP error handling), and the PDP is never evaluated.
2. `"default"` fallback survives only behind explicit `ANONREQ_SINGLE_TENANT=true` (new `Settings.SINGLE_TENANT`, documented in `.env.example`), validated/logged at startup via `validate_single_tenant_mode()`.
3. `assert_middleware_ordering()` in `startup_checks.py` fails fast if `TenantContextMiddleware` is ever reordered after `PolicyMiddleware`; called from the lifespan before accepting traffic.

**Tests added (`tests/test_tenant_isolation.py`):**
- Request with no `request.state.tenant_id` → 503 + `X-AnonReq-Blocked`, PDP never runs.
- `ANONREQ_SINGLE_TENANT=true` → explicit `"default"` fallback, request proceeds.
- Two tenants with divergent policies → 403 vs 200 (per-tenant enforcement, no leakage).

**Was (report):** the middleware constructed `ProcessingContext(tenant_id="default")`, bypassing multi-tenancy entirely.

**Now:** `_extract_tenant_id()` reads `request.state.tenant_id`, populated by `TenantContextMiddleware` per D-03 — genuine remediation. **But the fallback is still `return "default"`.**

**Why the residual matters:** if `TenantContextMiddleware` is misordered, skipped for a path, or raises before setting state, every request silently evaluates under tenant `"default"`. That is fail-open for tenancy — cross-tenant policy leakage with no alarm. In a product selling GDPR/compliance presets, silent wrong-tenant evaluation is worse than a loud 503.

**Fix:**
1. Replace the `"default"` fallback with fail-secure: log `tenant.missing` and return HTTP 503 with `X-AnonReq-Blocked: true`, mirroring the existing PDP/PEP error handling in the same `dispatch()`.
2. Keep `"default"` only behind an explicit single-tenant mode flag (e.g. `ANONREQ_SINGLE_TENANT=true`), validated at startup in `startup_checks.py`, so the behavior is a conscious deployment choice rather than a silent accident.
3. Add a startup assertion on middleware ordering (tenant context before policy), or collapse tenant extraction into `auth_context` so it cannot be skipped independently.

**Tests to add:**
- Request with no `request.state.tenant_id` → expect 503, never 200.
- Two tenants with divergent policies → decisions differ per tenant (no such test exists; `tests/policy/` is unit-level only).

**Verify:** read `_extract_tenant_id` in `src/anonreq/middleware/policy.py`; confirm no `return "default"` remains.

---

## Finding 4 — Provider error details leaked upstream internals ✅ FIXED

**Was:** `error_detail = str(error_body)[:200]` echoed into client-facing errors — upstream stack traces, paths, or PII reflected to callers.

**Now:** client messages are generic (`"Provider returned HTTP {status}"`, `"Upstream provider timeout"`, `"Provider unavailable"`); only `error_type` is logged server-side. Additionally, `follow_redirects=False` is set on the shared `httpx.AsyncClient`, which also closes scan item #5 (redirect-based SSRF).

**No code fix needed.** Suggested hardening: a test asserting `PipelineAbortError.message` never contains substrings of a stubbed upstream body — a one-test guard against regression.

**Done 2026-09-06:** hardening tests added in `tests/test_security_regression.py` (`TestProviderErrorGeneric` — stubbed upstream stack-trace/PII body never reaches the client message; `follow_redirects=False` asserted; source guard against `error_body` interpolation). All pass.

**Verify:** read `execute()` in `src/anonreq/pipeline/provider.py`; confirm no `error_body` interpolation into client messages.

---

## Finding 5 — Unauthenticated routers ✅ FIXED 2026-09-06

**Claim (report):** `/metrics` (tenant/entity counts), the PAC file (network position), and the license and trust-center routers are mounted without `Depends(auth_context)`.

**Re-check + fix applied (code read 2026-09-06):**
- `/metrics`: was public. Now requires `auth_context` by default; `ANONREQ_METRICS_NO_AUTH=true` escape hatch only for Prometheus-behind-sidecar topologies (startup warning logged, documented in `.env.example`). `tests/integration/test_metrics_endpoint.py` updated: authenticated scrapes return 200, unauthenticated returns 401.
- PAC (`GET /v1/proxy.pac`): public by design — serves only gateway routing topology (proxy host/port + AI domains), never credentials. Admin custom-rules endpoints were already admin-gated via `verify_admin_api_key`. Documented in `main.py` mount comment.
- Trust-center (`/v1/trust/*`): public by design (attestation metadata only, rate-limited, config-gated). Default flipped to `enabled: false` in `config/trust_center.yaml` (code default was already `False`); bootstrap logs the effective state.
- License (`GET /v1/admin/license`): already gated — router-level `Depends(_admin_auth)` → `require_auth`, and `LicenseStatus` returns only validity/tier/features/expiry/organization, never key material. No change needed.

**Claim (report):** `/metrics` (tenant/entity counts), the PAC file (network position), and the license and trust-center routers are mounted without `Depends(auth_context)`.

**Why it matters:** metrics with per-tenant entity counts are a cross-tenant oracle; PAC files map internal proxy topology. "Secured at network level" is assumed, not enforced — one misconfigured ingress exposes them.

**Fix (per router):**
- `/metrics`: require auth by default; add an `ANONREQ_METRICS_NO_AUTH=true` escape hatch only for Prometheus-behind-sidecar topologies, documented in `.env.example` with a production warning.
- PAC: same treatment, or serve it from the proxy component rather than the API app.
- Trust-center: keep public-by-design but default `enabled: false` in `trust_center.yaml`, with a startup log line stating its state.
- License: return only boolean validity plus expiry — never keys or customer identifiers.

**Verify:** read the router mounts in `src/anonreq/main.py` (~lines 760–810) and confirm `dependencies=[Depends(auth_context)]` on each. This finding has **not** yet been re-checked against current code.

---

## Finding 6 — Monolithic lifespan in `main.py` ✅ FIXED 2026-09-06

**Claim (report):** ~440-line lifespan function, 15+ initialization concerns, inconsistent error handling; all runtime state in an untyped `app.state` bag accessed via `getattr`.

**Re-check 2026-09-06:** the decomposition the report asked for already exists — lifespan delegates to one bootstrapper per domain in `bootstrap/services.py`, and `state.py` provides the typed `AppState` container with backward-compatible flat access. Remaining work applied:
1. Lifespan calls `assert_middleware_ordering(app)` before accepting traffic (fail-fast on tenant/policy misordering).
2. `run_startup_checks` now also runs `validate_single_tenant_mode()` (logs effective tenancy mode) and `validate_production_secrets()` (refuses prod boot with unset/default credentials).
3. Added `tests/test_startup_failsecure.py`: sabotaged Valkey → `DependencyUnavailableError` (never serves); ordering assertion accepts production order / rejects inverted; prod secrets gate blocks defaults in production, stays permissive in development.

**Claim (report):** ~440-line lifespan function, 15+ initialization concerns, inconsistent error handling; all runtime state in an untyped `app.state` bag accessed via `getattr`.

**Why it matters:** every new phase appends another try/except; startup/shutdown paths are untested, so an init-order bug can silently leave a stage unconfigured while the gateway serves traffic — the exact failure mode a fail-secure product must not have.

**Fix:**
1. Extract one bootstrapper per domain (`bootstrap/cache.py`, `bootstrap/detection.py`, `bootstrap/policy.py`, …), each exposing `async def init(state)` and `async def close(state)`; the lifespan becomes a ~30-line ordered loop over a registry. (A `bootstrap/` package already exists — extend it rather than adding new top-level structure.)
2. Introduce a typed `AppState` dataclass replacing `app.state.*` + `getattr`. `get_app_state()` already exists in `src/anonreq/state.py` — extend it to construct and validate the whole state object at startup so misconfiguration fails fast with a single error.
3. Add a lifespan test: startup with a sabotaged dependency (e.g. unreachable Valkey) must 503 — never serve.

**Verify:** line-count `create_app`/lifespan in `src/anonreq/main.py`; grep `app.state.` versus typed accessors.

---

## Finding 7 — Hardcoded/default credentials in compose ✅ FIXED 2026-09-06

**Claim (report):** MinIO `minioadmin:minioadmin`, Postgres `anonreq:anonreq`, `user: root` with a runtime `su` privilege drop; unpinned `latest` images for Presidio and MinIO.

**Fix applied (`docker-compose.yml`):**
1. Pinned `mcr.microsoft.com/presidio-analyzer:2.2.354`, `minio/minio:RELEASE.2025-04-22T22-12-26Z`, `valkey/valkey:8.0` (postgres/prometheus/grafana/exporters were already pinned).
2. Replaced `user: root` + runtime `su anonreq` with `user: "1001:1001"` and a direct `uvicorn` command — the `Dockerfile` already creates the `anonreq` user, chowns `/app` at build time, and runs as `USER anonreq`.
3. Production guard: `ANONREQ_ENV=production` + unset/default `PROVIDER_API_KEY` / `MINIO_ROOT_*` / `POSTGRES_PASSWORD` → startup refusal via `validate_production_secrets()`; `ANONREQ_ENV`, `ANONREQ_SINGLE_TENANT`, `ANONREQ_METRICS_NO_AUTH` wired through compose with safe defaults.

**Claim (report):** MinIO `minioadmin:minioadmin`, Postgres `anonreq:anonreq`, `user: root` with a runtime `su` privilege drop; unpinned `latest` images for Presidio and MinIO.

**Why it matters:** these are the first credentials an attacker tries; root-then-drop widens the window for startup-script exploitation; floating tags import upstream breakage and CVEs silently.

**Fix:**
1. Source all secrets from env with startup validation — refuse to boot in production mode (`ANONREQ_ENV=production`) when default credentials are detected.
2. Replace `user: root` + `su` with build-time `chown` and `USER anonreq` in the `Dockerfile`.
3. Pin `presidio-analyzer` and `minio` image tags; add Dependabot or Renovate for automated updates.

**Verify:** read `docker-compose.yml` and `Dockerfile`; attempt a boot with defaults in prod mode and expect refusal.

---

## Finding 8 — The scan's CRITICAL (`.env` with live keys) ⚠️ NOT A REPO FINDING

**Claim (report):** `.env` lines 6/8/12 contain real `sk-proj-…` keys — rated CRITICAL.

**Fact:** no `.env` exists in the repo tree — only `.env.example` is committed, and `.gitignore` is present. A committed-`.env` CRITICAL cannot apply to repository state; at most it describes a local working copy.

**Verified 2026-09-06:** `git ls-files` shows no tracked `.env` (only `.env.example`); `.gitignore:39` covers `.env`. A local `.env` DOES exist in the working copy and contains 1 `sk-proj`-pattern line — if that key was ever real and ever pushed, rotate it regardless of tree state.

**Action:**
1. Confirm `.gitignore` covers `.env` and that history never contained it: `git log --all -- .env`.
2. If the keys were ever real and ever pushed, rotate them regardless of current tree state.
3. Correct or retract the report entry — a security report whose headline finding does not match the repo trains readers to discount the rest. See [Report staleness](#report-staleness).

---

## Finding 9 — No end-to-end anonymization round-trip test ✅ FIXED 2026-09-06

**Claim (report):** stage-level and property tests exist, but nothing sends PII through the full pipeline — detect → tokenize → forward → restore — asserting the client gets originals back while upstream saw only tokens.

**Re-check 2026-09-06:** the gap is closed — `tests/integration/test_e2e_round_trip.py` already covers PII-tokenized-before-provider, echo-restore, cache cleanup, regex+NER detection, mapping/detection correspondence, and provider-error fail-secure (incl. no-PII-in-error-path). Extended 2026-09-06 with the report's missing cases:
1. `TestStreamingSplitToken`: token split across two SSE chunks through `TailBuffer` + `StreamingRestorationStage` restores the original with no residual token.
2. `TestCacheFailureFailsSecure`: killed cache (writes raise) → 5xx **and** the upstream mock receives nothing, no restored response.
3. Tenant wrong-context blocking is covered at the middleware layer by `tests/test_tenant_isolation.py` (ties to Finding 3).

**Claim (report):** stage-level and property tests exist, but nothing sends PII through the full pipeline — detect → tokenize → forward → restore — asserting the client gets originals back while upstream saw only tokens.

**Why it matters:** this is the product's entire promise, and integration of individually correct stages can still leak (wrong body forwarded, mapping TTL race, streaming tail-buffer edge).

**Fix — add `tests/integration/test_full_roundtrip.py`:**
1. Fake upstream (httpx `MockTransport` or respx) capturing the exact forwarded body; assert no raw PII is present — only `[TYPE_N]` tokens.
2. Fake upstream response echoing tokens back, including a token split across two SSE chunks; assert the client response contains the originals.
3. Negative cases: kill fakeredis mid-request → expect 5xx **and** assert the upstream mock received nothing; wrong-tenant request → blocked, never default-evaluated (ties to Finding 3).
4. Mark slow/Presidio-dependent variants; keep a regex-only fast path for CI.

**Verify:** the file exists, and fails if `transformed_request` is swapped for `original_request` (mutation check proving it guards the invariant).

---

## Suggested execution order

> Completed 2026-09-06. All items below are done and verified (see status
> table); `tests/test_auth.py`-style coverage lives in the new
> `tests/test_security_regression.py`, `tests/test_tenant_isolation.py`,
> and `tests/test_startup_failsecure.py`, plus extensions to
> `tests/integration/test_e2e_round_trip.py` and
> `tests/integration/test_metrics_endpoint.py`.

1. **Finding 3 → Finding 9 together:** ~~write the tenant test first, watch it fail, then fix the fallback. Then the round-trip test.~~ Done.
2. **Finding 5:** ~~router auth audit (`main.py` mounts).~~ Done.
3. **Finding 7:** ~~compose/docker credential hygiene.~~ Done.
4. **Finding 6:** ~~structural — lifespan decomposition, last.~~ Done (decomposition pre-existed; added ordering assertion + startup tests + prod gate).
5. Findings 1, 2, 4 ~~need only the regression tests noted above.~~ Done.
6. Finding 8 is process hygiene alongside everything else. Done (verified untracked; rotate the local `sk-proj` key if real).

---

## Report staleness

`CODE_REVIEW.md` and `SECURITY_SCAN.md` are dated 2026-07-17 and self-authored ("opencode automated review"). Since then, pushes continued to 2026-08-16, and at least four of their findings were remediated in code without the reports being updated:

- S-1 (timing-safe API key comparison) — fixed, see Finding 1.
- S-2 (admin key comparison) — fixed, see Finding 2.
- C-5 (provider error body leak) — fixed, see Finding 4.
- Scan item #5 (`follow_redirects`) — fixed, see Finding 4.

**Recommendation:** treat both reports as historical snapshots. Track each open item as a GitHub issue, update the reports (or mark them superseded by this document), and adopt a rule: automated-review reports expire after 30 days or 50 commits, whichever comes first. A security product with 0 open issues and stale green reports is less trustworthy than one with 20 open, triaged issues.
