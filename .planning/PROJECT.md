# AnonReq

## What This Is

AnonReq is a **self-hosted AI security and anonymization gateway for regulated enterprises**. It sits between enterprise applications and external or local LLM APIs, detects and replaces sensitive data (PII, PHI, financial identifiers, trade secrets) with context-preserving placeholder tokens, forwards sanitized requests, and restores original values in responses — all within the customer's secure perimeter. No raw sensitive data ever crosses the network boundary.

v1.0 ships as a comprehensive platform covering core anonymization, enterprise policy enforcement, AI security firewall, DLP, governance/oversight, financial services compliance, universal AI traffic gateway, CASB/RAG protection, SOC/SIEM integration, endpoint visibility, and sovereign AI control. ~49,500 lines of Python across 22 phases, 101 plans, 179 tasks, 768+ tests.

v1.5 shifts focus to enterprise hardening: engineering hygiene (CI/CD, code quality, secure defaults), public Trust Center portal, documentation parity across 8 languages, and enterprise guardrails with commercial licensing.

## Current Milestone: v2.0 Enterprise & Deployment Moat

**Goal:** Hardening AnonReq with enterprise-grade SSO/RBAC, multi-tenant isolation, high availability scaling, and secure cloud secrets management.

**Target features:**
- SSO, RBAC & API Gateways — OIDC, SAML, mTLS, API keys, and audit logging
- Multi-Tenant Isolation — partition cache, config, metrics, and logs per tenant
- HA, Scaling & DR — Kubernetes Helm chart, Valkey cluster, replica failover
- Secrets Management — HashiCorp Vault integration, Cloud KMS, secure rotation

## Core Value

Raw PII never crosses the network boundary. Every other concern is secondary to that guarantee.

## Requirements

### Validated

