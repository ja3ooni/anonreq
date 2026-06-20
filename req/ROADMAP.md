# Roadmap: AnonReq

## Milestones

- ✅ **v1.0 MVP** — Phases 1-9 (shipped 2026-06-18)
- 🚧 **v1.1 Enterprise** — Phases 10-19 (in planning)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-9)</summary>

- [] Phase 1: Foundation (1/1 plans) 
- [] Phase 2: Detection & Cache (3/3 plans) 
- [] Phase 3: Non-Streaming Proxy (4/4 plans) 
- [] Phase 4: Streaming Support (3/3 plans) 
- [] Phase 5: Multi-Provider Support (7/7 plans) 
- [] Phase 6: Custom Rules & Configuration (3/3 plans) 
- [] Phase 7: Audit & Deployment (4/4 plans) 
- [] Phase 8: Property-Based Test Suite (3/3 plans) 
- [] Phase 9: Enterprise Authentication & RBAC (3/3 plans) 


</details>

### 🚧 v2.0 Enterprise (In Planning)

**Milestone Goal:** Extend AnonReq with enterprise-grade capabilities focused on competitive differentiation — prompt security firewall, AI firewall, AI-aware DLP, agent/MCP governance, universal AI traffic gateway, and SOC/SIEM integration, backed by rate limiting, multimodal anonymization, observability, data classification, and audit infrastructure.

- [ ] **Phase 10: Rate Limiting & Spend Controls** — Per-tenant RPM/TPM/concurrent rate limits and daily/monthly spend budgets via Valkey-backed sliding window
- [ ] **Phase 11: Prompt Security Firewall** — Injection, jailbreak, and output policy violation detection with hot-reloadable rule sets
- [ ] **Phase 12: Multimodal Document Anonymization** — Tool call arguments, JSON payloads, and file metadata anonymization with structural preservation
- [ ] **Phase 13: Operational Observability & Audit Infrastructure** — SLO tracking, Prometheus metrics, config change audit trail, and supply chain SBOM
- [ ] **Phase 14: Data Classification & Handling Policies** — 5-level sensitivity classification with auto-detection and per-level handling policies
- [ ] **Phase 15: AI Firewall & Data Loss Prevention** — Inbound/outbound AI firewall with MITRE ATT&CK mapping and AI-aware DLP with 8-category policies
- [ ] **Phase 16: Universal AI Traffic Gateway** — Reverse proxy, transparent proxy (TLS interception), and appliance deployment topologies
- [ ] **Phase 17: Agent & Tool Call Governance** — MCP protocol inspection and per-tool permission policies for agent frameworks
- [ ] **Phase 18: Network Discovery, CASB & Secure RAG** — Shadow AI detection, AI SaaS governance, and RAG pipeline protection
- [ ] **Phase 19: AI SOC/SIEM Integration** — Structured AI security events to Splunk, QRadar, Sentinel, Elastic, Datadog

## Phase Details

### Phase 10: Rate Limiting & Spend Controls
**Goal**: Platform operators can enforce per-tenant rate limits and spend budgets at the gateway
**Depends on**: v1.0 Foundation (Valkey, FastAPI middleware)
**Requirements**: RATELIMIT-01
**Success Criteria** (what must be TRUE):
  1. Operator can configure RPM/TPM/concurrent rate limits per tenant → limits enforced with HTTP 429 + `Retry-After`
  2. Operator can set daily/monthly spend budgets per tenant → budgets enforced with HTTP 402 + structured error body
  3. Operator can query current usage per tenant via `GET /v1/admin/tenants/{tenant_id}/usage`
  4. Usage resets at daily (00:00 UTC) and monthly (1st) boundaries; `budget_reset` audit events logged
  5. Gateway fails closed (HTTP 503) when cache unavailable
**Plans**: TBD

