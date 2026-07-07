# Project Research Summary

**Project:** AnonReq v1.5 — Enterprise Hardening & Trust Center
**Domain:** Self-hosted AI security & anonymization gateway
**Researched:** 2026-07-07
**Confidence:** HIGH

## Executive Summary

AnonReq v1.5 hardens an existing, mature self-hosted AI security gateway for enterprise compliance, commercial licensing, and global documentation parity. The research unanimously confirms a **zero-new-pip-dependency approach**: all four v1.5 phases (Engineering Hygiene, Trust Center, Documentation Parity, Enterprise Guardrails) build on the existing stack — Python 3.12, FastAPI, Pydantic Settings, Valkey, Prometheus — using only Python stdlib additions (`hmac`, `hashlib`, `re`). No new infrastructure, no new pip packages, no Presidio sidecar modifications.

The core recommendation is a dependency-ordered 4-phase rollout: **Phase 1 (Hygiene) first** because CI/code quality enforcement is prerequisite for confident work in subsequent phases. **Phase 2 (Trust Center)** and **Phase 3 (Docs)** can run independently after Phase 1. **Phase 4 (Guardrails)** must follow Phase 2 because the license module gates the Trust Center and custom recognizers. Phase 3 is pure content work with no code dependencies.

The five critical risks to mitigate are: (1) registering Trust Center behind auth middleware (defeats the purpose of a public compliance portal), (2) routing custom recognizers through the Presidio sidecar (its HTTP API doesn't support custom patterns), (3) implementing license checks inside route handlers instead of FastAPI router-level dependencies, (4) implementing phone-home license validation (breaks air-gapped/sovereign deployments), and (5) leaking tenant-level PII in Trust Center responses. All have well-documented prevention strategies in the detailed research.

## Key Findings

### Recommended Stack

**Zero new pip dependencies for v1.5.** All features build on the existing stack plus Python stdlib modules. The HMAC-SHA256 license validation uses `hmac` + `hashlib` from stdlib rather than PyJWT (unnecessary dependency). Custom recognizers compile `re.Pattern` objects through the existing `RegexDetector` pipeline rather than modifying the Presidio sidecar.

**Core technologies:**

- **Python 3.12 + FastAPI 0.115+**: Established runtime, app factory pattern, dependency injection — all proven across 768+ existing tests
- **Pydantic Settings 2.x**: Config toggle pattern with `ANONREQ_` env prefix, validation already established in codebase
- **Valkey 7.x (Redis-compatible)**: SLO engine data, rate limiting, cache — existing infrastructure reused for Trust Center rate limiting
- **Prometheus client 0.20+**: Aggregate metrics via `REGISTRY.get_sample_value()` — no new monitoring infrastructure
- **structlog 24.x**: Audit logging for Trust Center and compliance evidence — already established
- **ruff 0.6+ / mypy 1.11+**: New dev dependencies for code quality enforcement (Phase 1)

**What NOT to use:**
- PyJWT libraries — HMAC-SHA256 is simpler, no dependency burden
- Presidio-analyzer in-process — breaks sidecar architecture
- `httpx` for license validation — license check is local computation
- Redis for license caching — in-process variable on `app.state` suffices

### Expected Features

**Must have (table stakes) — enterprise customers assume these exist:**
- CI/CD pipeline (GitHub Actions with pytest/ruff/mypy) — prerequisite for enterprise adoption
- Code quality enforcement (ruff + mypy) — security audit expectation
- Docker security hardening (remove host ports from non-gateway services) — security team gate
- Public compliance evidence portal (Trust Center) — Vanta baseline for enterprise evaluations
- Multi-language documentation (6 languages: FR, ES, PT, IT, AR, NL) — global TAM requirement
- Commercial licensing (HMAC-SHA256 validation) — legal/procurement requirement
- Secret detection (API keys, AWS keys, GitHub tokens, internal hostnames) — DLP requirement
- Continuous compliance monitoring (evidence endpoint, automated snapshots) — SOC 2/ISO 27001

**Should have (competitive differentiators):**
- HMAC-based licensing without phone-home — enables air-gapped/sovereign deployments
- Public Trust Center as part of open-source gateway — most competitors lack this
- Custom recognizer gating by license tier — clean monetization without bifurcating codebase
- Integrated translation manifest with per-file review status — compliance audit trail

**What NOT to do (anti-features):**
- Phone-home license validation (breaks air-gap)
- Modifying Presidio sidecar for custom recognizers (maintenance burden)
- Auth on Trust Center (defeats purpose)
- Gating the core anonymization pipeline (kills adoption)
- Real-time Prometheus scraping in Trust Center (use cached snapshots at scale)

### Architecture Approach

v1.5 introduces three new modules following established patterns. The **Trust Center** (`src/anonreq/trust_center/`) is a public, config-gated, rate-limited compliance evidence portal with 4 endpoints that aggregate data from SLOEngine, PresetEngine, and Prometheus REGISTRY. The **License module** (`src/anonreq/license/`) provides HMAC-SHA256 validation at startup with in-memory caching and FastAPI router-level dependency injection via `require_license("feature")`. The **Custom Recognizer modules** (4 new files in `src/anonreq/detection/recognizers/`) extend the existing `RegexDetector` pipeline — they do NOT go through the Presidio sidecar.

**Major components:**

1. **Trust Center module** — Public endpoints (`/v1/trust/status`, `/compliance`, `/metrics`, `/security`); config-gated + rate-limited + license-gated; aggregates metadata only (no PII, no tenant-level breakdowns)
2. **License module** — HMAC-SHA256 validation at startup; `require_license(feature)` FastAPI dependency factory for router-level gating; zero network calls; in-memory cached for app lifetime
3. **Custom recognizers** — 4 new recognizer classes (APIKey, AWSAccessKey, GitHubToken, InternalHostname) following the existing MNPIRecognizer pattern; license-gated via `advanced_detection` feature; compiled via `RegexDetector` not Presidio sidecar
4. **Documentation translation infrastructure** — 6 language mirrors of `docs/en/` + `TRANSLATION_MANIFEST.md` + `glossary.md`; pure content work, no code

**Key patterns:** Config-gated router registration (routes disabled = not mounted, returns 404 efficiently), license gate as FastAPI dependency factory, custom recognizer via RegexDetector extension, translation mirror with manifest tracking, structured service module for aggregate endpoints.

### Critical Pitfalls

1. **Trust Center routes registered behind auth middleware** — Most critical. The existing codebase registers all routers with `Depends(auth_context)`. Trust Center must be registered as a separate `include_router()` call AFTER all auth-protected routes, with NO auth dependency. **Prevention:** Standalone registration, test that `GET /v1/trust/status` returns 200 without any `Authorization` header.

2. **Custom recognizers routed through Presidio sidecar** — Presidio's HTTP API does NOT accept custom regex patterns — it only filters by built-in NER entity types. Custom recognizers sent to Presidio silently detect nothing. **Prevention:** Route all pattern-based recognizers through the existing `RegexDetector` → `DetectionStage` pipeline, not through `PresidioClient.analyze_text_nodes()`.

3. **License check implemented inside route handlers** — Per-handler checks create patchwork enforcement; new routes get added without the check. **Prevention:** Define `require_license("feature")` as a FastAPI dependency factory (in `license/deps.py`), apply at the **router** level via `dependencies=[Depends(require_license("..."))]`.

4. **Phone-home license validation** — HTTP calls to a licensing server break air-gapped deployments, add latency, and create a single point of failure. **Prevention:** HMAC-SHA256 symmetric signing with local key. Zero network calls. Validate at startup, cache in-memory.

5. **PII leaked in Trust Center responses** — Including tenant-level SLO breakdowns in public responses violates data protection. **Prevention:** Use `get_all_compliance("*")` with wildcard tenant ID for aggregated metrics only. Never iterate over tenants. Scan responses for `tenant_id` fields.

## Implications for Roadmap

Based on research, the recommended phase structure follows the dependency map confirmed by all four research files:

### Phase 1: Engineering Hygiene
**Rationale:** Prerequisite for all subsequent phases. Without CI pipeline and code quality enforcement, all later changes lack automated verification. Easy, isolated wins.
**Delivers:** GitHub Actions CI workflow (pytest, ruff, mypy), ruff + mypy configuration with `pyproject.toml` overrides, hardened Docker defaults (non-gateway services no longer expose host ports).
**Addresses:** Features: CI/CD pipeline, code quality enforcement, Docker security hardening
**Avoids:** No pitfalls directly (foundational phase)
**Stack additions:** ruff 0.6+, mypy 1.11+ as dev dependencies
**Research flag:** Standard patterns — skip research-phase. Well-documented GitHub Actions + ruff/mypy setup.

### Phase 2: Trust Center
**Rationale:** Second priority because it delivers the highest enterprise adoption value (Vanta baseline) and is a prerequisite for Phase 4 gating. No license module dependency (Trust Center is "core" tier). Parallelizable with Phase 3.
**Delivers:** Public `/v1/trust/*` endpoints (status, compliance, metrics, security), config-gated router registration, IP-based rate limiting (60 RPM via Valkey), Trust Center YAML configuration.
**Addresses:** Features: Public compliance evidence (table stake), Trust Center as differentiator
**Avoids:** Pitfall 1 (auth middleware — register standalone), Pitfall 5 (PII leak — aggregate only), Pitfall 7 (rate limiting), Pitfall 9 (config path)
**Implementation order:** config.py + YAML → schemas.py → service.py → deps.py (config gate + rate limit) → router.py → integration in main.py
**Research flag:** Needs attention during planning for rate limiter implementation (Valkey-backed sliding window) and ensuring SLO engine wildcard query path works correctly.

### Phase 3: Documentation Parity
**Rationale:** Independent of all code phases. Pure content work that can run in parallel with Phase 2. Worth doing early to close the "global enterprise" requirement.
**Delivers:** 6 new language directories (fr, es, pt, it, ar, nl) mirroring `docs/en/`, `docs/TRANSLATION_MANIFEST.md` with per-file review state, `docs/glossary.md` with technical term translations, RTL rendering note for Arabic.
**Addresses:** Features: Multi-language documentation (table stake), translation manifest as differentiator
**Avoids:** Pitfall 6 (translation drift — manifest tracks it), Pitfall 10 (Arabic rendering — RTL note)
**Research flag:** Skip research-phase — pure content work with no code changes. CI step for manifest validation is standard.

### Phase 4: Enterprise Guardrails
**Rationale:** Last phase because it depends on Phase 1 (CI for testing) and Phase 2 (license module gates Trust Center, though Trust Center is "core" tier). Internal sub-phase ordering matters.
**Delivers:** License module (`src/anonreq/license/`) with HMAC-SHA256 validation + router-level FastAPI dependency + admin status endpoint; 4 custom recognizer modules (API keys, AWS keys, GitHub tokens, internal hostnames); compliance evidence endpoint with scheduled snapshots.
**Addresses:** Features: Commercial licensing, secret detection, continuous compliance monitoring, license-tier gating of recognizers
**Avoids:** Pitfall 2 (recognizers through Presidio — use RegexDetector), Pitfall 3 (per-handler license checks — use router-level deps), Pitfall 4 (phone-home — use HMAC), Pitfall 8 (license overhead — cache at startup), Pitfall 11 (admin catch-22 — don't gate admin/license)
**Implementation order:** license/models.py + config.py → validator.py → deps.py + router.py → integration in main.py → config/recognizers.yaml → detection recognizer modules → DetectionStage integration → license gate on recognizer loading → evidence endpoint (4.2)
**Research flag:** Phase 4.1 (custom recognizers) needs careful integration with existing DetectionStage pipeline — verify the `extra_patterns` merge path during planning. Phase 4.3 (license module) is well-documented (HMAC patterns).

### Phase Ordering Rationale

- **Phase 1 must come first** — CI + code quality is the foundation for confident changes. Without automated verification, every subsequent phase risks introducing regressions without detection.
- **Phase 2 and Phase 3 are independent** — Trust Center (code) and Documentation (content) have zero shared dependencies and can be developed in parallel after Phase 1 completes.
- **Phase 4 must follow Phase 2** — While the Trust Center is "core" tier (not license-gated for free users), the license module created in Phase 4.3 is needed to enforce the gate. The license admin endpoint (Phase 4.3) is also needed for operational visibility before custom recognizers (Phase 4.1) can be gated by tier.
- **Phase 4 internal ordering** — License module (4.3) must be built before custom recognizers (4.1) because recognizer loading is license-gated. Evidence endpoint (4.2) is independent of recognizers but depends on governance/audit record persistence.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** Trust Center rate limiter implementation — confirm Valkey-backed sliding window pattern matches existing cache usage; verify SLOEngine `get_all_compliance("*")` wildcard path returns properly aggregated data
- **Phase 4.1:** Custom recognizer integration with DetectionStage — verify `extra_patterns` merge path and test coverage for the license-gated loading path

Phases with standard patterns (skip research-phase):
- **Phase 1:** Standard GitHub Actions + ruff/mypy setup, well-documented, skip research
- **Phase 3:** Pure documentation content work, no code changes, skip research
- **Phase 4.3:** HMAC-SHA256 validation is a well-documented stdlib pattern, skip research

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified against `src/anonreq/` (existing deps), Python stdlib docs, and `.planning/v1.5-SPEC.md`. No ambiguity — zero new pip dependencies confirmed. |
| Features | HIGH | Derived from `.planning/v1.5-SPEC.md` (canonical), verified against codebase interfaces (SLOEngine, PresetEngine, Recognizer patterns). Phase dependencies cross-referenced. |
| Architecture | HIGH | Detailed codebase verification against `main.py`, pipeline, detection, admin, and compliance modules. All component boundaries and integration points identified. Five confirmed patterns with code examples. |
| Pitfalls | HIGH | Each pitfall verified against actual codebase patterns (`main.py` router registration, `presidio_client.py` HTTP API limitations, existing MNPI recognizer pattern). Prevention strategies reference real code patterns. |

**Overall confidence:** HIGH

All four research files rate HIGH confidence, and the synthesis reveals strong alignment across them — no contradictions, consistent dependency ordering, and well-documented implementation paths. The codebase is mature (v1.0 complete with 768+ tests), so research findings are verified against real running code, not speculative patterns.

### Gaps to Address

- **Trust Center rate limiter implementation details:** Research confirms Valkey-backed IP-based rate limiting at 60 RPM, but the specific sliding window implementation (bucket vs. sorted set) needs design confirmation during Phase 2 planning. Low risk — Valkey is already a dependency.
- **Compliance evidence endpoint (Phase 4.2) dependency on PostgreSQL/MinIO:** The evidence collection depends on governance record persistence (PostgreSQL for AuditChainService, MinIO for archives). These are optional in the observability profile. The implementation should warn if dependencies are missing, not crash. Needs design attention during Phase 4.2 planning.
- **License key distribution mechanism:** Research confirms HMAC-SHA256 validates locally, but does not prescribe how license keys are distributed to customers. This is an operational concern (out of scope for v1.5 implementation) but should be flagged for the product team.
- **Translation quality verification (Phase 3):** The manifest tracks review state, but there's no automated quality gate for translations. This is acceptable for v1.5 — manual review by native speakers is the standard approach.

## Sources

### Primary (HIGH confidence)
- `src/anonreq/main.py` — App factory, router registration, middleware, lifespan (verified architecture patterns)
- `src/anonreq/pipeline/detection.py` — DetectionStage, AtomicConfigRegistry, RegexDetector integration (verified custom recognizer path)
- `src/anonreq/detection/presidio_client.py` — Presidio HTTP API limitations (verified no custom recognizer support)
- `src/anonreq/detection/recognizers/mnpi.py` — Existing custom recognizer pattern (verified pattern for v1.5 recognizers)
- `src/anonreq/services/slo_engine.py` — SLOEngine interface, `get_all_compliance()` (verified Trust Center data source)
- `src/anonreq/compliance/engine.py` — PresetEngine, compliance framework metadata (verified Trust Center data source)
- `src/anonreq/admin/config.py` — AtomicConfigRegistry hot-reload pattern (verified custom recognizer config)
- `src/anonreq/config/__init__.py` — Pydantic Settings pattern, `ANONREQ_` env prefix (verified config pattern)
- `src/anonreq/dependencies.py` — `auth_context` dependency, `Depends` composition (verified dependency injection)
- `.planning/v1.5-SPEC.md` — Canonical specification for all four phases
- `.planning/PROJECT.md` — Project context, milestones, constraints
- Python stdlib docs: `hmac`, `hashlib`, `re` modules — verified no compatibility concerns

### Secondary (MEDIUM confidence)
- `config/compliance/*.yaml` — Compliance preset YAML format (verified structure, Trust Center reads from PresetEngine)
- `config/slo.yaml` — SLO target configuration format (verified structure, Trust Center reads aggregated data)
- `docs/en/` — Source documentation structure (verified mirror pattern for Phase 3)

---

*Research completed: 2026-07-07*
*Ready for roadmap: yes*
