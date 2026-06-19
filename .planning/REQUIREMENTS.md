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
- [ ] **DET-06**: Custom recognizer patterns loaded from YAML at startup

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
- [ ] **CACH-05**: TTL extension at 80% elapsed time during long streams
- [ ] **CACH-06**: Health check verifies persistence disabled, reachability, read/write

### SSE Streaming

- [ ] **SSE-01**: `stream: true` requests return `text/event-stream` without buffering
- [ ] **SSE-02**: Pre-fetch Mapping via `HGETALL` at stream start
- [ ] **SSE-03**: Tail_Buffer (512 char max) handles split tokens across chunk boundaries
- [ ] **SSE-04**: Case-insensitive Token matching (e.g. `[name_1]`, `[Name_1]`)
- [ ] **SSE-05**: Bracket-optional Token matching (`NAME_1` at word boundaries)
- [ ] **SSE-06**: Tail_Buffer flush after 50 consecutive chunks or 500ms
- [ ] **SSE-07**: Anti-buffering headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`
- [ ] **SSE-08**: Flush Tail_Buffer on terminal event

### Multi-Provider

- [ ] **PROV-01**: OpenAI-compatible providers (including Azure OpenAI) — native schema passthrough
- [ ] **PROV-02**: Anthropic Claude — message format translation via Provider_Adapter
- [ ] **PROV-03**: Google Gemini — contents[] format translation via Provider_Adapter
- [ ] **PROV-04**: Ollama — OpenAI-compatible passthrough to configurable base URL
- [ ] **PROV-05**: Model alias routing to upstream provider with name translation
- [ ] **PROV-06**: API key injection from env/secrets at network boundary
- [ ] **PROV-07**: `GET /v1/models` endpoint enumerating configured aliases
- [ ] **PROV-08**: Provider errors forwarded with generic messages (no keys, URLs, or raw content)

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
- [ ] **AUDT-02**: No raw prompt text, raw response text, tokens, entity values, credentials, or internal URLs in logs
- [ ] **AUDT-03**: Structured-log field allowlist — non-allowlisted fields stripped
- [ ] **AUDT-04**: Fail-secure event log entries (timestamp, session_id, failure_type, http_status)
- [ ] **AUDT-05**: Log entry written before HTTP response flushed

### Token Verification & Metrics

- [ ] **METR-01**: Post-restoration `\[[A-Z]+_\d+\]` scan on non-streaming responses
- [ ] **METR-02**: Post-stream verification scan on full assembled text
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
- [ ] **TEST-04**: Fail-secure — Detection/Cache/Timeout → HTTP 500, 0 forwarded
- [ ] **TEST-05**: Locale checksum — invalid checksums not flagged
- [ ] **TEST-06**: No-PII-in-logs — synthetic PII absent from log output
- [ ] **TEST-07**: Streaming round-trip — all split indices produce byte-for-byte match
- [ ] **TEST-08**: Cross-request randomization — 1000+ session pairs, ≥ 1 − 2⁻³² probability

### Developer Experience & Documentation

- [ ] **DOCS-01**: Integration quickstarts in 5 languages (EN, DE, FR, ES, PT-BR)
- [ ] **DOCS-02**: SDK examples for Python, Node.js, curl
- [ ] **DOCS-03**: `CHANGELOG.md` (Keep a Changelog format)
- [ ] **DOCS-04**: Apache 2.0 LICENSE, NOTICE file, SECURITY.md
- [ ] **DOCS-05**: README with "Why AnonReq" and "License and Commercial Use" sections

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

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

### Enterprise/Appliance Tier (Req 22–56)

- Rate limiting and spend controls (Req 22)
- Multimodal/structured document anonymization (Req 23)
- Operational observability and SLO dashboards (Req 24)
- Configuration change audit trail (Req 25)
- Supply chain security and SBOM automation (Req 26)
- AI Governance (ISO 42001/EU AI Act) — accountability, risk assessment, human oversight, transparency, lifecycle management, bias monitoring, third-party governance, post-deployment monitoring, conformity assessment (Req 27–35)
- Prompt security and AI firewall (Req 36)
- Financial services compliance — MNPI protection, MRM, data classification, financial crime controls, DORA resilience (Req 37–43)
- Data lineage and traceability (Req 44)
- Record retention and Legal Hold (Req 45)
- Data subject rights handling (Req 46)
- Breach notification automation (Req 47)
- Appliance tier — universal proxy, AI-aware DLP, agent governance, SOC integration, content disarm, behavioral analytics, network tap, WAF integration, compliance attestation (Req 48–56)

## Out of Scope

| Feature | Reason |
|---------|--------|
| LLM-based PII detection | The research found this consistently recommended against — slower, more expensive, less reliable than Presidio NER + regex combination |
| Persistent cache/disk storage | Contradicts the core ephemeral guarantee; defeats seizure-resistance requirement |
| UI dashboard | v1 is an API-only gateway; admin UI is enterprise/Appliance tier scope |
| Full SIEM/SOC integration | Appliance tier (Req 48–56); v1 uses stdout structured logs for consumption by existing log aggregators |
| Model training or fine-tuning | Out of scope — AnonReq uses pre-built Presidio models and hand-crafted regex patterns |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PIPE-01 | Phase 2 | Pending |
| PIPE-02 | Phase 2 | Pending |
| PIPE-03 | Phase 2 | Pending |
| PIPE-04 | Phase 2 | Pending |
| PIPE-05 | Phase 2 | Pending |
| PIPE-06 | Phase 2 | Pending |
| FAIL-01 | Phase 2 | Pending |
| FAIL-02 | Phase 2 | Pending |
| FAIL-03 | Phase 1 | Pending |
| FAIL-04 | Phase 1 | Pending |
| DET-01 | Phase 2 | Pending |
| DET-02 | Phase 2 | Pending |
| DET-03 | Phase 2 | Pending |
| DET-04 | Phase 2 | Pending |
| DET-05 | Phase 2 | Pending |
| DET-06 | Phase 2 | Pending |
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
| CACH-05 | Phase 3 | Pending |
| CACH-06 | Phase 2 | Pending |
| SSE-01 | Phase 3 | Pending |
| SSE-02 | Phase 3 | Pending |
| SSE-03 | Phase 3 | Pending |
| SSE-04 | Phase 3 | Pending |
| SSE-05 | Phase 3 | Pending |
| SSE-06 | Phase 3 | Pending |
| SSE-07 | Phase 3 | Pending |
| SSE-08 | Phase 3 | Pending |
| PROV-01 | Phase 2 | Pending |
| PROV-02 | Phase 3 | Pending |
| PROV-03 | Phase 3 | Pending |
| PROV-04 | Phase 3 | Pending |
| PROV-05 | Phase 3 | Pending |
| PROV-06 | Phase 3 | Pending |
| PROV-07 | Phase 3 | Pending |
| PROV-08 | Phase 3 | Pending |
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
| AUDT-01 | Phase 1 | Pending |
| AUDT-02 | Phase 1 | Pending |
| AUDT-03 | Phase 1 | Pending |
| AUDT-04 | Phase 2 | Pending |
| AUDT-05 | Phase 2 | Pending |
| METR-01 | Phase 5 | Pending |
| METR-02 | Phase 5 | Pending |
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
| TEST-04 | Phase 6 | Pending |
| TEST-05 | Phase 6 | Pending |
| TEST-06 | Phase 6 | Pending |
| TEST-07 | Phase 6 | Pending |
| TEST-08 | Phase 6 | Pending |
| DOCS-01 | Phase 7 | Pending |
| DOCS-02 | Phase 7 | Pending |
| DOCS-03 | Phase 7 | Pending |
| DOCS-04 | Phase 7 | Pending |
| DOCS-05 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 85 total (across 14 categories)
- Mapped to phases: 85
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-19*
*Last updated: 2026-06-19 after roadmap creation*