- ✓ Core Anonymization Pipeline — OpenAI-compatible `POST /v1/chat/completions`, detection on all message roles, tokenization, restoration, cache cleanup — v1.0
- ✓ Fail-Secure Architecture — any error returns HTTP 5xx, never forward unsanitized data, health endpoint, startup pre-flight — v1.0
- ✓ Hybrid PII Detection Engine — regex tier (email, phone, credit card, IBAN, IP, URL, DOB, national IDs, SWIFT, crypto) + NER tier (name, org, address, city, job title), conflict resolution via regex priority — v1.0
- ✓ Context-Preserving Tokenization — `[TYPE_N]` format, deduplication, reverse-offset replacement, cryptographically random seed per session — v1.0
- ✓ Ephemeral Mapping Store — Valkey/Redis with persistence disabled, TTL 60-3600s, DEL post-response — v1.0
- ✓ SSE Streaming Support — token restoration in stream, Tail_Buffer for split tokens, case-insensitive + bracket-optional matching — v1.0
- ✓ Multi-Provider LLM Support — OpenAI, Anthropic, Gemini, Ollama; Provider_Adapter translation layer, `GET /v1/models` — v1.0
- ✓ Multilingual PII Detection — 8 locales via `X-AnonReq-Locale` header, locale-specific recognizer bundles, checksum validation — v1.0
- ✓ Per-Jurisdiction Compliance Presets — GDPR, LGPD, PDPA, POPIA, Privacy Act, PIPEDA; `GET /v1/compliance/presets` — v1.0
- ✓ Metadata-Only Audit Logging — structured JSON to stdout, field allowlist, no raw values, fail-secure log entries — v1.0
- ✓ Custom Detection Rules and Exclusion Lists — YAML-based custom patterns, hot-reload, `GET /v1/config/rules` — v1.0
- ✓ Docker Compose Deployment — multi-stage Dockerfile (Python 3.12-slim), Presidio + Valkey services, `.env.example` — v1.0
- ✓ Response-Side Token Verification — post-restoration `\[[A-Z]+_\d+\]` scan, Prometheus `/metrics` — v1.0
- ✓ Commercial Open-Source Positioning — Apache 2.0, NOTICE file, SECURITY.md, README with roadmap — v1.0
- ✓ Developer Experience and Multilingual Documentation — `docs/` directory with quickstarts, SDK examples, CHANGELOG.md — v1.0
- ✓ Property-Based Test Suite — Hypothesis-based round-trip correctness, token uniqueness, deduplication, fail-secure, locale checksum, no-PII-in-logs, streaming round-trip, cross-request randomization — v1.0
- ✓ Enterprise Policy Engine — rate limits, spend controls, data residency, PDP/PEP middleware, RBAC, decision audit, crypto evidence store — v1.0
- ✓ Multimodal Document Anonymization — tool call arguments, JSON payloads, file metadata — v1.0
- ✓ AI Security Firewall — prompt injection, jailbreak detection, outbound content inspection — v1.0
- ✓ Operational Observability — SLO tracking, immutable audit trail, SBOM — v1.0
- ✓ Data Classification & Handling — 5 sensitivity levels, auto-classification, per-level policies — v1.0
- ✓ AI Firewall & DLP — inbound/outbound enforcement, 8 DLP categories, exfiltration detection, MITRE ATT&CK mapping — v1.0
- ✓ AI Governance & Oversight — ISO/IEC 42001 alignment, risk assessment, human oversight, lifecycle management, conformity package — v1.0
- ✓ Financial Services Compliance — MNPI protection, Model Risk Management (SR 11-7), DORA resilience, AML webhook — v1.0
- ✓ Compliance, Audit & Fairness — bias monitoring, data lineage, retention/legal hold, DSAR, breach notification, eDiscovery — v1.0
- ✓ Universal AI Traffic Gateway — reverse/transparent proxy, TLS/MITM, MCP inspection, appliance mode — v1.0
- ✓ Agent & Tool Call Governance — MCP protocol, per-tool permissions, human approval routing — v1.0
- ✓ Network Discovery, CASB & Secure RAG — shadow AI detection, AI SaaS governance, RAG pipeline inspection — v1.0
- ✓ AI SOC/SIEM Integration — Splunk, QRadar, Sentinel, Elastic, Datadog, webhook sinks — v1.0
- ✓ Endpoint Visibility & Sovereign AI Control Plane — desktop agents, local model routing, hybrid AI architecture, air-gapped mode — v1.0
- ✓ CI/CD Test Workflow (HYG-01) — PR testing and automated verification — v1.5
- ✓ Code Quality Enforcement (HYG-02) — global ruff rules and strict mypy verification — v1.5
- ✓ Secure Compose Defaults (HYG-03) — port restriction and Grafana authentication — v1.5
- ✓ Public Trust Center Portal (TRUST-01) — SLO, compliance evidence, and security metrics endpoints — v1.5
- ✓ Trust Center Configuration (TRUST-02) — config-gated access and YAML properties — v1.5
- ✓ Multilingual Documentation (DOCS-01) — docs in FR, ES, PT, IT, AR, NL — v1.5
- ✓ Translation Manifest Tracking (DOCS-02) — manifest-tracked doc review status — v1.5
- ✓ Advanced Secret Detection (GUARD-01) — custom Presidio recognizers for enterprise secrets — v1.5
- ✓ Continuous Compliance Monitoring (GUARD-02) — automated evidence collection snapshots — v1.5
- ✓ Commercial Licensing (GUARD-03) — feature gating and license signature verification — v1.5

### Active

- [ ] **SSO-01**: OAuth2/OIDC/SAML integration for user and application authentication
- [ ] **SSO-02**: RBAC policy engine mapping permissions to client requests
- [ ] **SSO-03**: mTLS certificate-based authentication for client traffic
- [ ] **TEN-01**: Tenant namespacing across cache, config, metrics, and audit logs
- [ ] **TEN-02**: Tenant isolation partitioning in the gateway and database layers
- [ ] **HA-01**: Valkey Sentinel/Cluster support for database scaling and replication
- [ ] **HA-02**: Kubernetes Helm chart and HA deployment profiles
- [ ] **SEC-01**: HashiCorp Vault and cloud secrets manager integration
- [ ] **SEC-02**: Automated cryptographic key rotation

