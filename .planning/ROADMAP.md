# Roadmap: AnonReq

## Milestones

- ✅ **v1.0 MVP** — Phases 1-22 (shipped 2026-07-07)
- 🚧 **v1.5 Enterprise Hardening & Trust Center** — Phases 23-26 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-22) — SHIPPED 2026-07-07</summary>

- [x] Phase 1: Foundation, Fail-Secure & Auth (4/4 plans) — completed 2026-07-01
- [x] Phase 2: Core Pipeline & Classification (5/5 plans) — completed 2026-07-01
- [x] Phase 3: SSE Streaming + Multi-Provider (5/5 plans) — completed 2026-07-03
- [x] Phase 4: Multi-Locale Detection + Compliance Presets (4/4 plans) — completed 2026-07-02
- [x] Phase 5: Configuration & Observability (3/3 plans) — completed 2026-07-02
- [x] Phase 6: Advanced Property-Based Tests (4/4 plans) — completed 2026-07-02
- [x] Phase 6.5: Production Readiness Review (1/1 plan) — completed 2026-07-02
- [x] Phase 7: Developer Experience & Documentation (3/3 plans) — completed 2026-07-02
- [x] Phase 8: Enterprise Policy Engine (6/6 plans) — completed 2026-07-03
- [x] Phase 9: Multimodal Document Anonymization (5/5 plans) — completed 2026-07-03
- [x] Phase 10: AI Security Firewall (5/5 plans) — completed 2026-07-05
- [x] Phase 11: Operational Observability & Compliance Infrastructure (5/5 plans) — completed 2026-07-05
- [x] Phase 12: Data Classification & Handling Policies (4/4 plans) — completed 2026-07-04
- [x] Phase 13: AI Firewall & Data Loss Prevention (5/5 plans) — completed 2026-07-05
- [x] Phase 14: AI Governance & Oversight (5/5 plans) — completed 2026-07-05
- [x] Phase 15: Financial Services Compliance (5/5 plans) — completed 2026-07-05
- [x] Phase 16: Compliance, Audit & Fairness (5/5 plans) — completed 2026-07-05
- [x] Phase 17: Universal AI Traffic Gateway (4/4 plans) — completed 2026-07-05
- [x] Phase 18: Agent & Tool Call Governance (4/4 plans) — completed 2026-07-03
- [x] Phase 19: Network Discovery, CASB & Secure RAG (6/6 plans) — completed 2026-07-05
- [x] Phase 20: AI SOC/SIEM Integration (6/6 plans) — completed 2026-07-05
- [x] Phase 21: Endpoint Visibility & Sovereign AI Control Plane (7/7 plans) — completed 2026-07-06
- [x] Phase 22: Close Milestone Audit Gaps — Runtime Integration Blockers (4/4 plans) — completed 2026-07-07

</details>

### v1.5 (Enterprise Hardening & Trust Center)

- [x] **Phase 23: Engineering Hygiene** - CI/CD, code quality enforcement, secure Docker defaults (completed 2026-07-08)
- [x] **Phase 24: Trust Center** - Public compliance evidence portal (completed 2026-07-08)
- [ ] **Phase 25: Documentation Parity** - Multi-language documentation (8 languages)
- [ ] **Phase 26: Enterprise Guardrails** - Secret detection, compliance monitoring, commercial licensing

## Phase Details

### Phase 23: Engineering Hygiene

**Goal**: Development workflow enforces code quality and secure defaults automatically on every change
**Depends on**: Nothing (foundation phase)
**Requirements**: HYG-01, HYG-02, HYG-03
**Success Criteria** (what must be TRUE):

  1. Every push/PR to main triggers GitHub Actions running the full pytest suite and reporting pass/fail
  2. Ruff and mypy violations cause CI failure (staged rollout with pre-existing violations baseline)
  3. Docker Compose exposes only gateway port 8080 by default; Grafana anonymous auth is disabled
   4. Developers can run the same lint/type-check commands locally via `uv run` with identical configuration

**Plans**: 3 plans
**Plan list:**

- [x] 23-01-PLAN.md — ruff/mypy configuration and auto-fix sweep
- [x] 23-02-PLAN.md — Docker secure defaults (remove host ports, disable Grafana anonymous auth)
- [x] 23-03-PLAN.md — CI/CD test workflow (ruff, mypy, pytest, coverage)

### Phase 24: Trust Center

**Goal**: Enterprises can publicly demonstrate security posture, compliance, and operational health
**Depends on**: Phase 23
**Requirements**: TRUST-01, TRUST-02
**Success Criteria** (what must be TRUE):

   1. Public `/v1/trust/status`, `/v1/trust/compliance`, `/v1/trust/metrics`, `/v1/trust/security` endpoints return aggregate metadata without authentication
   2. Trust Center can be enabled/disabled via YAML configuration toggle (returns 404 when disabled)
   3. Trust Center endpoints are rate-limited (60 RPM) and return no PII, tenant-level data, or raw metrics
   4. SLO and compliance data is publicly accessible as aggregate metadata for enterprise evaluations

**Plans**: 2 plans
**Plan list:**

- [x] 24-01-PLAN.md — Trust Center package scaffold (config, schemas, service, rate limiter, router, main.py wiring)
- [x] 24-02-PLAN.md — Unit and integration tests (config, schemas, rate limiter, fail-closed, TestClient)

### Phase 25: Documentation Parity

