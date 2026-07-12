# Requirements: AnonReq v1.5 — Enterprise Hardening & Trust Center

**Defined:** 2026-07-07
**Core Value:** Raw PII never crosses the network boundary.

## v1.5 Requirements

### Engineering Hygiene

- [x] **HYG-01**: CI/CD test workflow runs the full pytest suite on every push/PR to main
- [x] **HYG-02**: ruff and mypy enforce code quality in CI with staged rollout
- [x] **HYG-03**: Docker Compose exposes only the gateway port (8080) by default; Grafana anonymous auth disabled

### Trust Center

- [x] **TRUST-01**: Public `/v1/trust/status`, `/v1/trust/compliance`, `/v1/trust/metrics`, `/v1/trust/security` endpoints
- [x] **TRUST-02**: Trust Center is config-gated (YAML toggle), rate-limited, returns aggregate metadata only

### Documentation Parity

- [x] **DOCS-01**: Documentation translated into FR, ES, PT, IT, AR, NL (8 total languages including existing EN/DE)
- [x] **DOCS-02**: Translation manifest tracks source→target mapping and review status

### Enterprise Guardrails

- [x] **GUARD-01**: Custom Presidio recognizers for API keys, AWS tokens, GitHub tokens, internal hostnames
- [x] **GUARD-02**: Continuous compliance monitoring with automated evidence collection endpoint
- [x] **GUARD-03**: HMAC-SHA256 commercial licensing with feature gating for Appliance-tier capabilities

## v2 Requirements (Deferred)

- Trust Center AI chatbot for automated NDA/security questionnaire responses
- Translation memory tooling (Crowdin/Lokalise) for ongoing doc maintenance
- License key distribution server and admin CLI
- Entropy-based generic secret detection
- Arabic RTL rendering verification

## Out of Scope

| Feature | Reason |
|---------|--------|
| Enterprise Authentication (OAuth/JWT/mTLS, SSO) | Deferred post-v1.5; not part of MOTE scope |
| Secrets Management (Vault, AWS Secrets Manager) | Deferred post-v1.5 |
| Multi-Tenant Isolation | Deferred post-v1.5 |
| High Availability / Kubernetes | Deferred post-v1.5 |
| Data Sovereignty Dashboards | Deferred post-v1.5 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| HYG-01 | Phase 23 | Complete |
| HYG-02 | Phase 23 | Complete |
| HYG-03 | Phase 23 | Complete |
| TRUST-01 | Phase 24 | Complete |
| TRUST-02 | Phase 24 | Complete |
| DOCS-01 | Phase 25 | Complete |
| DOCS-02 | Phase 25 | Complete |
| GUARD-01 | Phase 26 | Complete |
| GUARD-02 | Phase 26 | Complete |
| GUARD-03 | Phase 26 | Complete |

**Coverage:**

- v1.5 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0 ✓

---

*Requirements defined: 2026-07-07*
*Last updated: 2026-07-07 after v1.5 milestone start*