### Out of Scope

- Post-v2.0 enhancements (hardware HSM integration, customer-managed evidence storage, federated control planes)

## Context

- **v1.0 shipped**: 2026-07-07. All 22 phases complete with 101 plans, 179 tasks, ~49,500 lines of Python, 768+ tests.
- **v1.5 shipped**: 2026-07-12. All 5 phases complete with 11 plans, 11 summaries, all technical debt cleaned up.
- **v2.0 started**: 2026-07-12. Enterprise platform and deployment moat development.
- **Tech stack**: Python 3.12, FastAPI, Pydantic Settings, httpx, Redis/Valkey, Presidio Analyzer, prometheus-client, structlog, SQLAlchemy/Alembic, MinIO, pyarrow, reportlab, cryptography, ONNX Runtime, Docker Compose.
- **Test framework**: pytest, Hypothesis (property-based), fakeredis, respx, aioresponses, pytest-asyncio.
- **Deployment**: Multi-stage Dockerfile, docker-compose.yml with anonreq + presidio-analyzer + valkey. Optional observability profile (PostgreSQL, MinIO, Grafana, Prometheus).
- **Governance persistence**: PostgreSQL via SQLAlchemy/Alembic (optional, for audit trail, governance records, lineage).
- **Deferred**: Post-v2.0 enhancements (HSM integration, customer-managed evidence storage, federated control planes).

## Constraints

- **Fail-secure**: Any error → HTTP 5xx, never forward unsanitized data. Non-negotiable.
- **No PII in logs**: Metadata-only audit; field allowlist enforced. The audit log itself must not become a PII liability.
- **Ephemeral cache only**: Redis with `save ""`, no AOF, no RDB. Mapping exists only in RAM during request lifecycle.
- **Token format**: `[TYPE_N]` — case-insensitive + bracket-optional matching during restoration.
- **OpenAI-compatible input schema**: Single wire protocol; adapters translate for other providers.
- **Session-scoped mapping**: `anonreq:{Session_ID}` key, TTL 60–3600s, deleted post-response.
- **Multi-locale**: `X-AnonReq-Locale` header, 8 locales, locale-specific recognizer bundles.
- **License**: Apache 2.0.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python 3.12 + FastAPI | Best ecosystem fit for Presidio integration, async support for SSE streaming, strong typing | ✓ Good — served all 22 phases, 768+ tests |
| Single wire protocol (OpenAI schema) | Minimum friction for existing OpenAI SDK users; adapters for others | ✓ Good — Anthropic/Gemini/Ollama adapters built and tested |
| Microsoft Presidio Analyzer | Mature NER pipeline with regex support, locale extensibility, active community | ✓ Good — 8 locale bundles with checksum validation |
| Valkey over Redis | Open-source fork with identical API, no licensing concerns | ✓ Good — seamless drop-in replacement |
| Property-based tests (Hypothesis) | Required by Req 16 for generative proof of correctness | ✓ Good — 50+ property tests proving invariants |
| Phase 22 gap-closure approach | Wired 6 audit-blocked enterprise/appliance modules into runtime paths | ✓ Good — all critical integration gaps closed, 27 integration tests |
| Proxy-to-pipeline dispatcher adapter | Bridge proxy dispatch() contract to PipelineManager.run() | ✓ Good — 9 unit tests, fail-closed on all error paths |
| Delete non-functional test files (D-01/D-02) | Restores CI collection cleanliness without cluttering workspace | ✓ Good — pytest collections clean |
| Default-enable Trust Center config (D-04/D-05) | Exposing Trust Center public endpoints by default aligns with its no-auth design | ✓ Good — public portal active |
| Correct hygiene summary doc (D-07) | Reflects the global ruff rules and mypy override model in project reality | ✓ Good — docs match reality |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-12 after Milestone v2.0 initialization*

