# Roadmap: AnonReq

## Overview

AnonReq is the **AI Security Gateway for regulated enterprises** — a self-hosted anonymization
gateway that intercepts outbound LLM API calls, detects/replaces PII with context-preserving
tokens, forwards sanitized requests to external LLM providers, and restores original values in
responses. All in-memory, no data written to disk.

Core principle: **Raw PII never crosses the network boundary.**

The roadmap is organized into three stages:

| Stage | Phases | Goal | Customer |
|-------|--------|------|----------|
| **1. Prove the Problem** | 1–7 | MVP deployment-ready gateway | Law firms, accounting firms, mid-market |
| **2. Build the Enterprise Platform** | 8–16 | Enterprise security & compliance product | Banks, insurers, healthcare, government |
| **3. Build the Moat** | 17–21 | AI governance & sovereign control plane | Global enterprises, regulated industries |

---

## Stage 1: Prove the Problem (Phases 1–7)

Goal: Demonstrate that enterprises can safely use external AI systems without exposing sensitive
data. Each phase delivers a working, independently verifiable vertical slice.

**Three hardening decisions embedded across these phases:**

1. **Fail-secure error boundaries and auth are Phase 1, Plans 01-02 and 01-05** — the global
   exception handler, structured logging (no-PII enforcement), and static bearer token middleware
   are built before any pipeline code.

2. **Classification runs before anonymization (Phase 2, Plan 02-02)** — payloads are classified
   into BLOCK / ROUTE_LOCAL / ANONYMIZE / PASS before they reach Presidio.

3. **Property-based tests are written alongside the phases they prove** — round-trip correctness
   and token uniqueness tests land in Phase 2; streaming split-token tests land in Phase 3.

---

### Phase 1: Foundation, Fail-Secure & Auth

**Goal**: As an operator, I want to deploy a leak-free, authenticated gateway scaffold, so that I can securely route LLM requests with confidence that errors never leak data, dependencies are healthy, and access is controlled.

**Mode**: mvp
**Depends on**: Nothing (first phase)
**Requirements**: DOCK-01 to DOCK-07, FAIL-01 to FAIL-04, AUDT-01 to AUDT-03, AUTH-MINIMAL-01

**Success Criteria**:

1. Global exception handler intercepts all errors and returns static HTTP 500. No request body,
   stack trace, token value, or PII substring appears in response or logs.

2. Structured JSON logger writes to stdout using a strict field allowlist. Non-allowlisted
   fields are stripped, not redacted.

3. Operator can deploy all 3 containers (`anonreq`, `presidio-analyzer`, `valkey`) with
   `docker compose up`. All services healthy within 60 seconds.

4. Pre-flight checks prevent gateway startup when Valkey or Presidio is unreachable. Clear
   error message identifies the unhealthy component.

5. All routes return HTTP 401 when `Authorization: Bearer <token>` is absent or does not match
   `ANONREQ_API_KEY`. Startup fails if `ANONREQ_API_KEY` is unset or < 32 characters.

**Plans**: 4 plans

- [ ] 01-01: Project scaffold + configuration management (Pydantic Settings, env validation)
- [ ] 01-02: Docker Compose deployment (multi-stage Dockerfile, valkey + presidio sidecars)
- [ ] 01-03: Fail-secure exception handler + audit logging + health/pre-flight checks
- [ ] 01-04: Static bearer token auth + RequestContext

---

### Phase 2: Core Pipeline & Classification (Non-Streaming)

**Goal**: Full non-streaming pipeline — classifies payload first (Block/Route/Anonymize/Pass),
then detects PII via regex and NER, tokenizes with `[TYPE_N]` placeholders, forwards sanitized
request to OpenAI, caches mapping in Valkey, restores original values, and cleans up.
Correctness proven by Hypothesis tests before Phase 3 begins.

**Mode**: mvp
**Depends on**: Phase 1
**Requirements**: PIPE-01 to PIPE-06, FAIL-01 to FAIL-02, DET-01 to DET-06, TOKN-01 to TOKN-07,
CACH-01 to CACH-06, PROV-01, AUDT-04 to AUDT-05, CLASS-AC-01 to 05, TEST-01 to TEST-03

