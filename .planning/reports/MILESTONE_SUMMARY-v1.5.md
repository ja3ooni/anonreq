# Milestone v1.5 — Project Summary

**Generated:** 2026-07-12
**Purpose:** Team onboarding and project review

---

## 1. Project Overview

AnonReq is a **self-hosted AI security and anonymization gateway for regulated enterprises**. It sits between enterprise applications and external or local LLM APIs, detects and replaces sensitive data (PII, PHI, financial identifiers, trade secrets) with context-preserving placeholder tokens, forwards sanitized requests, and restores original values in responses — all within the customer's secure perimeter. **Core value: raw PII never crosses the network boundary.**

- **v1.0** (shipped 2026-07-07) delivered the full platform: core anonymization pipeline, fail-secure architecture, hybrid PII detection (regex + NER), SSE streaming, multi-provider LLM support (OpenAI, Anthropic, Gemini, Ollama), multilingual detection (8 locales), enterprise policy engine, AI firewall/DLP, governance, financial services compliance, universal AI traffic gateway, SOC/SIEM integration, and sovereign AI control. ~49,500 lines of Python, 22 phases, 101 plans, 768+ tests.
- **v1.5 "Enterprise Hardening & Trust Center"** (this milestone, 2026-07-07 → 2026-07-09) turned code-review feedback (internally called "the MOTE") into production-ready practices: CI/CD and code-quality gating, a public Trust Center compliance portal, documentation parity across 8 languages, and commercial licensing with enterprise-grade detection.

All 4 phases (23–26) and all 10 requirements are complete and marked `SHIPPED` in the archived requirements doc.

## 2. Architecture & Technical Decisions

- **Decision:** GitHub Actions for CI/CD, single Python 3.12 target, `uv sync --group dev` for dependency management.
  - **Why:** Repo is already GitHub-hosted; project pins `>=3.12`; `uv` is the existing project convention.
  - **Phase:** 23 (Engineering Hygiene)
- **Decision:** `ruff` (rules `E,F,I,N,W,UP,B,SIM,ARG,PT,RUF`, line-length 100) + `mypy --strict` with per-module `ignore_missing_imports` overrides for untyped third-party deps.
  - **Why:** Strict typing catches real bugs; known-untyped packages (fastapi, pydantic, sqlalchemy, etc.) would otherwise generate noise.
  - **Phase:** 23
- **Decision:** Coverage gate at 60% hard block / 70% soft threshold in CI, computed from `coverage.xml` inline in the GitHub Actions step summary.
  - **Why:** Baseline coverage was unknown; soft enforcement avoids blocking day-one CI while nudging upward.
  - **Phase:** 23
- **Decision:** Docker Compose hardening — removed host port bindings from `postgres`, `minio`, `prometheus`, `grafana`; disabled `GF_AUTH_ANONYMOUS_ENABLED`. Only the gateway (8080) is exposed to the host.
  - **Why:** Reduces attack surface for a security-focused gateway; observability stack should sit behind the reverse proxy / internal network only.
  - **Phase:** 23
- **Decision:** Trust Center (`src/anonreq/trust_center/`) is registered unconditionally at app startup but gated at request time via a `Depends()` check against `app.state.trust_center_enabled` (from `config/trust_center.yaml`), returning 404 when disabled.
  - **Why:** No existing pattern for conditional `include_router`; runtime gating is simpler and matches the "disabled → 404" requirement.
  - **Phase:** 24
- **Decision:** Trust Center is public (no auth, same pattern as `/metrics`), rate-limited to 60 RPM/IP via a dedicated Redis-backed `TrustCenterRateLimiter` (not the tenant-scoped `UsageLimiter`), fails closed (503) if the SLO engine or PresetEngine is unavailable, and returns aggregate metadata only — never raw or per-tenant data.
  - **Why:** Public compliance portal per Vanta baseline; must not leak tenant-level intelligence even under aggregation.
  - **Phase:** 24
- **Decision:** CORS is not handled in-app for Trust Center; delegated to the reverse proxy.
  - **Why:** Adding CORS middleware would affect all routes globally; gateway is designed for internal-network deployment behind a proxy.
  - **Phase:** 24