### Phase 11: Prompt Security Firewall
**Goal**: CISO can detect and block prompt injection, jailbreaks, and policy-violating LLM outputs
**Depends on**: v1.0 Foundation
**Requirements**: FIREWALL-01
**Success Criteria** (what must be TRUE):
  1. System detects direct/indirect injection and role-confusion attacks at configurable threshold → HTTP 400 with reason code
  2. System detects jailbreak attempts via configurable YAML rule set with `block`/`flag_and_forward`/`monitor` actions
  3. System inspects LLM responses for policy-violating content → HTTP 451 on violation
  4. Security team can hot-reload rule set within 60 seconds without restart
  5. All firewall events logged with Prometheus counters and audit entries
**Plans**: 5 in 5 waves

**Wave 1** *(standalone — Wave 1 first)*
- 11-01: Firewall Foundation — Abstract Interfaces, Rule Model & Config

**Wave 2** *(blocked on Wave 1 completion)*
- 11-02: Detection Engine, Scoring & Middleware Integration

**Wave 3** *(blocked on Wave 2 completion)*
- 11-03: Outbound Response Inspection & Streaming Support

**Wave 4** *(blocked on Wave 1 completion)*
- 11-04: Admin API, Audit Events & Metrics Exposition

**Wave 5** *(blocked on Wave 4 completion)*
- 11-05: Programmatic Test Generation & Property-Based Tests

### Phase 12: Multimodal Document Anonymization
**Goal**: Platform engineers can anonymize tool calls, JSON payloads, and file metadata through the gateway
**Depends on**: v1.0 Foundation (Presidio pipeline, provider adapters)
**Requirements**: MULTIMODAL-01
**Success Criteria** (what must be TRUE):
  1. System anonymizes tool call arguments and tool results in structured payloads
  2. System anonymizes JSON documents with recursive string leaf scan → structural validity preserved
  3. System handles multimodal metadata (file names, content types) anonymization
  4. Unsupported content types return HTTP 415
   5. Property-based test: anonymize→restore produces byte-for-byte identical document for all content types
**Plans**: 7 in 7 waves

**Wave 1** *(standalone — TokenizerService first)*
- 12-01: Tokenizer Service — Shared Tokenizer with format-specific walkers + refactor all three routes

**Wave 2** *(blocked on Wave 1 completion)*
- 12-02: Generic JSON Recursive String Leaf Scan

**Wave 3** *(blocked on Wave 1 completion)*
- 12-03: Schema-Aware Document Handling

**Wave 4** *(blocked on Wave 1 completion)*
- 12-04: Multimodal Metadata & Content Identifier Recognizers

**Wave 5** *(standalone — independent of Waves 2-4)*
- 12-05: Content Type Detection — Unsupported Content Type Enforcement

**Wave 6** *(blocked on Wave 1 + Wave 5 completion)*
- 12-06: Streaming Consistency for Multimodal Content

**Wave 7** *(blocked on all prior wave completion)*
- 12-07: Property-Based Tests for Multimodal Anonymization

### Phase 13: Operational Observability & Audit Infrastructure
**Goal**: SRE has comprehensive SLO tracking, security officer has immutable audit trail, and supply chain has SBOM
**Depends on**: Phase 10 (rate limit metrics)
**Requirements**: OBSERV-01, AUDITTRAIL-01, SBOM-01
**Success Criteria** (what must be TRUE):
  1. SRE can view per-SLO compliance status at `GET /v1/governance/status` with breach alerting via webhook
  2. Prometheus metrics available for rate_limit_hits, spend_limit_hits, tenant_active_sessions, config_reload
  3. Security officer can query immutable config change audit trail with pagination, filters, and JSON Lines export; 7-year retention
  4. CycloneDX SBOM generated per release build + container image SBOM via Syft + OCI attestation via cosign; Dependabot weekly scans
  5. `SECURITY.md` with disclosure contact and `docs/security/incident-response.md` published
**Plans**: TBD

