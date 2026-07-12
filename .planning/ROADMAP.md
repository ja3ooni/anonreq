# Roadmap: AnonReq

## Milestones

- ✅ **v1.0 MVP** — Phases 1-22 (shipped 2026-07-07)
- ✅ **v1.5 Enterprise Hardening & Trust Center** — Phases 23-27 (shipped 2026-07-12)
- 🚧 **v2.0 Enterprise & Deployment Moat** — Phases 28-32 (in progress)

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

<details>
<summary>✅ v1.5 Enterprise Hardening & Trust Center (Phases 23-27) — SHIPPED 2026-07-12</summary>

- [x] Phase 23: Engineering Hygiene (3/3 plans) — completed 2026-07-08
- [x] Phase 24: Trust Center (2/2 plans) — completed 2026-07-08
- [x] Phase 25: Documentation Parity (2/2 plans) — completed 2026-07-08
- [x] Phase 26: Enterprise Guardrails (3/3 plans) — completed 2026-07-09
- [x] Phase 27: v1.5 Tech Debt Cleanup (1/1 plan) — completed 2026-07-12

</details>

### 🚧 v2.0 Enterprise & Deployment Moat (In Progress)

**Milestone Goal:** Hardening AnonReq with enterprise-grade SSO/RBAC, multi-tenant isolation, high availability scaling, and secure cloud secrets management.

#### Phase 28: High Availability Cache & Resilience
**Goal**: Resilient, HA-aware Valkey connection caching logic that is fail-safe during reelection.
**Depends on**: Phase 27
**Requirements**: [HA-01, HA-03]
**Success Criteria** (what must be TRUE):
  1. Gateway dynamically routes requests using Valkey Sentinel or Cluster connection factories based on the configured connection scheme.
  2. Valkey connection failures or master reelections fail closed, returning HTTP 5xx errors to the client rather than routing un-anonymized data.
  3. Cache operations successfully recover from transient reelection failover latency via exponential retry backoffs within 30 seconds.
**Plans**: 2 plans

Plans:
- [ ] 28-01: Implement Valkey Sentinel & Cluster connection factories in CacheManager
- [ ] 28-02: Implement exponential backoff retries with fail-closed security guards for reelection failovers

#### Phase 29: Secure Configuration & Secrets Management
**Goal**: Safe, dynamic secrets retrieval and hot-reloading from HashiCorp Vault / Cloud KMS without env or disk persistence, including secure rotation buffering and logs redaction.
**Depends on**: Phase 28
**Requirements**: [SEC-01, SEC-02, SEC-03, SEC-04]
**Success Criteria** (what must be TRUE):
  1. Gateway successfully retrieves credentials dynamically from HashiCorp Vault or Cloud KMS at startup without environment variable or disk persistence.
  2. Modified configurations and rotated secrets are dynamically reloaded in-memory without service disruption when secret volumes change.
  3. Sensitive secret substrings are automatically replaced with `[REDACTED]` in all structured logs.
  4. Active SSE streams continue to function using previous cryptographic keys stored in a read-only rotation buffer during key rotation.
**Plans**: 3 plans

Plans:
- [ ] 29-01: Integrate hvac and dynamic secret retrieval from Vault/cloud KMS
- [ ] 29-02: Implement watchdog volume monitor and config hot-reload
- [ ] 29-03: Implement log formatter secret redaction and rotation buffer grace window

#### Phase 30: Enterprise Authentication & RBAC
**Goal**: Secure administrative and gateway access using OIDC JWT signature verification, predefined enterprise roles, and ingress-forwarded mTLS validation.
**Depends on**: Phase 29
**Requirements**: [SSO-01, SSO-02, SSO-03]
**Success Criteria** (what must be TRUE):
  1. Admin and gateway requests are authenticated via OIDC JWT signature verification against cached JWKS endpoints.
  2. Route decorators enforce roles (`administrator`, `security_officer`, `operator`, `read_only_auditor`), blocking unauthorized role access with HTTP 403.
  3. Machine-to-machine requests are verified using mTLS client certificates forwarded by trusted ingress proxies.
  **UI hint**: yes