- **Decision:** Documentation translated via machine translation + human review into FR, ES, PT, IT, AR, NL (joining existing EN/DE for 8 total languages). Code blocks, CLI commands, filenames, and anchors stay in English; only prose is translated.
  - **Why:** Translated code breaks copy-paste workflows and tool compatibility.
  - **Phase:** 25
- **Decision:** `docs/GLOSSARY.md` (23 terms × 8 languages) and `docs/TRANSLATION_MANIFEST.md` (54 file entries, source→target mapping, status) track translation consistency and completeness.
  - **Why:** Prevents terminology drift across independently translated documents; satisfies DOCS-02.
  - **Phase:** 25
- **Decision:** 4 custom enterprise Presidio-compatible recognizers (`AnonReq_APIKeyRecognizer`, `AnonReq_AWSAccessKeyRecognizer`, `AnonReq_GitHubTokenRecognizer`, `AnonReq_InternalHostnameRecognizer`) route through the existing `RegexDetector` pipeline, not the Presidio sidecar, and are explicitly `AnonReq_`-prefixed to avoid Presidio's internal dict-key namespace collisions.
  - **Why:** Keeps detection self-contained and avoids collisions with Presidio's built-in recognizer names.
  - **Phase:** 26
- **Decision:** Commercial licensing uses offline HMAC-SHA256 signed payloads (org, tier, features, expiry), verified with `hmac.compare_digest`, keyed by `ANONREQ_LICENSE_SECRET` env var. No phone-home; no PyJWT dependency. A `require_license(feature)` FastAPI dependency returns HTTP 402 when a gated feature is accessed without a valid license.
  - **Why:** Avoids third-party licensing infrastructure and network dependency for license checks; 402 is semantically correct for "payment required."
  - **Phase:** 26
- **Decision:** Only Appliance-tier features are gated (Trust Center, AI firewall, SOC integration, advanced detection, compliance monitoring). The **core anonymization pipeline is never gated** — detection, tokenization, and restoration remain free.
  - **Why:** Core value proposition (PII never crosses the boundary) must remain universally available regardless of license status.
  - **Phase:** 26
- **Decision:** Compliance evidence (`GET /v1/admin/compliance/evidence?framework=...`) aggregates SLO compliance state, audit chain entries, governance records, and incident history into JSON Lines snapshots, stored in MinIO with local filesystem fallback, on a configurable (default daily) cron schedule.
  - **Why:** Extends the existing `AuditChainService`; MinIO is already part of the observability stack.
  - **Phase:** 26

## 3. Phases Delivered

| Phase | Name | Status | One-Liner |
|-------|------|--------|-----------|
| 23 | Engineering Hygiene | Complete | ruff/mypy configured and passing cleanly; Docker Compose hardened (no host ports on non-gateway services, Grafana anon-auth disabled); GitHub Actions CI running lint/type/test/coverage on every push/PR |
| 24 | Trust Center | Complete | Public, config-gated, rate-limited `/v1/trust/*` portal (status, compliance, metrics, security) exposing aggregate-only metadata, with full unit + integration test coverage (29 scenarios) |
| 25 | Documentation Parity | Complete | 54 documents (9 source docs × 6 languages) translated into FR, ES, PT, IT, AR, NL; glossary and translation manifest fully populated |
| 26 | Enterprise Guardrails | Complete | 4 custom secret/hostname recognizers, compliance evidence endpoint, and HMAC-SHA256 offline commercial licensing with feature gating (402 responses); 54 tests (unit, property-based, integration) all green |

## 4. Requirements Coverage

From `.planning/milestones/v1.5-REQUIREMENTS.md` (archived, status: SHIPPED):