### Phase 14: Data Classification & Handling Policies
**Goal**: Information security officer can classify every request by sensitivity level with per-level handling policies
**Depends on**: v1.0 Foundation (entity detection for auto-classification)
**Requirements**: FIN-05 (Req 41)
**Success Criteria** (what must be TRUE):
  1. Five classification levels (Public, Internal, Confidential, Restricted, Highly Restricted) enforced
  2. Auto-classification based on detected entity types with configurable mapping; undetected defaults to Internal
  3. Client-asserted `X-AnonReq-Classification` header supported; higher of client vs detected classification used
  4. Per-level handling policies (allow_and_anonymize / anonymize_and_flag / block) enforced with HTTP 451 on block
  5. Classification_Level present in every audit log entry
**Plans**: TBD

### Phase 15: AI Firewall & Data Loss Prevention
**Goal**: CISO has active inbound/outbound AI security enforcement and AI-specific DLP controls across all AI traffic types
**Depends on**: Phase 11 (prompt firewall as base), Phase 14 (classification for DLP contextual rules)
**Requirements**: APPL-05 (AI Firewall), APPL-02 (AI DLP)
**Success Criteria** (what must be TRUE):
  1. Inbound AI firewall detects prompt injection, jailbreak, data exfiltration, model manipulation, and agent abuse with MITRE ATT&CK mapping
  2. Outbound AI firewall detects PII reconstruction, harmful content, and data exfiltration encoding (Base64, hex, stego) with HTTP 451 suppression
  3. DLP policies classify AI traffic into 8 data categories (PII, PHI, PCI, MNPI, Trade Secrets, Source Code, Financial Records, Customer Data)
  4. Per-category DLP actions (allow/anonymize/redact/quarantine/block) enforced; contextual rules combine category + business_unit + Classification_Level
  5. All firewall and DLP events logged with Prometheus counters and structured audit entries
**Plans**: TBD

### Phase 16: Universal AI Traffic Gateway
**Goal**: Enterprise architect can route all AI interactions through a single enforcement point
**Depends on**: v1.0 Foundation (proxy architecture)
**Requirements**: APPL-01 (Req 48)
**Success Criteria** (what must be TRUE):
  1. All AI interaction types routed through single gateway (chat, voice bots, agent frameworks, RAG, MCP, email/CRM AI integrations)
  2. Deployment topologies: reverse proxy, transparent proxy (TLS interception using tenant-managed CA cert with re-origination), virtual appliance, physical appliance
  3. Block all non-intercepted AI API traffic via configurable `block-all-unintercepted-AI` policy
  4. P95 overhead ≤ 5ms for proxy-mode (no anonymization) — policy evaluation only
  5. Inline inspection of MCP protocol traffic, tool call/result payloads, and structured content
**Plans**: TBD

### Phase 17: Agent & Tool Call Governance
**Goal**: AI governance officer can inspect all agent actions before execution with per-tool permission policies
**Depends on**: Phase 12 (multimodal for tool call anonymization)
**Requirements**: APPL-04 (Req 51)
**Success Criteria** (what must be TRUE):
  1. MCP protocol traffic and OpenAI/Anthropic tool call/result payloads inspected
  2. Per-tool permission policy: `allow`, `allow_with_audit`, `require_human_approval`, `block`
  3. Tool call parameters anonymized for external API targets; tool results inspected for sensitive data
  4. Agent execution suspended for tools requiring human approval; routed through oversight queue
  5. Audit entries: `tool_allowed`, `tool_blocked`, `tool_approval_required` with structured details
**Plans**: TBD