**Success Criteria**:

1. Classification runs before Presidio is called. Payloads matching BLOCK rules return HTTP 403
   with audit entry; ROUTE_LOCAL forwards to configured on-prem endpoint. Four tiers:
   PASS / ANONYMIZE / ROUTE_LOCAL / BLOCK, YAML-configurable at startup.

2. PII detected by regex tier (email, phone, credit card, IBAN, IP, URL, DOB, national IDs,
   SWIFT, crypto) and NER tier (names, orgs, addresses, job titles). Regex wins on overlap.

3. Same entity value repeated → same token (deduplication). Different values of same type →
   distinct tokens with different indices.

4. When detection engine or cache is unhealthy, all requests return HTTP 503, zero data
   forwarded upstream.

5. Hypothesis tests pass: round-trip correctness (byte-for-byte match) and token uniqueness
   (N distinct values → N distinct tokens; same value K times → 1 token).

**Plans**:

- [x] 02-01-PLAN.md
- [x] 02-02-PLAN.md
- [x] 02-03-PLAN.md
- [x] 02-04-PLAN.md
- [ ] 02-05-PLAN.md

4/5 plans executed
      health check, monitoring lockdown)

- [x] 02-02: Classification engine (4-tier YAML rules) + Detection engine (regex + NER via
      Presidio, confidence thresholds, exclusion lists, custom YAML)

- [x] 02-03: Tokenization engine (`[TYPE_N]`, deduplication, reverse-offset, random seed)
- [x] 02-04: Pipeline orchestration (POST /v1/chat/completions, step sequence, fail-secure)
- [ ] 02-05: Property tests (round-trip, token uniqueness, deduplication, BLOCK invariant)

---

### Phase 3: SSE Streaming + Multi-Provider

**Goal**: Streaming responses with real-time token restoration via Tail_Buffer FSM.
Multi-provider support for Anthropic, Gemini, and Ollama via Provider_Adapter translation
layer. Client disconnect handling. Streaming correctness proven by Hypothesis.

**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: SSE-01 to SSE-08, PROV-02 to PROV-08, CACH-05, TEST-07

**Plan execution order**: 03-02 → 03-01 → 03-03 → 03-04 (provider wire formats must be
understood before Tail_Buffer FSM is built).

**Success Criteria**:

1. `stream: true` requests return `text/event-stream` without full-response buffering. Tokens
   restored in real-time. Anti-buffering headers present.

2. Tokens split across SSE chunk boundaries correctly restored via Tail_Buffer (512-char max).
   Every split position produces byte-for-byte match with non-streamed response.

3. Prompts route to Anthropic Claude, Google Gemini, and Ollama via model alias.
   `GET /v1/models` returns all configured aliases.

4. On client disconnect: upstream HTTPX stream cancelled, Valkey mapping deleted, disconnect
   event logged. No orphaned connections after 100 concurrent disconnects.

5. Hypothesis streaming tests pass: all split-token positions produce byte-for-byte match.

**Plans**:

- [ ] 03-02: Provider adapters — Anthropic, Gemini, Ollama (execute first)
- [ ] 03-01: SSE streaming route with Tail_Buffer FSM, HGETALL pre-fetch, case-insensitive +
      bracket-optional matching, flush heuristics, client disconnect handling

- [ ] 03-03: Model alias routing and `GET /v1/models` endpoint
- [ ] 03-04: Streaming property tests (Hypothesis) + disconnect load test

---

### Phase 4: Multi-Locale Detection + Compliance Presets

**Goal**: PII detection in 8 locales via `X-AnonReq-Locale` header with locale-specific regex
recognizer bundles and checksum validation for national IDs. Per-jurisdiction compliance
presets enforce mandated entity detection at startup.

**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: LOCL-01 to LOCL-07, COMP-01 to COMP-05

**Success Criteria**:

1. `X-AnonReq-Locale: de-DE` activates German detection (Steuer-ID with modulo-11 checksum).
   `fr-FR` detects NIR. `pt-BR` detects CPF/CNPJ. All 8 locales active.

