# Requirements: AnonReq

**Defined:** 2026-06-19
**Core Value:** Raw PII never crosses the network boundary.

## v1 Requirements

### Core Pipeline

- [ ] **PIPE-01**: Gateway exposes `POST /v1/chat/completions` accepting OpenAI-compatible payload
- [ ] **PIPE-02**: Detection_Engine scans all text across all message roles (system, user, assistant, tool, function)
- [ ] **PIPE-03**: Tokenization_Engine replaces detected entities with `[TYPE_N]` tokens preserving context
- [ ] **PIPE-04**: Restoration_Engine replaces tokens with original values in LLM responses
- [ ] **PIPE-05**: Cache_Manager deletes Mapping within 100ms of response delivery
- [ ] **PIPE-06**: P95 processing overhead ≤ 100ms for prompts ≤ 1,000 words

### Fail-Secure

- [ ] **FAIL-01**: Any error returns HTTP 5xx, never forwards unsanitized data
- [ ] **FAIL-02**: Detection_Engine/Cache_Manager health probes gate all requests
- [ ] **FAIL-03**: `GET /health` endpoint returns status of all components
- [ ] **FAIL-04**: Pre-flight health check prevents startup until all components pass

### Detection Engine

- [ ] **DET-01**: Regex recognizer tier for structured PII (email, phone, CC, IBAN, IP, URL, DOB, national IDs, SWIFT, crypto)
- [ ] **DET-02**: NER recognizer tier for unstructured PII (name, org, address, city, job title)
- [ ] **DET-03**: Regex-NER overlap resolution (regex wins)
- [ ] **DET-04**: Configurable Confidence_Threshold (0.0–1.0, default 0.7) per entity type
- [ ] **DET-05**: Exclusion_List support with exact match and wildcard matching
- [x] **DET-06**: Custom recognizer patterns loaded from YAML at startup

### Tokenization

- [ ] **TOKN-01**: Token format `[TYPE_N]` with uppercase TYPE (1–20 chars) and positive integer N
- [ ] **TOKN-02**: Same entity value → same Token across all occurrences (deduplication)
- [ ] **TOKN-03**: Different entity values of same type → distinct Tokens with different indices
- [ ] **TOKN-04**: Reverse character-offset replacement to prevent position drift
- [ ] **TOKN-05**: Token index offsets derived from cryptographically random seed per session
- [ ] **TOKN-06**: No entities → no Mapping created, request forwarded unchanged
- [ ] **TOKN-07**: No entities → request forwarded unchanged, no Mapping created

### Cache Manager

- [ ] **CACH-01**: Valkey/Redis with persistence disabled (`save ""`, no AOF, no RDB)
- [ ] **CACH-02**: TTL range 60–3600s (default 300s), `allkeys-lru` eviction
- [ ] **CACH-03**: Monitoring commands (MONITOR, SLOWLOG) disabled
- [ ] **CACH-04**: Async DEL post-response, TTL as fallback
- [x] **CACH-05**: TTL extension at 80% elapsed time during long streams
- [ ] **CACH-06**: Health check verifies persistence disabled, reachability, read/write

### SSE Streaming