- ✅ **HYG-01** — CI/CD test workflow runs full pytest suite on every push/PR to main (Phase 23)
- ✅ **HYG-02** — ruff and mypy enforce code quality in CI with staged rollout (Phase 23)
- ✅ **HYG-03** — Docker Compose exposes only the gateway port (8080); Grafana anonymous auth disabled (Phase 23)
- ✅ **TRUST-01** — Public `/v1/trust/status`, `/v1/trust/compliance`, `/v1/trust/metrics`, `/v1/trust/security` endpoints (Phase 24)
- ✅ **TRUST-02** — Trust Center is config-gated, rate-limited, returns aggregate metadata only (Phase 24)
- ✅ **DOCS-01** — Documentation translated into FR, ES, PT, IT, AR, NL (8 total languages) (Phase 25)
- ✅ **DOCS-02** — Translation manifest tracks source→target mapping and review status (Phase 25)
- ✅ **GUARD-01** — Custom Presidio recognizers for API keys, AWS tokens, GitHub tokens, internal hostnames (Phase 26)
- ✅ **GUARD-02** — Continuous compliance monitoring with automated evidence collection endpoint (Phase 26)
- ✅ **GUARD-03** — HMAC-SHA256 commercial licensing with feature gating for Appliance-tier capabilities (Phase 26)

**Coverage: 10/10 requirements mapped and complete. 0 unmapped.**

No `v1.5-MILESTONE-AUDIT.md` was found — the archive does not include a separate audit verdict document for this milestone.

## 5. Key Decisions Log

See Section 2 for the full decision list with rationale. Summary by phase:

- **Phase 23 (14 decisions, `CONTEXT.md`):** GitHub Actions, single Py3.12 target, `uv` package manager, no CI Docker service containers (fakeredis/respx mocks suffice), ruff/mypy rule sets, auto-fix-then-manual-fix strategy, 70%/60% coverage thresholds, no pre-commit hooks (CI-only enforcement), Docker port hardening scope, uv dependency caching, load tests excluded from default CI run.
- **Phase 24 (13 decisions, `CONTEXT.md`):** Trust Center package structure, runtime config-gating via `Depends()`, YAML config loading via pydantic-settings, SLO/PresetEngine integration for aggregate metrics, dedicated IP-based rate limiter, no-auth public access, CORS delegated to reverse proxy, fail-closed on backend unavailability, Pydantic response schemas, test strategy.
- **Phase 25 (7 decisions, `CONTEXT.md`):** Source document set, machine-translation-with-review method, translation manifest tracking, Arabic RTL guidance (deferred full verification to v2), link validation via existing CI, glossary creation, code/config/CLI snippets excluded from translation.
- **Phase 26 (10 decisions, `CONTEXT.md`):** Recognizer registration through `RegexDetector` (not Presidio sidecar), `AnonReq_`-prefixed recognizer names, YAML-configurable recognizers, compliance evidence endpoint design, MinIO/filesystem evidence storage, HMAC-SHA256 offline licensing (no phone-home), feature-gate dependency returning 402, license package structure, core pipeline exempt from all gating.

## 6. Tech Debt & Deferred Items

**From `.planning/milestones/v1.5-REQUIREMENTS.md` (v2 Requirements — explicitly deferred):**
- Trust Center AI chatbot for automated NDA/security questionnaire responses
- Translation memory tooling (Crowdin/Lokalise) for ongoing doc maintenance
- License key distribution server and admin CLI
- Entropy-based generic secret detection
- Arabic RTL rendering verification (full check, beyond the current guidance note)

**Out of scope (deferred post-v1.5, per PROJECT.md):**
- Enterprise Authentication (OAuth/JWT/mTLS, RBAC, OIDC/SAML)
- Secrets Management & Network Security (Vault, cloud secret stores, internal mTLS)
- Multi-Tenant Isolation (tenant namespacing, per-tenant config, provisioning API)
- High Availability / Scalability / DR (Valkey Sentinel/Cluster, Kubernetes Helm chart)
- Data Sovereignty & Compliance Assurance (geographic routing, detection benchmarks, SLO dashboards)