2. Multiple locales (`de-DE, fr-FR`) produce merged detection (union, highest confidence).
3. Unsupported/malformed locale → HTTP 400. Missing locale → universal recognizers only + log.
4. Compliance preset (`gdpr`) enforces mandated entity types at startup. Startup rejects config
   that disables preset-mandated types.

5. Audit log includes `compliance_preset` field. Merged presets: union of types, highest
   confidence threshold.

**Plans**:

- [x] 04-01: Locale recognizer bundles (8 YAML configs with checksum validation)
- [x] 04-02: Locale negotiation (header parsing, multi-locale merging, fallback, checksums)
- [x] 04-03: Compliance preset engine (6 presets, startup validation, merge, audit field,
      `GET /v1/compliance/presets`)

---

### Phase 5: Configuration & Observability

**Goal**: Operational monitoring with Prometheus metrics, P95 latency validation under load,
post-restoration token verification, and custom detection rules API.

**Mode**: mvp
**Depends on**: Phase 3
**Requirements**: METR-01 to METR-03, PIPE-06, DET-06

**Success Criteria**:

1. `GET /metrics` returns Prometheus counters: requests, detection latency (ms histogram),
   entities by type, unrestored tokens, fail-secure events, audit failures.

2. Non-streaming responses scanned for `\[[A-Z]+_\d+\]` post-restoration. Streaming scanned
   on assembled text. Residual tokens increment counter and log warning.

3. P95 processing overhead ≤ 100ms at 50 concurrent users, 1,000-word prompts, 60s sustained.
   Default Presidio model: `en_core_web_sm`. Load test result logged as build artifact.

4. `GET /v1/config/rules` returns active custom recognizers and exclusion list count.

**Plans**:

- [x] 05-01-PLAN.md
- [x] 05-02-PLAN.md
- [x] 05-TEST-PLAN.md

3/3 plans executed

- [x] 05-01: Prometheus metrics endpoint + k6 load test
- [x] 05-02: Post-restoration token verification scan (non-streaming + post-stream) + Admin API hot-reload

---

### Phase 6: Advanced Property-Based Tests

**Goal**: Complete the generative test suite for edge cases not covered in Phases 2 and 3.

**Mode**: mvp
**Depends on**: Phase 4, Phase 5
**Requirements**: TEST-04 to TEST-06, TEST-08

**Success Criteria**:

1. Hypothesis confirms fail-secure: detection/cache/timeout failure → HTTP 500, 0 forwarded.
2. Hypothesis confirms no-PII-in-logs: synthetic PII across all pipeline paths produces zero
   PII substrings in log output.

3. Hypothesis confirms cross-request randomization: 1,000+ session pairs, same PII value,
   different tokens across sessions, P(duplicate) ≥ 1 − 2⁻³².

4. Locale checksum tests: invalid checksum IDs (Steuer-ID, BSN, NIR, CPF, CNPJ, Codice Fiscale)
   are not flagged as valid detections.

**Plans**:

- [x] 06-01: Fail-secure and no-PII-in-logs property tests
- [x] 06-02: Cross-request randomization probability test
- [ ] 06-03: Locale checksum invalidation tests

---

### Phase 6.5: Production Readiness Review

**Goal**: Validate operational readiness before opening the gateway to external developers. This phase produces no code — it produces confidence.

**Mode**: mvp
**Depends on**: Phase 6 (all security gates must pass)
**Requirements**: None (operational — documents Phase 5 load test, Phase 6 security gate, Docker/container patterns)

**Success Criteria**:

1. PRR.md documents deployment architecture, dependencies, resource requirements, and scaling limits.
2. THREAT_MODEL.md documents trust boundaries, attack surface, data flow risks, and mitigations.
3. DEPLOYMENT_GUIDE.md documents Docker Compose and Kubernetes deployment with all env vars.
4. RUNBOOK.md documents startup/shutdown, health checks, log interpretation, restart procedures.
5. SRE_PLAYBOOK.md documents incident classification, response procedures, escalation paths.
6. Docker deployment verified end-to-end with real provider credentials.