- [x] **SSE-01**: `stream: true` requests return `text/event-stream` without buffering
- [x] **SSE-02**: Pre-fetch Mapping via `HGETALL` at stream start
- [x] **SSE-03**: Tail_Buffer (512 char max) handles split tokens across chunk boundaries
- [x] **SSE-04**: Case-insensitive Token matching (e.g. `[name_1]`, `[Name_1]`)
- [x] **SSE-05**: Bracket-optional Token matching (`NAME_1` at word boundaries)
- [x] **SSE-06**: Tail_Buffer flush after 50 consecutive chunks or 500ms
- [x] **SSE-07**: Anti-buffering headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`
- [x] **SSE-08**: Flush Tail_Buffer on terminal event

### Multi-Provider

- [x] **PROV-01**: OpenAI-compatible providers (including Azure OpenAI) — native schema passthrough
- [x] **PROV-02**: Anthropic Claude — message format translation via Provider_Adapter
- [x] **PROV-03**: Google Gemini — contents[] format translation via Provider_Adapter
- [x] **PROV-04**: Ollama — OpenAI-compatible passthrough to configurable base URL
- [x] **PROV-05**: Model alias routing to upstream provider with name translation
- [x] **PROV-06**: API key injection from env/secrets at network boundary
- [x] **PROV-07**: `GET /v1/models` endpoint enumerating configured aliases
- [x] **PROV-08**: Provider errors forwarded with generic messages (no keys, URLs, or raw content)

### Multilingual Detection

- [ ] **LOCL-01**: 8 locale-specific regex recognizer bundles (en, de-DE, fr-FR, nl-NL, es, it-IT, ar, pt-BR)
- [ ] **LOCL-02**: `X-AnonReq-Locale` header activates locale-specific recognizer bundles
- [ ] **LOCL-03**: Unsupported/malformed locale → HTTP 400
- [ ] **LOCL-04**: No locale header → universal recognizers only + log entry
- [ ] **LOCL-05**: Multi-locale support (up to 10 comma-separated codes) with result merging
- [ ] **LOCL-06**: Extensible locale recognizer bundles (config file, no code change)
- [ ] **LOCL-07**: Checksum validation for locale-specific national IDs (Steuer-ID, BSN, NIR, CPF, CNPJ, Codice Fiscale)

### Compliance Presets

- [ ] **COMP-01**: Named presets for GDPR, LGPD, PDPA, POPIA, Privacy Act (AU), PIPEDA
- [ ] **COMP-02**: Startup validation rejects config that disables preset-mandated entity types
- [ ] **COMP-03**: `compliance_preset` field in audit log entries
- [ ] **COMP-04**: Merged preset when multiple active (union of types, highest threshold)
- [ ] **COMP-05**: `GET /v1/compliance/presets` endpoint

### Audit Logging

- [ ] **AUDT-01**: Structured JSON to stdout with timestamp, session_id, provider, model, entity_counts, latency_ms, compliance_preset, locale
- [x] **AUDT-02**: No raw prompt text, raw response text, tokens, entity values, credentials, or internal URLs in logs
- [ ] **AUDT-03**: Structured-log field allowlist — non-allowlisted fields stripped
- [ ] **AUDT-04**: Fail-secure event log entries (timestamp, session_id, failure_type, http_status)
- [ ] **AUDT-05**: Log entry written before HTTP response flushed

### Token Verification & Metrics

- [x] **METR-01**: Post-restoration `\[[A-Z]+_\d+\]` scan on non-streaming responses
- [x] **METR-02**: Post-stream verification scan on full assembled text
- [ ] **METR-03**: Prometheus `/metrics` with counters for requests, detection latency, entities, unrestored tokens, fail-secure events, audit failures

### Docker Compose Deployment

- [ ] **DOCK-01**: `docker-compose.yml` with anonreq + presidio + valkey services
- [ ] **DOCK-02**: Multi-stage Dockerfile (Python 3.12-slim), final image ≤ 2GB
- [ ] **DOCK-03**: Valkey with `save ""`, bound to internal network only
- [ ] **DOCK-04**: `depends_on` with `service_healthy` for both presidio and valkey
- [ ] **DOCK-05**: All config via env vars with documented defaults
- [ ] **DOCK-06**: `.env.example` documenting every env var
- [ ] **DOCK-07**: Missing required env var → startup failure with error

### Property-Based Tests

- [ ] **TEST-01**: Round-trip correctness — anonymize → restore → byte-for-byte match
- [ ] **TEST-02**: Token uniqueness — N distinct values → N distinct Tokens
- [ ] **TEST-03**: Deduplication — same value K times → same Token
- [x] **TEST-04**: Fail-secure — Detection/Cache/Timeout → HTTP 500, 0 forwarded
- [ ] **TEST-05**: Locale checksum — invalid checksums not flagged
- [ ] **TEST-06**: No-PII-in-logs — synthetic PII absent from log output
- [x] **TEST-07**: Streaming round-trip — all split indices produce byte-for-byte match
- [x] **TEST-08**: Cross-request randomization — 1000+ session pairs, ≥ 1 − 2⁻³² probability

### Developer Experience & Documentation

- [ ] **DOCS-01**: Integration quickstarts in 5 languages (EN, DE, FR, ES, PT-BR)
- [ ] **DOCS-02**: SDK examples for Python, Node.js, curl
- [ ] **DOCS-03**: `CHANGELOG.md` (Keep a Changelog format)
- [ ] **DOCS-04**: Apache 2.0 LICENSE, NOTICE file, SECURITY.md
- [ ] **DOCS-05**: README with "Why AnonReq" and "License and Commercial Use" sections

## Stage 2 Requirements (Enterprise)

### Rate Limiting & Spend Controls (Req 22)

- [ ] **RATE-01**: Per-tenant RPM/TPM/concurrent rate limits — configurable independently
- [x] **RATE-02**: RPM/TPM exceeded → HTTP 429 with `Retry-After` header
- [ ] **RATE-03**: Concurrent limit exceeded → HTTP 429 with `reason: concurrent_limit_exceeded`
- [ ] **RATE-04**: Per-tenant daily/monthly spend budgets (USD or configured currency)
- [x] **RATE-05**: Budget exceeded → HTTP 402 with `budget_type`, `current_spend`, `budget_limit`, `currency`
- [x] **RATE-06**: Daily reset at 00:00 UTC, monthly reset on 1st; `budget_reset` audit event
- [x] **RATE-07**: `GET /v1/admin/tenants/{tenant_id}/usage` endpoint (operator/admin role)
- [x] **RATE-08**: Fail closed (HTTP 503) when cache unavailable

### Multimodal Document Anonymization (Req 23)

- [ ] **MULTI-01**: Tool call arguments (`tool_calls` JSON) anonymized
- [ ] **MULTI-02**: Tool call results (`tool` role content) anonymized
- [x] **MULTI-03**: JSON documents — recursive string leaf scan, structural validity preserved
- [x] **MULTI-04**: Multimodal metadata (file names, `image_url` descriptions) anonymized
- [x] **MULTI-05**: Unsupported content types → HTTP 415
- [ ] **MULTI-06**: Property-based test: anonymize→restore byte-for-byte identical document

### Operational Observability (Req 24)

- [x] **OBS-01**: SLO evaluation: success ≥ 99.9%, P95 ≤ 100ms, fail-secure ≤ 0.1%, audit ≥ 99.99%
- [x] **OBS-02**: `GET /v1/governance/status` with per-SLO compliance, breach alert webhook
- [x] **OBS-03**: SLO breach log entry `event_type: slo_breach_detected`
- [x] **OBS-04**: Metrics: `anonreq_rate_limit_hits_total`, `anonreq_spend_limit_hits_total`,
      `anonreq_tenant_active_sessions`, `anonreq_config_reload_total`

- [ ] **OBS-05**: `docs/operations/slo-runbook.md`

### Configuration Change Audit Trail (Req 25)

- [ ] **AUDT-CFG-01**: Audit entry for every config change (presets, recognizers, exclusion list,
      providers, rate limits, budgets, tenants)

- [ ] **AUDT-CFG-02**: Entry fields: timestamp, operator_id, tenant_id, change_type, prev_value_hash, new_value_hash
- [ ] **AUDT-CFG-03**: Append-only trail — no modify or delete API (except Legal Hold)
- [ ] **AUDT-CFG-04**: `GET /v1/admin/audit/config-history` paginated + filterable
- [ ] **AUDT-CFG-05**: JSON Lines export via `GET /v1/admin/audit/config-history/export`
- [ ] **AUDT-CFG-06**: 7-year retention (or longer per regulatory framework)

### Supply Chain Security & SBOM (Req 26)

- [ ] **SBOM-01**: CycloneDX JSON SBOM per release (all direct + transitive Python deps)
- [ ] **SBOM-02**: Container image SBOM via Syft (OS packages, Python, model artifacts)
- [ ] **SBOM-03**: SBOM published as release artifact + OCI attestation via cosign
- [ ] **SBOM-04**: Dependabot weekly scans; CVSS ≥ 9.0 auto-issue within 24h
- [ ] **SBOM-05**: `docs/security/incident-response.md`
- [ ] **SBOM-06**: `SECURITY.md` with disclosure contact, response SLA (≤ 5 business days)

### AI Governance & Accountability (Req 27)

- [ ] **GOV-01**: Structured governance record per tenant (governance/risk/compliance/security owners)
- [ ] **GOV-02**: Governance approval entry for production config changes affecting compliance
- [ ] **GOV-03**: `GET /v1/governance/status` with owner assignments, review dates, pending approvals
- [ ] **GOV-04**: Configurable governance review cycle (default 90 days); overdue review surfaced + logged
- [ ] **GOV-05**: Append-only governance log (separate from audit log), 7-year retention
- [ ] **GOV-06**: Governance export `GET /v1/admin/governance/export` (JSON Lines)

### AI Risk & Impact Assessment (Req 28)

- [ ] **RISK-01**: Versioned risk assessment per tenant (privacy, security, bias, explainability,
      misuse, regulatory dimensions)

- [ ] **RISK-02**: Config change affecting entity types → `risk_reassessment_required` event +
      pending indicator in governance status

- [ ] **RISK-03**: Approved risk assessment required before activating new preset/provider;
      unapproved → HTTP 409

- [ ] **RISK-04**: Treatment plans for risk_level ≥ Medium (owner, due_date, status)
- [ ] **RISK-05**: Risk assessment export `GET /v1/admin/risk-assessments/export`

### Human Oversight & Intervention (Req 29)

- [ ] **HUM-01**: Configurable human-approval gate for high-risk request categories
- [ ] **HUM-02**: `GET /v1/oversight/pending`, `POST /v1/oversight/{id}/approve`,
      `POST /v1/oversight/{id}/reject`

- [ ] **HUM-03**: Approved → normal processing. Rejected → HTTP 403 + `human_rejection` audit entry
- [ ] **HUM-04**: Kill-switch `POST /v1/oversight/kill-switch` (admin role); halts all outbound;
      `DELETE /v1/oversight/kill-switch` to release

- [ ] **HUM-05**: All oversight actions logged with actor_id, tenant_id, timestamp
- [ ] **HUM-06**: `GET /v1/oversight/sessions/{session_id}/summary` (entity counts, no raw content)

### AI System Transparency (Req 30)

- [x] **TRAN-01**: `X-AnonReq-Processed: true/false` response header on all responses
- [x] **TRAN-02**: `X-AnonReq-Entity-Count` response header (integer count)
- [x] **TRAN-03**: `X-AnonReq-Block-Reason` response header for blocked requests
- [ ] **TRAN-04**: Transparency record per session via `GET /v1/transparency/{session_id}`
- [ ] **TRAN-05**: Periodic transparency report `GET /v1/admin/transparency/report?period=monthly`

### AI Lifecycle Management (Req 31)

- [ ] **LIF-01**: Lifecycle record per provider integration and compliance preset
      (design→development→testing→staging→production→retired)

- [ ] **LIF-02**: Production activation requires lifecycle transition record with approver
- [ ] **LIF-03**: `retired` → immediately cease routing, disable in all tenant configs,
      `lifecycle_retired` audit entry

- [ ] **LIF-04**: `GET /v1/admin/lifecycle` listing all integrations with stage, transition date, approver

### Bias, Fairness & Non-Discrimination (Req 32)

- [ ] **BIAS-01**: Fairness testing datasets per locale (200+ examples per demographic group)
- [ ] **BIAS-02**: CI/CD bias assessment on each release; build fails if recall disparity > 0.05
- [ ] **BIAS-03**: `locale` field in audit log for demographic analysis
- [ ] **BIAS-04**: `GET /v1/admin/fairness/report` with most recent bias results
- [ ] **BIAS-05**: Bias records retained 7 years, included in ISO 42001 governance export

### Third-Party AI Supplier Governance (Req 33)

- [ ] **SUPP-01**: Provider inventory (name, legal entity, jurisdiction, data residency,
      risk classification, contract status, last review date)

- [ ] **SUPP-02**: Critical provider activation requires explicit administrator approval
- [ ] **SUPP-03**: Expired/suspended contract → immediately cease routing, `provider_suspended` audit entry
- [ ] **SUPP-04**: Configurable provider review cycle (default 365 days); overdue surfaced in status
- [ ] **SUPP-05**: `GET /v1/admin/providers` returns full inventory

### Post-Deployment Monitoring & Incident Reporting (Req 34)

- [ ] **MON-01**: Continuous signals: detection quality drift, fail-secure frequency, audit failure rate, SLO compliance
- [ ] **MON-02**: Incident classification (S1 data exposure / S2 degradation / S3 anomaly)
- [ ] **MON-03**: `event_type: incident_opened` with severity, incident_id, description
- [ ] **MON-04**: `GET /v1/admin/incidents` + `POST /v1/admin/incidents/{id}/close`
- [ ] **MON-05**: Incident export as JSON Lines (root cause, corrective actions)

### Technical Documentation & Conformity (Req 35)

- [ ] **DOC-TECH-01**: Versioned docs in `docs/`: architecture, controls, risk methodology,
      governance, security, deployment

- [ ] **DOC-TECH-02**: `GET /v1/admin/compliance/conformity-package` returns ZIP with SBOM,
      governance export, risk assessments, config audit history, fairness report, manifest

- [ ] **DOC-TECH-03**: Requirements traceability matrix linking reqs → code modules → tests → regulations
- [ ] **DOC-TECH-04**: All technical docs in English with changelog per version

### Prompt Security & AI Firewall (Req 36)

- [x] **FIREWALL-01**: Inbound prompt inspection: direct injection, indirect injection, role-confusion
- [ ] **FIREWALL-02**: Injection detected ≥ threshold (default 0.85) → HTTP 400 `prompt_injection_detected`
- [x] **FIREWALL-03**: Jailbreak YAML rule set with block/flag_and_forward/monitor actions
- [ ] **FIREWALL-04**: Outbound response inspection for policy-violating content → HTTP 451
- [ ] **FIREWALL-05**: All events logged: `event_type`, session_id, tenant_id, confidence_score, rule_id
- [ ] **FIREWALL-06**: Prometheus counter `anonreq_prompt_security_events_total` (event_type, tenant_id)
- [x] **FIREWALL-07**: `GET /v1/admin/prompt-security/rules` listing active rules
- [x] **FIREWALL-08**: Hot-reload rules within 60 seconds without restart

### Financial Services Compliance Framework (Req 37)

- [ ] **FIN-01**: Compliance mapping document `docs/compliance/financial-services-mapping.md`
      (DORA, NIS2, GDPR, ISO 27001/42001, EBA, FCA, SEC, FINRA)

- [ ] **FIN-02**: Evidence records linking controls to regulatory mappings
- [ ] **FIN-03**: `GET /v1/admin/compliance/report?framework={id}` — structured compliance report
- [ ] **FIN-04**: Compliance evidence package with financial-services cover sheet
- [ ] **FIN-05**: Version history of regulatory mappings `?as_of={iso_date}`

### MNPI Protection (Req 38)

- [ ] **MNPI-01**: MNPI recognizer bundle (ticker symbols, deal codenames, restricted names list)
- [ ] **MNPI-02**: Tenant-configurable restricted-names list, hot-reloadable
- [ ] **MNPI-03**: MNPI detected → `[TYPE_N]` tokenized, `Classification_Level: Restricted`,
      `mnpi_detected` audit entry (no raw values)

- [ ] **MNPI-04**: 4 handling policies: anonymize_and_forward, flag_and_forward, block, quarantine
- [ ] **MNPI-05**: 7-year retention per SEC 17a-4 / FINRA 4511
- [ ] **MNPI-06**: `GET /v1/admin/mnpi/events` paginated (no raw entity values)

### Model Risk Management (Req 39)

- [ ] **MRM-01**: Model inventory (model_id, provider, name, business_purpose, risk_classification,
      approval_status, approval_date, approver, next_review_date, model_owner)

- [ ] **MRM-02**: Model approval gating — unapproved models → HTTP 403
- [ ] **MRM-03**: `GET /v1/admin/models` — full inventory with approval status
- [ ] **MRM-04**: Model review cycle (default 365 days); overdue surfaced + logged
- [ ] **MRM-05**: Model validation workflow: `POST /v1/admin/models/{id}/validations`,
      `GET /v1/admin/models/{id}/validations`

- [ ] **MRM-06**: 7-year retention for all inventory + validation records
- [ ] **MRM-07**: `docs/compliance/sr-11-7-alignment.md`

### Third-Party AI Provider Risk (Req 40)

- [ ] **PROV-RISK-01**: Provider records include DPA reference, sub-processor list, jurisdiction,
      ICT concentration risk flag

- [ ] **PROV-RISK-02**: Concentration risk surfaced in governance status; annual justification
      record required

- [ ] **PROV-RISK-03**: Provider suspension `POST /v1/admin/providers/{id}/suspend`
- [ ] **PROV-RISK-04**: Provider approval gating — expired/suspended → HTTP 503
- [ ] **PROV-RISK-05**: Provider inventory export for DORA ICT third-party register

### Data Classification & Handling (Req 41)

- [x] **CLASS-01**: 5 classification levels (Public → Highly Restricted)
- [x] **CLASS-02**: Auto-classification by highest-sensitivity entity type; defaults to Internal
- [ ] **CLASS-03**: Client-asserted `X-AnonReq-Classification` header; higher wins, overrides logged
- [ ] **CLASS-04**: Per-level handling: allow_and_anonymize (≤ Confidential), anonymize_and_flag
      (Restricted), block (Highly Restricted) → HTTP 451

- [x] **CLASS-05**: Classification_Level in every audit log entry

### Financial Crime Controls (Req 42)

- [ ] **FINC-01**: Financial crime recognizer bundle (IBAN, payment refs, customer IDs, AML case refs)
- [ ] **FINC-02**: High-risk context words within 50 chars → confidence +0.15 (capped at 1.0)
- [ ] **FINC-03**: `event_type: financial_crime_entity_detected` audit entry
- [ ] **FINC-04**: Export via `GET /v1/admin/financial-crime/events/export`
- [ ] **FINC-05**: Configurable webhook for real-time AML platform integration

### DORA Operational Resilience (Req 43)

- [ ] **DORA-01**: Critical service flag `dora.critical_service: true` → S1 auto-escalation
- [ ] **DORA-02**: Resilience testing procedure in `docs/operations/resilience-testing.md`
      (cache failover, detection unavailable, network partition)

- [ ] **DORA-03**: `GET /v1/admin/resilience/test-records` with test_date, scenario, outcome
- [ ] **DORA-04**: ICT third-party register export `GET /v1/admin/providers/ict-register`
- [ ] **DORA-05**: Single-command DORA audit evidence generation

### Data Lineage & Traceability (Req 44)

- [ ] **LINE-01**: Immutable Lineage_Record per request (lineage_id, session_id, tenant_id,
      timestamps, source_app, provider, model, entities, compliance_preset, classification, policies)

- [ ] **LINE-02**: No API to modify or delete lineage records
- [ ] **LINE-03**: `GET /v1/admin/lineage/{session_id}` — lineage record retrieval
- [ ] **LINE-04**: `GET /v1/admin/lineage` — paginated, filterable by tenant_id, time range
- [ ] **LINE-05**: Lineage export for eDiscovery

### Record Retention & Legal Hold (Req 45)

- [ ] **RET-01**: Configurable retention schedules by record type (audit, governance, lineage, incidents)
- [ ] **RET-02**: Legal Hold support: `POST /v1/admin/legal-hold` suspends deletion for specified
      records/tenants

- [ ] **RET-03**: `GET /v1/admin/legal-hold` — list active holds
- [ ] **RET-04**: Records under Legal Hold excluded from purge operations
- [ ] **RET-05**: Legal Hold release requires audit trail entry with authorizing user

### Data Subject Rights (Req 46)

- [ ] **DSR-01**: DSAR intake `POST /v1/admin/dsr` (data subject ID, request type, tenant)
- [ ] **DSR-02**: Request types: access, erasure, rectification, portability, restriction
- [ ] **DSR-03**: Status tracking: `GET /v1/admin/dsr/{id}` — current status, progress, completion date
- [ ] **DSR-04**: Erasure: purge all Mapping data for data subject from cache + lineage records
- [ ] **DSR-05**: Portability: export all data subject records as JSON Lines
- [ ] **DSR-06**: Audit trail for every DSR action

### Breach Notification Automation (Req 47)

- [ ] **BREACH-01**: Configurable notification templates (regulator, affected tenants, internal)
- [ ] **BREACH-02**: Regulator notification queue with status tracking
- [ ] **BREACH-03**: Affected-tenant notification workflow
- [ ] **BREACH-04**: Audit trail for all breach notifications

## Stage 3 Requirements (Appliance)

### Universal AI Traffic Gateway (Req 48)

- [x] **APPL-01**: All AI interaction types routed through single gateway (chat, voice bots,
      agents, RAG, MCP, email/CRM AI integrations)

- [ ] **APPL-02**: Reverse proxy topology
- [ ] **APPL-03**: Transparent proxy with TLS interception (tenant-managed CA cert, re-origination)
- [ ] **APPL-04**: Virtual appliance deployment
- [ ] **APPL-05**: Physical appliance deployment
- [ ] **APPL-06**: `block-all-unintercepted-AI` policy
- [ ] **APPL-07**: P95 ≤ 5ms proxy-only mode (no anonymization)

### AI-Aware DLP (Req 49)

- [ ] **APPL-DLP-01**: 8 data categories: PII, PHI, PCI, MNPI, Trade Secrets, Source Code,
      Financial Records, Customer Data

- [ ] **APPL-DLP-02**: Per-category actions: allow / anonymize / redact / quarantine / block
- [ ] **APPL-DLP-03**: Contextual rules combining category + business_unit + Classification_Level
- [ ] **APPL-DLP-04**: Data exfiltration encoding detection (Base64, hex, steganography)
- [ ] **APPL-DLP-05**: Prometheus counters and audit entries for all DLP actions

### Prompt Security Advanced (Req 50)

- [ ] **APPL-PS-01**: Inbound AI firewall with MITRE ATT&CK mapping (T1574.002, T1190, etc.)
- [ ] **APPL-PS-02**: Outbound AI firewall: PII reconstruction detection, harmful content,
      data exfiltration attempts

- [ ] **APPL-PS-03**: Dynamic policy adaptation based on user role, data classification, and
      provider risk score

### Agent & Tool Call Governance (Req 51)

- [ ] **APPL-AGENT-01**: MCP protocol traffic inspection
- [ ] **APPL-AGENT-02**: Per-tool permission policies: allow, allow_with_audit,
      require_human_approval, block

- [x] **APPL-AGENT-03**: Tool call parameters anonymized for external API targets
- [x] **APPL-AGENT-04**: Tool results inspected for sensitive data
- [ ] **APPL-AGENT-05**: Agent execution suspended for tools requiring human approval
- [ ] **APPL-AGENT-06**: Audit entries: `tool_allowed`, `tool_blocked`, `tool_approval_required`

### Network Discovery (Req 52)

- [x] **APPL-DISC-01**: AI API traffic identification by hostname/IP across 8+ providers
- [x] **APPL-DISC-02**: Shadow AI detection via network flow/DNS analysis
- [ ] **APPL-DISC-03**: `shadow_ai_detected` event emission
- [ ] **APPL-DISC-04**: AI asset inventory export (JSON/CSV)

### CASB Integration (Req 53)

- [ ] **APPL-CASB-01**: AI SaaS usage monitoring via corporate proxy/CASB telemetry
- [ ] **APPL-CASB-02**: Application classification: sanctioned / tolerated / unsanctioned
- [ ] **APPL-CASB-03**: Per-application policies

### Secure RAG (Req 54)

- [ ] **APPL-RAG-01**: RAG pipeline document inspection at retrieval injection point
- [ ] **APPL-RAG-02**: Full detection pipeline applied to retrieved content before LLM exposure
- [ ] **APPL-RAG-03**: Token restoration in RAG-anonymized content within LLM response
- [ ] **APPL-RAG-04**: `rag_content_anonymized` audit entry

### Content Disarm & Behavioral Analytics (Req 55)

- [ ] **APPL-CDP-01**: Content disarm and reconstruction for AI inputs/outputs
- [ ] **APPL-CDP-02**: Behavioral analytics: user baseline profiling and anomaly detection on
      AI usage patterns

- [ ] **APPL-CDP-03**: Network tap integration for passive traffic monitoring
- [ ] **APPL-CDP-04**: WAF integration for coordinated AI + web attack detection

### SOC/SIEM Integration (Req 56)

- [ ] **APPL-SOC-01**: Structured events for: firewall violations, DLP actions, shadow AI,
      prompt security, agent governance

- [ ] **APPL-SOC-02**: Splunk HEC sink
- [ ] **APPL-SOC-03**: IBM QRadar syslog CEF sink
- [ ] **APPL-SOC-04**: Microsoft Sentinel DCR API sink
- [ ] **APPL-SOC-05**: Elastic Bulk API sink
- [ ] **APPL-SOC-06**: Datadog Logs API sink
- [ ] **APPL-SOC-07**: Events include mitre_technique_id, severity, event_type, tenant_id,
      session_id, timestamp (no raw prompt content)

- [ ] **APPL-SOC-08**: Sink health status `GET /v1/admin/soc/integration/status`
- [ ] **APPL-SOC-09**: Local event buffer (max 10k) with exponential backoff retry;
      `soc_buffer_overflow` when full (discard oldest, never block processing)

- [ ] **APPL-SOC-10**: Compliance attestation event generation for regulatory audit

## Deferred / Future

### Enterprise Authentication & Authorization (Req 17)

- **AUTH-01**: API keys (≥256-bit entropy), OAuth 2.0 JWT, mTLS authentication
- **AUTH-02**: RBAC with built-in roles (administrator, security_officer, operator, read_only_auditor)
- **AUTH-03**: OIDC and SAML 2.0 delegation to external IdPs
- **AUTH-04**: API key/JWT revocation list with configurable cache TTL

### Secrets Management & Network Security (Req 18)

- **SECR-01**: TLS 1.3 for all external communications
- **SECR-02**: mTLS for internal component communications
- **SECR-03**: Integration with HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, Google Secret Manager
- **SECR-04**: Automatic secret rotation without process restart

### Multi-Tenant Isolation (Req 19)

- **MTEN-01**: Tenant_ID via X-AnonReq-Tenant-ID header, scoping all operations
- **MTEN-02**: Key format `anonreq:{tenant_id}:{session_id}` for structural isolation
- **MTEN-03**: Per-tenant fully independent configuration
- **MTEN-04**: Tenant provisioning API (CRUD)

### High Availability & Scalability (Req 20)

- **HASC-01**: Stateless Gateway tier for horizontal scaling
- **HASC-02**: Valkey Sentinel/Cluster HA modes
- **HASC-03**: Kubernetes Helm chart with HPA, readiness/liveness probes
- **HASC-04**: Recovery objectives: 99.9% SLA, RTO ≤ 15min, RPO = 0

### Data Sovereignty & Compliance Assurance (Req 21)

- **SOVR-01**: Geographic routing policies with region-restricted provider routing
- **SOVR-02**: Detection quality benchmarks (precision ≥ 0.95, recall ≥ 0.90) per locale
- **SOVR-03**: SBOM in CycloneDX JSON format with every release
- **SOVR-04**: Published SLOs (request success, P95 overhead, fail-secure rate, audit write success)

## Out of Scope

| Feature | Reason |
|---------|--------|
| LLM-based PII detection | The research found this consistently recommended against — slower, more expensive, less reliable than Presidio NER + regex combination |
| Persistent cache/disk storage | Contradicts the core ephemeral guarantee; defeats seizure-resistance requirement |
| UI dashboard | v1 is an API-only gateway; admin UI is enterprise/Appliance tier scope |
| Full SIEM/SOC integration | Appliance tier (Req 48–56); v1 uses stdout structured logs for consumption by existing log aggregators |
| Model training or fine-tuning | Out of scope — AnonReq uses pre-built Presidio models and hand-crafted regex patterns |

## Traceability

### Stage 1 (MVP)

| Requirement | Phase | Status |
|-------------|-------|--------|
| PIPE-01 | Phase 2 | Pending |
| PIPE-02 | Phase 2 | Pending |
| PIPE-03 | Phase 2 | Pending |
| PIPE-04 | Phase 2 | Pending |
| PIPE-05 | Phase 2 | Pending |
| PIPE-06 | Phase 5 | Pending |
| FAIL-01 | Phase 1 | Pending |
| FAIL-02 | Phase 1 | Pending |
| FAIL-03 | Phase 1 | Pending |
| FAIL-04 | Phase 1 | Pending |
| DET-01 | Phase 2 | Pending |
| DET-02 | Phase 2 | Pending |
| DET-03 | Phase 2 | Pending |
| DET-04 | Phase 2 | Pending |
| DET-05 | Phase 2 | Pending |
| DET-06 | Phase 5 | Complete |
| TOKN-01 | Phase 2 | Pending |
| TOKN-02 | Phase 2 | Pending |
| TOKN-03 | Phase 2 | Pending |
| TOKN-04 | Phase 2 | Pending |
| TOKN-05 | Phase 2 | Pending |
| TOKN-06 | Phase 2 | Pending |
| TOKN-07 | Phase 2 | Pending |
| CACH-01 | Phase 2 | Pending |
| CACH-02 | Phase 2 | Pending |
| CACH-03 | Phase 2 | Pending |
| CACH-04 | Phase 2 | Pending |
| CACH-05 | Phase 3 | Complete |
| SSE-01 | Phase 3 | Complete |
| SSE-02 | Phase 3 | Complete |
| SSE-03 | Phase 3 | Complete |
| SSE-04 | Phase 3 | Complete |
| SSE-05 | Phase 3 | Complete |
| SSE-06 | Phase 3 | Complete |
| SSE-07 | Phase 3 | Complete |
| SSE-08 | Phase 3 | Complete |
| PROV-01 | Phase 2 | Complete |
| PROV-02 | Phase 3 | Complete |
| PROV-03 | Phase 3 | Complete |
| PROV-04 | Phase 3 | Complete |
| PROV-05 | Phase 3 | Complete |
| PROV-06 | Phase 3 | Complete |
| PROV-07 | Phase 3 | Complete |
| PROV-08 | Phase 3 | Complete |
| LOCL-01 | Phase 4 | Pending |
| LOCL-02 | Phase 4 | Pending |
| LOCL-03 | Phase 4 | Pending |
| LOCL-04 | Phase 4 | Pending |
| LOCL-05 | Phase 4 | Pending |
| LOCL-06 | Phase 4 | Pending |
| LOCL-07 | Phase 4 | Pending |
| COMP-01 | Phase 4 | Pending |
| COMP-02 | Phase 4 | Pending |
| COMP-03 | Phase 4 | Pending |
| COMP-04 | Phase 4 | Pending |
| COMP-05 | Phase 4 | Pending |
| AUTH-MINIMAL-01 | Phase 1 | Pending |
| CLASS-AC-01 | Phase 2 | Pending |
| CLASS-AC-02 | Phase 2 | Pending |
| CLASS-AC-03 | Phase 2 | Pending |
| CLASS-AC-04 | Phase 2 | Pending |
| CLASS-AC-05 | Phase 2 | Pending |
| SSE-DISCONNECT-01 | Phase 3 | Complete |
| PERF-LOAD-01 | Phase 5 | Pending |
| AUDT-01 | Phase 1 | Pending |
| AUDT-02 | Phase 1 | Complete |
| AUDT-03 | Phase 1 | Pending |
| AUDT-04 | Phase 2 | Pending |
| AUDT-05 | Phase 2 | Pending |
| METR-01 | Phase 5 | Complete |
| METR-02 | Phase 5 | Complete |
| METR-03 | Phase 5 | Pending |
| DOCK-01 | Phase 1 | Pending |
| DOCK-02 | Phase 1 | Pending |
| DOCK-03 | Phase 1 | Pending |
| DOCK-04 | Phase 1 | Pending |
| DOCK-05 | Phase 1 | Pending |
| DOCK-06 | Phase 1 | Pending |
| DOCK-07 | Phase 1 | Pending |
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 6 | Pending |
| TEST-03 | Phase 6 | Pending |
| TEST-04 | Phase 6 | Complete |
| TEST-05 | Phase 6 | Pending |
| TEST-06 | Phase 6 | Pending |
| TEST-07 | Phase 3 | Complete |
| TEST-08 | Phase 6 | Complete |
| DOCS-01 | Phase 7 | Pending |
| DOCS-02 | Phase 7 | Pending |
| DOCS-03 | Phase 7 | Pending |
| DOCS-04 | Phase 7 | Pending |
| DOCS-05 | Phase 7 | Pending |

### Stage 2 (Enterprise)

| Requirement | Phase | Status |
|-------------|-------|--------|
| RATE-01 to RATE-08 | Phase 8 | Pending |
| MULTI-01 to MULTI-06 | Phase 9 | Pending |
| FIREWALL-01 to FIREWALL-08 | Phase 10 | Pending |
| OBS-01 to OBS-05 | Phase 11 | Pending |
| AUDT-CFG-01 to AUDT-CFG-06 | Phase 11 | Pending |
| SBOM-01 to SBOM-06 | Phase 11 | Pending |
| CLASS-01 to CLASS-05 | Phase 12 | Pending |
| APPL-DLP-01 to APPL-DLP-05 | Phase 13 | Pending |
| GOV-01 to GOV-06 | Phase 14 | Pending |
| RISK-01 to RISK-05 | Phase 14 | Pending |
| HUM-01 to HUM-06 | Phase 14 | Pending |
| TRAN-01 to TRAN-05 | Phase 14 | Pending |
| LIF-01 to LIF-04 | Phase 14 | Pending |
| DOC-TECH-01 to DOC-TECH-04 | Phase 14 | Pending |
| FIN-01 to FIN-05 | Phase 15 | Pending |
| MNPI-01 to MNPI-06 | Phase 15 | Pending |
| MRM-01 to MRM-07 | Phase 15 | Pending |
| PROV-RISK-01 to PROV-RISK-05 | Phase 15 | Pending |
| FINC-01 to FINC-05 | Phase 15 | Pending |
| DORA-01 to DORA-05 | Phase 15 | Pending |
| BIAS-01 to BIAS-05 | Phase 16 | Pending |
| SUPP-01 to SUPP-05 | Phase 16 | Pending |
| MON-01 to MON-05 | Phase 16 | Pending |
| LINE-01 to LINE-05 | Phase 16 | Pending |
| RET-01 to RET-05 | Phase 16 | Pending |
| DSR-01 to DSR-06 | Phase 16 | Pending |
| BREACH-01 to BREACH-04 | Phase 16 | Pending |

### Stage 3 (Appliance)

| Requirement | Phase | Status |
|-------------|-------|--------|
| APPL-01 to APPL-07 | Phase 17 | Pending |
| APPL-AGENT-01 to APPL-AGENT-06 | Phase 18 | Pending |
| APPL-DISC-01 to APPL-DISC-04 | Phase 19 | Pending |
| APPL-CASB-01 to APPL-CASB-03 | Phase 19 | Pending |
| APPL-RAG-01 to APPL-RAG-04 | Phase 19 | Pending |
| APPL-SOC-01 to APPL-SOC-10 | Phase 20 | Pending |
| Endpoint/Sovereign features | Phase 21 | Pending |

**Coverage:**

- Stage 1 (MVP) requirements: 90 (across 14 categories + review findings)
- Stage 2 (Enterprise) requirements: 80+ (across 16 requirement groups)
- Stage 3 (Appliance) requirements: 35+ (across 8 requirement groups)
- Mapped to phases: All

---
*Requirements defined: 2026-06-19*
*Last updated: 2026-06-19 — consolidated across all roadmaps and enterprise docs*