**Risk notes surfaced during planning (`CONTEXT.md` files):**
- Public Trust Center metrics, even aggregated, can leak business-intelligence trends (e.g., request volume); the 60 RPM rate limiter does not fully prevent intentional scraping.
- Trust Center fails closed (503) on SLO/PresetEngine outage — every request 503s during an outage. Accepted for MVP; short-TTL caching of last-known-good data was considered but deferred.
- Current Trust Center design is single-tenant (`tenant_id="default"`); would need rework for cross-tenant aggregation if multi-tenancy is added later.
- `mypy --strict` on a large codebase risked surfacing 100+ violations; mitigated with iterative, per-category fixes and scoped `# type: ignore` comments.
- Docker Compose hardening removes host ports for observability services — local dev workflows relying on direct access need `--profile observability` and should consult `CONTRIBUTING.md`.

**⚠️ Operational gap found during this summary generation (not previously flagged in planning docs):** The working tree at `/Users/aljaunia/Documents/Develop/annon` currently has **484 modified files and 29 untracked paths uncommitted to git**, including all of Phase 26's work (`src/anonreq/license/`, `src/anonreq/trust_center/`, `src/anonreq/detection/recognizers/enterprise.py`, `config/recognizers.yaml`, `config/trust_center.yaml`, all `docs/{fr,es,pt,it,ar,nl}/` translations, `.github/workflows/test.yml`, and the Phase 26 SUMMARY files themselves). `git log` HEAD stops at "Complete Phase 25" (`9b62f3e`) — Phase 26 has no commits at all. The large modified-file count is consistent with the Phase 23 `ruff --fix` sweep touching most of `src/`, but this has not been committed either. **Recommend committing this work before starting the next milestone** to avoid losing it or conflating it with new work.

## 7. Getting Started

- **Run the project:** `docker compose up` — multi-stage Dockerfile (Python 3.12-slim) with `anonreq` (gateway, only exposed port), `presidio-analyzer`, and `valkey` services. Optional `--profile observability` adds PostgreSQL, MinIO, Grafana, Prometheus (no host ports since Phase 23 hardening — access via the gateway or internal network only).
- **Tests:** `uv run pytest` (full suite), `uv run pytest tests/property/` (Hypothesis property-based), `uv run pytest tests/unit/`, `uv run pytest -m load` (load tests, excluded from default CI run). CI runs `ruff check`, `mypy`, `pytest -m "not load"`, and enforces 60% hard-block / 70% soft coverage via `.github/workflows/test.yml`.
- **Key directories:**
  - `src/anonreq/core/`, `pipeline/`, `detection/`, `tokenization/`, `restore/` — core anonymization pipeline (never license-gated)
  - `src/anonreq/trust_center/` — public compliance portal (Phase 24)
  - `src/anonreq/license/` — HMAC-SHA256 commercial licensing (Phase 26)
  - `src/anonreq/detection/recognizers/enterprise.py` — custom secret/hostname recognizers (Phase 26)
  - `src/anonreq/services/compliance_evidence.py` — compliance evidence aggregation (Phase 26)
  - `docs/{en,de,fr,es,pt,it,ar,nl}/` — 8-language documentation; `docs/GLOSSARY.md` and `docs/TRANSLATION_MANIFEST.md` track terminology and translation status
  - `config/trust_center.yaml`, `config/recognizers.yaml` — Phase 24/26 configuration
  - `.planning/phases/23-26-*/` — this milestone's plans, summaries, and context docs
- **Where to look first:** `src/anonreq/main.py` (app factory / lifespan wiring for Trust Center and licensing), `.planning/PROJECT.md` (full requirements and architecture history), `AGENTS.md` (test/dev command reference).

---

## Stats

- **Timeline:** 2026-07-07 → 2026-07-09 (3 days)
- **Phases:** 4 / 4 complete (Phases 23, 24, 25, 26)
- **Commits:** 14 commits between the `v1.0` tag and current `HEAD` relate to v1.5 work (through "Complete Phase 25"); **Phase 26 work is fully uncommitted** — see Tech Debt section.
- **Files changed:** Not reliably computable — `git diff --stat v1.0..HEAD` did not return within a reasonable time on this repo, and a large portion of relevant changes (all of Phase 26, plus untracked Phase 24/25 files) are outside any commit range. From `git status`: 484 modified + 29 untracked paths currently uncommitted.
- **Contributors:** aljaunia