**Plans**:

- [ ] 06.5-01: Production Readiness Review document set — **Planned**

---

### Phase 7: Developer Experience & Documentation

**Goal**: Open-source ready repository with quickstarts, SDK examples, and legal files.

**Mode**: mvp
**Depends on**: Phase 6
**Requirements**: DOCS-01 to DOCS-05

**Success Criteria**:

1. Developer can run executable quickstart scripts from `examples/quickstart/` and see
   working anonymization in under 5 minutes.

2. SDK examples for curl, Python, TypeScript, and Go are standalone runnable projects,
   demonstrating basic anonymization, streaming, GDPR preset, and locale detection.

3. Repository includes Apache 2.0 LICENSE, NOTICE file (third-party attributions), SECURITY.md,
   and 13-section README covering "Why AnonReq" and "License and Commercial Use".

4. CHANGELOG.md follows Keep a Changelog format with entries for all 7 phases.
5. Documentation CI validates markdown, links, Mermaid diagrams, OpenAPI sync, CHANGELOG format,
   and quickstart execution on every PR.

6. Documentation available in English (source) and German (generated).

**Plans**:

- [x] 07-01: Integration quickstarts (EN) + doc structure (docs/en/, architecture diagram, OpenAPI export)
- [x] 07-02: SDK examples (curl, Python, TypeScript, Go) and README (13 sections)
- [x] 07-03: CHANGELOG, Apache 2.0 LICENSE, NOTICE file, SECURITY.md, CI workflows, DE translations

---

### Stage 1 Progress

**Execution order**: 1 → 2 → 3 → 4 → 5 → 6 → 6.5 → 7
**Within Phase 3**: plans execute in order 03-02 → 03-01 → 03-03 → 03-04

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 1. Foundation, Fail-Secure & Auth | 4/4 | Planned | — |
| 2. Core Pipeline & Classification | 4/5 | In Progress|  |
| 3. SSE Streaming + Multi-Provider | 3/4 | In Progress | — |
| 4. Multi-Locale + Compliance Presets | 4/4 | Complete | 2026-07-02 |
| 5. Configuration & Observability | 3/3 | Complete | 2026-07-02 |
| 6. Advanced Property-Based Tests | 4/4 | Complete | 2026-07-02 |
| 6.5. Production Readiness Review | 0/1 | Planned | — |
| 7. Developer Experience & Docs | 3/3 | Planned | — |
| **Stage 1 Total** | **23/25** | | |

---

## Stage 2: Build the Enterprise Platform (Phases 8–16)

Goal: Transform the gateway into an enterprise security product with enforcement, observability,
governance, and financial-services compliance.

---

### Phase 8: Rate Limiting & Spend Controls

**Goal**: Platform operators can enforce per-tenant rate limits and spend budgets at the gateway.

**Mode**: enterprise
**Depends on**: Phase 1 (Valkey, FastAPI middleware)
**Requirements**: Req 22

**Success Criteria**:

1. Operator configures RPM/TPM/concurrent rate limits per tenant → HTTP 429 with `Retry-After`.
2. Operator sets daily/monthly spend budgets per tenant → HTTP 402 with structured error body.
3. Operator queries current usage via `GET /v1/admin/tenants/{tenant_id}/usage`.
4. Usage resets at daily (00:00 UTC) and monthly (1st) boundaries; `budget_reset` audit events.
5. Gateway fails closed (HTTP 503) when cache unavailable.

**Plans**: TBD

---

### Phase 9: Multimodal Document Anonymization

**Goal**: Anonymize all content types — tool call arguments, JSON payloads, file metadata.

**Mode**: enterprise
**Depends on**: Phase 2 (Presidio pipeline, provider adapters)
**Requirements**: Req 23

**Success Criteria**:

1. Tool call arguments (`tool_calls` JSON) and tool results (`tool` role content) anonymized.
2. JSON documents recursively scanned at string-valued leaf nodes; JSON structural validity
   preserved after anonymization.