**Plans**: 3 plans

Plans:
- [ ] 30-01: Implement authlib-based OIDC token verification with local JWKS caching
- [ ] 30-02: Implement role-based authorization decorator and access control checks
- [ ] 30-03: Implement mTLS client certificate verification middleware

#### Phase 31: Multi-Tenant Segregation & Isolation
**Goal**: Rigid request namespacing, tenant-scoped cache partitioning with dynamic KMS encryption, and tenant-scoped logging/metrics.
**Depends on**: Phase 30
**Requirements**: [TEN-01, TEN-02, TEN-03, TEN-04]
**Success Criteria** (what must be TRUE):
  1. Gateway rejects requests missing or failing validation of the `X-AnonReq-Tenant-ID` header.
  2. Valkey cache keys are isolated using tenant-prefixed namespaces (`anonreq:tenant_{tenant_id}:{session_id}`).
  3. Cached token mappings are dynamically encrypted and decrypted in-memory using tenant-specific KMS keys.
  4. Structured logs and custom Prometheus metrics are partitioned/labeled with the corresponding active `tenant_id`.
**Plans**: 3 plans

Plans:
- [ ] 31-01: Implement TenantContextMiddleware and Valkey prefix isolation
- [ ] 31-02: Implement dynamic key-based encryption for cached token mappings
- [ ] 31-03: Implement tenant-scoped logging interceptors and labeled Prometheus metrics

#### Phase 32: Kubernetes Deployment & Scaling
**Goal**: Package the enterprise-grade HA, multi-tenant, and secret-managed gateway into an official Helm v3 deployment.
**Depends on**: Phase 31
**Requirements**: [HA-02]
**Success Criteria** (what must be TRUE):
  1. Deploy the gateway using an official Helm v3 chart with replica controls and node anti-affinity rules.
  2. Pod count scales dynamically via Horizontal Pod Autoscaler (HPA) based on CPU and memory usage metrics.
**Plans**: 1 plan

Plans:
- [ ] 32-01: Create Helm v3 chart with replica controls and HPA / anti-affinity rules

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
| 23. Engineering Hygiene | v1.5 | 3/3 | Complete | 2026-07-08 |
| 24. Trust Center | v1.5 | 2/2 | Complete | 2026-07-08 |
| 25. Documentation Parity | v1.5 | 2/2 | Complete | 2026-07-08 |
| 26. Enterprise Guardrails | v1.5 | 3/3 | Complete | 2026-07-09 |
| 27. v1.5 Tech Debt Cleanup | v1.5 | 1/1 | Complete | 2026-07-12 |
| 28. High Availability Cache & Resilience | v2.0 | 0/2 | Not started | - |
| 29. Secure Configuration & Secrets Management | v2.0 | 0/3 | Not started | - |
| 30. Enterprise Authentication & RBAC | v2.0 | 0/3 | Not started | - |
| 31. Multi-Tenant Segregation & Isolation | v2.0 | 0/3 | Not started | - |
| 32. Kubernetes Deployment & Scaling | v2.0 | 0/1 | Not started | - |

## Summary

| Stage | Phases | Plans | Status |
|-------|--------|-------|--------|
| 1. Prove the Problem | 7 (1–7) | 26/26 | Complete |
| 2. Build the Enterprise Platform | 9 (8–16) | 44/44 | Complete |
| 3. Build the Moat | 6 (17–22) | 31/31 | Complete |
| 4. Enterprise Hardening | 5 (23–27) | 11/11 | Complete |
| 5. Enterprise & Deployment Moat | 5 (28–32) | 0/12 | In progress |
| **Total** | **32** | **112/124** | **In progress** |

*Archived from consolidated roadmaps. See `.planning/milestones/v1.0-ROADMAP.md` and `.planning/milestones/v1.5-ROADMAP.md` for full phase details.*