**Goal**: Global enterprises can evaluate and deploy AnonReq in their preferred language
**Depends on**: Phase 23
**Requirements**: DOCS-01, DOCS-02
**Success Criteria** (what must be TRUE):

  1. Documentation available in FR, ES, PT, IT, AR, NL (8 total languages including existing EN/DE)
  2. Translation manifest (`docs/TRANSLATION_MANIFEST.md`) tracks every source→target mapping with per-file review status
  3. Glossary of technical terms maintained with translations across all 8 languages
  4. Arabic documentation includes RTL rendering guidance note

**Plans**: 2 plans
**Plan list:**

- [ ] 25-01-PLAN.md — Translation infrastructure (glossary, manifest, English source docs, language directories)
- [ ] 25-02-PLAN.md — Translation content (translate 9 docs to 6 languages, update manifest, validate links)

### Phase 26: Enterprise Guardrails

**Goal**: Enterprise-grade secret detection, compliance automation, and commercial licensing are operational
**Depends on**: Phase 23, Phase 24
**Requirements**: GUARD-01, GUARD-02, GUARD-03
**Success Criteria** (what must be TRUE):

  1. Custom Presidio recognizers detect API keys, AWS tokens, GitHub tokens, and internal hostnames through the existing RegexDetector pipeline (not Presidio sidecar)
  2. Continuous compliance monitoring endpoint collects and serves automated evidence snapshots from SLO engine and governance records
  3. Commercial licensing enforces HMAC-SHA256 validation with router-level feature gating for Appliance-tier capabilities
  4. License validation works entirely offline (no phone-home) with in-memory caching for application lifetime
  5. Router-level `require_license("feature")` dependency prevents access to gated endpoints without a valid license key

**Plans**: 3 plans
**Plan list:**

- [ ] 26-01-PLAN.md — Custom recognizers (API keys, AWS tokens, GitHub tokens, internal hostnames)
- [ ] 26-02-PLAN.md — Compliance evidence endpoint + HMAC-SHA256 commercial licensing
- [ ] 26-03-PLAN.md — Tests for all enterprise guardrails components

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|---------------|--------|-----------|
| 1. Foundation, Fail-Secure & Auth | v1.0 | 4/4 | Complete | 2026-07-01 |
| 2. Core Pipeline & Classification | v1.0 | 5/5 | Complete | 2026-07-01 |
| 3. SSE Streaming + Multi-Provider | v1.0 | 5/5 | Complete | 2026-07-03 |
| 4. Multi-Locale Detection + Compliance Presets | v1.0 | 4/4 | Complete | 2026-07-02 |
| 5. Configuration & Observability | v1.0 | 3/3 | Complete | 2026-07-02 |
| 6. Advanced Property-Based Tests | v1.0 | 4/4 | Complete | 2026-07-02 |
| 6.5. Production Readiness Review | v1.0 | 1/1 | Complete | 2026-07-02 |
| 7. Developer Experience & Documentation | v1.0 | 3/3 | Complete | 2026-07-02 |
| 8. Enterprise Policy Engine | v1.0 | 6/6 | Complete | 2026-07-03 |
| 9. Multimodal Document Anonymization | v1.0 | 5/5 | Complete | 2026-07-03 |
| 10. AI Security Firewall | v1.0 | 5/5 | Complete | 2026-07-05 |
| 11. Operational Observability & Compliance | v1.0 | 5/5 | Complete | 2026-07-05 |
| 12. Data Classification & Handling | v1.0 | 4/4 | Complete | 2026-07-04 |
| 13. AI Firewall & Data Loss Prevention | v1.0 | 5/5 | Complete | 2026-07-05 |
| 14. AI Governance & Oversight | v1.0 | 5/5 | Complete | 2026-07-05 |
| 15. Financial Services Compliance | v1.0 | 5/5 | Complete | 2026-07-05 |
| 16. Compliance, Audit & Fairness | v1.0 | 5/5 | Complete | 2026-07-05 |
| 17. Universal AI Traffic Gateway | v1.0 | 4/4 | Complete | 2026-07-05 |
| 18. Agent & Tool Call Governance | v1.0 | 4/4 | Complete | 2026-07-03 |
| 19. Network Discovery, CASB & Secure RAG | v1.0 | 6/6 | Complete | 2026-07-05 |
| 20. AI SOC/SIEM Integration | v1.0 | 6/6 | Complete | 2026-07-05 |
| 21. Endpoint Visibility & Sovereign Control | v1.0 | 7/7 | Complete | 2026-07-06 |
| 22. Close Milestone Audit Gaps | v1.0 | 4/4 | Complete | 2026-07-07 |
| 23. Engineering Hygiene | v1.5 | 3/3 | Complete    | 2026-07-08 |
| 24. Trust Center | v1.5 | 2/2 | Complete    | 2026-07-08 |
| 25. Documentation Parity | v1.5 | 0/0 | Not started | - |
| 26. Enterprise Guardrails | v1.5 | 0/3 | Planning | - |

## Summary

| Stage | Phases | Plans | Status |
|-------|--------|-------|--------|
| 1. Prove the Problem | 7 (1–7) | 26/26 | Complete |
| 2. Build the Enterprise Platform | 9 (8–16) | 44/44 | Complete |
| 3. Build the Moat | 6 (17–22) | 31/31 | Complete |
| 4. Enterprise Hardening | 4 (23–26) | 0/10 | In progress |
| **Total** | **26** | **101/111** | **In progress** |

*Archived from consolidated roadmaps. See `.planning/milestones/v1.0-ROADMAP.md` for full phase details.*