3. Multimodal metadata (file names, `image_url` descriptions) anonymized.
4. Unsupported content types → HTTP 415 with descriptive error.
5. Property-based test: anonymize→restore produces byte-for-byte identical document.

**Plans**: TBD

---

### Phase 10: AI Security Firewall

**Goal**: Detect and block prompt injection attempts, jailbreak patterns, and policy-violating
LLM outputs at the infrastructure layer.

**Mode**: enterprise
**Depends on**: Phase 1 (pipeline architecture)
**Requirements**: Req 36

**Success Criteria**:

1. Inbound prompts inspected for direct injection, indirect injection, and role-confusion
   attacks at configurable threshold (default 0.85) → HTTP 400 with `prompt_injection_detected`.

2. Jailbreak attempts detected via YAML rule set with `block` / `flag_and_forward` / `monitor`.
3. Outbound LLM responses inspected for policy-violating content → HTTP 451 on violation.
4. Hot-reload rule set within 60 seconds without restart (same mechanism as Req 11).
5. All events logged with Prometheus counters (`anonreq_prompt_security_events_total`) and
   structured audit entries.

**Plans**: 5 plans (Waves: foundation, detection, streaming, admin API, property tests)

---

### Phase 11: Operational Observability & Compliance Infrastructure

**Goal**: SLO tracking, immutable audit trail for config changes, and supply chain SBOM.

**Mode**: enterprise
**Depends on**: Phase 8 (rate limit metrics)
**Requirements**: Req 24, 25, 26

**Success Criteria**:

1. SRE views SLO compliance at `GET /v1/governance/status`. SLOs: success ≥ 99.9%, P95 ≤ 100ms,
   fail-secure ≤ 0.1%, audit write ≥ 99.99%. Breach alerting via webhook.

2. Security officer queries immutable config change audit trail with pagination, filters,
   JSON Lines export. 7-year retention.

3. CycloneDX SBOM per release build. Container image SBOM via Syft. OCI attestation via cosign.
   Dependabot weekly scans.

**Plans**: TBD

---

### Phase 12: Data Classification & Handling Policies

**Goal**: Every request classified by sensitivity level with per-level handling policies.

**Mode**: enterprise
**Depends on**: Phase 2 (entity detection for auto-classification)
**Requirements**: Req 41

**Success Criteria**:

1. Five classification levels: `Public`, `Internal`, `Confidential`, `Restricted`,
   `Highly Restricted`.

2. Auto-classification based on highest-sensitivity detected entity type. Undetected defaults
   to `Internal`. Configurable entity-type-to-classification mapping.

3. Client-asserted `X-AnonReq-Classification` header supported. Higher of client vs detected
   classification wins. Overrides logged.

4. Per-level handling policies: `allow_and_anonymize` (≤ Confidential), `anonymize_and_flag`
   (Restricted), `block` (Highly Restricted). Block returns HTTP 451.

5. Classification_Level in every audit log entry.

**Plans**: TBD

---

### Phase 13: AI Firewall & Data Loss Prevention

**Goal**: Active inbound/outbound AI security enforcement and AI-specific DLP controls across
all AI traffic types.

**Mode**: enterprise
**Depends on**: Phase 10 (prompt firewall), Phase 12 (classification for DLP context)
**Requirements**: APPL-05 (AI Firewall), APPL-02 (AI DLP)

**Success Criteria**:

1. Inbound AI firewall: injection, jailbreak, data exfiltration, model manipulation, agent
   abuse — with MITRE ATT&CK mapping.

2. Outbound AI firewall: PII reconstruction, harmful content, data exfiltration encoding
   (Base64, hex, stego) → HTTP 451 suppression.

3. DLP policies classify traffic into 8 categories: PII, PHI, PCI, MNPI, Trade Secrets,
   Source Code, Financial Records, Customer Data.

4. Per-category actions: allow / anonymize / redact / quarantine / block. Contextual rules
   combine category + business unit + Classification_Level.

5. All events logged with Prometheus counters and structured audit entries.

**Plans**: TBD

---

### Phase 14: AI Governance & Oversight