### Phase 18: Network Discovery, CASB & Secure RAG
**Goal**: Security administrator gains visibility into AI service usage, governs AI SaaS applications, and protects RAG pipelines
**Depends on**: v1.0 Foundation
**Requirements**: APPL-06 (Network Discovery), APPL-07 (CASB), APPL-08 (Secure RAG)
**Success Criteria** (what must be TRUE):
  1. AI API traffic identified by hostname/IP across 8+ providers (OpenAI, Anthropic, Gemini, AWS Bedrock, Azure OpenAI, Mistral, Cohere, local LLMs)
  2. Shadow AI traffic detected via network flow/DNS analysis; `shadow_ai_detected` event emitted; AI asset inventory exportable as JSON/CSV
  3. AI SaaS usage monitored via corporate proxy/CASB telemetry; applications classified as sanctioned/tolerated/unsanctioned with per-app policies
  4. RAG pipeline documents inspected at retrieval injection point; full detection pipeline applied to retrieved content before LLM exposure
  5. Tokens restored in RAG-anonymized content within LLM response; `rag_content_anonymized` audit entry
**Plans**: TBD

### Phase 19: AI SOC/SIEM Integration
**Goal**: SOC analyst can monitor AI security events within enterprise SIEM across all major platforms
**Depends on**: Phase 11 (firewall events), Phase 15 (firewall + DLP events), Phase 14 (classification events)
**Requirements**: APPL-09 (Req 56)
**Success Criteria** (what must be TRUE):
  1. Structured events generated for: firewall violations, DLP actions, shadow AI, prompt security events
  2. SIEM sinks: Splunk (HEC), IBM QRadar (syslog CEF), Microsoft Sentinel (Data Collection Rules API), Elastic (Bulk API), Datadog (Logs API)
  3. Events include `mitre_technique_id`, `severity`, `event_type`, `tenant_id`, `session_id`, `timestamp`, `gateway_version`, `appliance_instance_id` (no raw prompt content)
  4. Sink health status available at `GET /v1/admin/soc/integration/status`
  5. Local event buffer (max 10k events) with exponential backoff retry; `soc_buffer_overflow` when full (discard oldest, never block processing)
**Plans**: TBD

## Progress

**Execution Order:** Phases 10, 11, 12, 14, and 16 are independent (all start from v1.0). Phase 13 depends on Phase 10. Phase 15 depends on Phase 11 + Phase 14. Phase 17 depends on Phase 12. Phase 18 is independent. Phase 19 depends on Phase 11, Phase 14, and Phase 15 (needs their events).

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 1/1 | Complete | 2026-06-14 |
| 2. Detection & Cache | v1.0 | 3/3 | Complete | 2026-06-15 |
| 3. Non-Streaming Proxy | v1.0 | 4/4 | Complete | 2026-06-15 |
| 4. Streaming Support | v1.0 | 3/3 | Complete | 2026-06-15 |
| 5. Multi-Provider Support | v1.0 | 7/7 | Complete | 2026-06-15 |
| 6. Custom Rules & Configuration | v1.0 | 3/3 | Complete | 2026-06-15 |
| 7. Audit & Deployment | v1.0 | 4/4 | Complete | 2026-06-15 |
| 8. Property-Based Test Suite | v1.0 | 3/3 | Complete | 2026-06-16 |
| 9. Enterprise Authentication & RBAC | v1.0 | 3/3 | Complete | 2026-06-16 |
| 10. Rate Limiting & Spend Controls | v1.1 | 0/TBD | Not started | - |
| 11. Prompt Security Firewall | v1.1 | 5/5 | Planned | - |
| 12. Multimodal Document Anonymization | v1.1 | 0/7 | Planned    |  |
| 13. Operational Observability & Audit | v1.1 | 0/TBD | Not started | - |
| 14. Data Classification & Handling | v1.1 | 0/TBD | Not started | - |
| 15. AI Firewall & DLP | v1.1 | 0/TBD | Not started | - |
| 16. Universal AI Traffic Gateway | v1.1 | 0/TBD | Not started | - |
| 17. Agent & Tool Call Governance | v1.1 | 0/TBD | Not started | - |
| 18. Discovery, CASB & Secure RAG | v1.1 | 0/TBD | Not started | - |
| 19. AI SOC/SIEM Integration | v1.1 | 0/TBD | Not started | - |