**Goal**: Structured governance framework aligned with ISO/IEC 42001:2023 and EU AI Act,
with risk management, human oversight, transparency, and lifecycle management.

**Mode**: enterprise
**Depends on**: Phase 2 (pipeline for session-level hooks)
**Requirements**: Req 27, 28, 29, 30, 31, 35

**Success Criteria**:

1. Governance records per tenant with named owners (governance/risk/compliance/security).
   Governance review cycle (default 90 days). Overdue reviews surfaced in status.

2. Risk assessment records per tenant across 6 dimensions with severity/likelihood and
   treatment plans. Config changes affecting entity types trigger reassessment flag.

3. Human oversight: approval queue for high-risk requests (HTTP 202 pending), approve/reject
   endpoints, kill-switch (`POST /v1/oversight/kill-switch`), session summary endpoint
   (metadata only, no raw content).

4. Transparency: `X-AnonReq-Processed` and `X-AnonReq-Entity-Count` response headers.
   Transparency records per session. Periodic transparency reports.

5. Lifecycle management: provider/preset lifecycle stages (design → retired) with approval
   gates. Production activation requires completed testing + risk assessment.

6. Conformity assessment package: `GET /v1/admin/compliance/conformity-package` returns ZIP
   with SBOM, governance export, risk assessments, config audit history, bias report, manifest.

**Plans**: 0/1 plans executed

- [ ] 14-TEST-PLAN.md

---

### Phase 15: Financial Services Compliance

**Goal**: Financial-sector regulatory compliance with MNPI protection, Model Risk Management,
third-party provider oversight, financial crime controls, and DORA resilience.

**Mode**: enterprise
**Depends on**: Phase 4 (locale detection for MNPI), Phase 12 (classification)
**Requirements**: Req 37, 38, 39, 40, 42, 43

**Success Criteria**:

1. Compliance mapping document covering DORA, NIS2, GDPR, ISO 27001/42001, EBA, FCA, SEC,
   FINRA. Regulator-ready reports via `GET /v1/admin/compliance/report?framework={id}`.

2. MNPI recognizer bundle (ticker symbols, deal codenames, restricted names list). 4 policies:
   anonymize_and_forward / flag_and_forward / block / quarantine. SEC 17a-4 retention.

3. Model Risk Management: model inventory (risk classification, approval status, review cycles).
   Approval gating blocks unapproved models. SR 11-7 alignment documentation.

4. Third-party provider inventory with DORA ICT concentration risk flagging. Provider
   suspension endpoint. Annual concentration risk justification for critical providers.

5. Financial crime controls: context-word boosting (0.15 confidence increase within 50 chars).
   AML webhook integration. Structured audit events for AML platform consumption.

6. DORA operational resilience: critical service classification auto-escalates incidents.
   Resilience testing procedures. ICT third-party register export.

**Plans**: TBD

---

### Phase 16: Compliance, Audit & Fairness

**Goal**: Bias monitoring, post-deployment surveillance, data lineage, record retention,
data subject rights, and breach notification.

**Mode**: enterprise
**Depends on**: Phase 4 (locale data for fairness datasets)
**Requirements**: Req 32, 33, 34, 44, 45, 46, 47

**Success Criteria**:

1. Fairness testing datasets per locale (200+ examples per demographic group). CI/CD bias
   assessment on every release: recall disparity across groups ≤ 0.05. Build fails if exceeded.

2. Third-party AI supplier governance: provider inventory with contract/risk/review status.
   Provider review cycle (default 365 days). Overdue reviews surfaced in governance status.

3. Post-deployment monitoring: detection quality drift, fail-secure frequency, SLO compliance.
   Incident classification (S1 data exposure / S2 degradation / S3 anomaly). Incident
   management endpoints and export.

4. Immutable lineage records per session with full provenance (session_id, timestamps,
   provider, model, entities, policies). No API to modify or delete lineage records.

5. Record retention schedules with Legal Hold support. Hold suspension blocks deletion.
   Export for eDiscovery.

6. Data subject rights: DSAR intake, erasure, rectification, portability, and restriction
   workflows. Status tracking and audit trail for each request.

7. Breach notification automation: configurable templates, regulator notification queue,
   affected-tenant notification workflow.

**Plans**: TBD

---

### Stage 2 Progress

**Execution order**: Phases 8, 9, 10, 12, and 14 are independent (all start from Stage 1).
Phase 11 depends on Phase 8. Phase 13 depends on Phase 10 + Phase 12. Phase 15 depends on
Phase 4 + Phase 12. Phase 16 is independent.

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 8. Rate Limiting & Spend Controls | 0/TBD | Not started | — |
| 9. Multimodal Document Anonymization | 0/TBD | Not started | — |
| 10. AI Security Firewall | 0/5 | Planned | — |
| 11. Operational Observability & Compliance | 0/TBD | Not started | — |
| 12. Data Classification & Handling | 0/TBD | Not started | — |
| 13. AI Firewall & Data Loss Prevention | 0/TBD | Not started | — |
| 14. AI Governance & Oversight | 0/1 | Planned    |  |
| 15. Financial Services Compliance | 0/TBD | Not started | — |
| 16. Compliance, Audit & Fairness | 0/TBD | Not started | — |
| **Stage 2 Total** | **0/TBD** | | |

---

## Stage 3: Build the Moat (Phases 17–21)

Goal: Become the enterprise control plane for AI — universal traffic interception, agent
governance, CASB, SIEM integration, and sovereign AI control.

---

### Phase 17: Universal AI Traffic Gateway

**Goal**: Route all AI interactions through a single enforcement point. Support reverse proxy,
transparent proxy, and appliance deployment topologies.

**Mode**: appliance
**Depends on**: Phase 1 (proxy architecture)
**Requirements**: APPL-01 (Req 48)

**Success Criteria**:

1. All AI interaction types routed through single gateway: chat, voice bots, agent frameworks,
   RAG, MCP, email/CRM AI integrations.

2. Deployment topologies: reverse proxy, transparent proxy (TLS interception with
   tenant-managed CA cert + re-origination), virtual appliance, physical appliance.

3. Block all non-intercepted AI API traffic via configurable `block-all-unintercepted-AI`
   policy.

4. P95 overhead ≤ 5ms for proxy-only mode (no anonymization — policy evaluation only).
5. Inline inspection of MCP protocol traffic, tool call/result payloads, and structured content.

**Plans**: TBD

---

### Phase 18: Agent & Tool Call Governance

**Goal**: Inspect all agent actions before execution with per-tool permission policies.
Support MCP protocol and OpenAI/Anthropic tool call/result payloads.

**Mode**: appliance
**Depends on**: Phase 9 (multimodal for tool call anonymization)
**Requirements**: APPL-04 (Req 51)

**Success Criteria**:

1. MCP protocol traffic and OpenAI/Anthropic tool call/result payloads inspected.
2. Per-tool permission policies: `allow`, `allow_with_audit`, `require_human_approval`, `block`.
3. Tool call parameters anonymized for external API targets; tool results inspected for
   sensitive data.

4. Agent execution suspended for tools requiring human approval; routed through oversight
   queue (Phase 14).

5. Audit entries: `tool_allowed`, `tool_blocked`, `tool_approval_required` with structured
   details.

**Plans**: 4/4 plans executed

- [x] 18-01-PLAN.md — Tool permission policy, extraction, PDP #2 evaluation
- [x] 18-02-PLAN.md — Async human approval flow, tool result inspection
- [x] 18-03-PLAN.md — Observability, metrics, property-based tests
- [x] 18-TEST-PLAN.md — Test specification

---

### Phase 19: Network Discovery, CASB & Secure RAG

**Goal**: Shadow AI detection, AI SaaS governance, and RAG pipeline protection.

**Mode**: appliance
**Depends on**: Phase 1 (proxy architecture)
**Requirements**: APPL-06, APPL-07, APPL-08

**Success Criteria**:

1. AI API traffic identified by hostname/IP across 8+ providers (OpenAI, Anthropic, Gemini,
   AWS Bedrock, Azure OpenAI, Mistral, Cohere, local LLMs).

2. Shadow AI traffic detected via network flow/DNS analysis. `shadow_ai_detected` event
   emitted. AI asset inventory exportable as JSON/CSV.

3. AI SaaS usage monitored via corporate proxy/CASB telemetry. Applications classified as
   sanctioned / tolerated / unsanctioned with per-app policies.

4. RAG pipeline documents inspected at retrieval injection point. Full detection pipeline
   applied to retrieved content before LLM exposure.

5. Tokens restored in RAG-anonymized content within LLM response. `rag_content_anonymized`
   audit entry.

**Plans**: TBD

---

### Phase 20: AI SOC/SIEM Integration

**Goal**: Security analysts can monitor AI security events within enterprise SIEM across all
major platforms.

**Mode**: appliance
**Depends on**: Phase 10 (firewall events), Phase 13 (firewall + DLP), Phase 12 (classification)
**Requirements**: APPL-09 (Req 56)

**Success Criteria**:

1. Structured events generated for: firewall violations, DLP actions, shadow AI detection,
   prompt security events, agent governance actions.

2. SIEM sinks: Splunk (HEC), IBM QRadar (syslog CEF), Microsoft Sentinel (Data Collection
   Rules API), Elastic (Bulk API), Datadog (Logs API).

3. Events include `mitre_technique_id`, `severity`, `event_type`, `tenant_id`, `session_id`,
   `timestamp`, `gateway_version`. No raw prompt content.

4. Sink health status available at `GET /v1/admin/soc/integration/status`.
5. Local event buffer (max 10k events) with exponential backoff retry. `soc_buffer_overflow`
   when full (discard oldest, never block processing).

**Plans**: TBD

---

### Phase 21: Endpoint Visibility & Sovereign AI Control Plane

**Goal**: Desktop agents for local traffic inspection, AI application discovery, and sovereign
AI deployment with local model routing and GPU inference integration.

**Mode**: appliance
**Depends on**: Phase 17 (universal gateway)
**Requirements**: roadmap4 Phases 8–10

**Success Criteria**:

1. Desktop agents for Windows and macOS. Local traffic inspection and AI application discovery
   (Cursor, Claude Desktop, ChatGPT Desktop, VS Code extensions, Copilot).

2. Local model routing: route prompts to on-prem LLMs via vLLM, Ollama, or GPU inference
   endpoints based on classification level.

3. Sovereign deployment policies: enforce data residency by jurisdiction. Route by
   classification: Public → OpenAI, Internal → Claude EU, Confidential → Local Llama,
   Restricted → Block.

4. Hybrid AI architecture: gateway chooses provider per request based on policy + data
   sensitivity + jurisdiction.

5. Air-gapped deployment mode: all provider traffic routed to local models, no external
   network required.

**Plans**: TBD

---

### Stage 3 Progress

**Execution order**: Phase 17 is independent (starts from Stage 1). Phase 18 depends on Phase 9.
Phase 19 is independent. Phase 20 depends on Phases 10, 12, 13. Phase 21 depends on Phase 17.

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 17. Universal AI Traffic Gateway | 0/TBD | Not started | — |
| 18. Agent & Tool Call Governance | 0/1 | Planned    |  |
| 19. Network Discovery, CASB & Secure RAG | 0/TBD | Not started | — |
| 20. AI SOC/SIEM Integration | 0/TBD | Not started | — |
| 21. Endpoint Visibility & Sovereign Control | 0/TBD | Not started | — |
| **Stage 3 Total** | **0/TBD** | | |

---

## Summary

| Stage | Phases | Plans | Status |
|-------|--------|-------|--------|
| 1. Prove the Problem | 7 (1–7) | 25 | 23/25 Complete |
| 2. Build the Enterprise Platform | 9 (8–16) | TBD | Not started |
| 3. Build the Moat | 5 (17–21) | TBD | Not started |
| **Total** | **21** | **25+TBD** | |

---

*Consolidated from roadmap1.md, roadmap2.md, roadmap3.md, roadmap4.md, req/ROADMAP.md,
and .planning/REQUIREMENTS.md. Last updated: 2026-06-19.*
