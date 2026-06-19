# Roadmap: AnonReq

## Overview

AnonReq ships as 7 phases, each delivering a working, independently verifiable vertical slice of the self-hosted LLM anonymization gateway. Phase 1 establishes the deployment scaffold (Docker + health + audit). Phase 2 delivers the core value proposition: a non-streaming anonymization pipeline that detects PII via regex and NER, tokenizes with context-preserving placeholders, forwards sanitized requests to OpenAI, and restores original values in responses — all fail-secure. Phase 3 adds SSE streaming and multi-provider support (Anthropic, Gemini, Ollama). Phase 4 extends detection to 8 locales with checksum validation and compliance presets (GDPR, LGPD, PDPA, POPIA, Privacy Act, PIPEDA). Phase 5 adds operational observability (Prometheus metrics, post-restoration token verification). Phase 6 proves correctness with Hypothesis property-based tests. Phase 7 packages the project for open-source consumption with quickstarts, SDK examples, legal files, and changelog.

## Phases

- [ ] **Phase 1: Foundation** — Project scaffold, Docker Compose deployment, health endpoint, pre-flight checks, structured audit logging
- [ ] **Phase 2: Core Pipeline (Non-Streaming)** — Full anonymization pipeline with regex/NER detection, tokenization, caching, restoration, and OpenAI passthrough
- [ ] **Phase 3: SSE Streaming + Multi-Provider** — SSE streaming with Tail_Buffer, Anthropic/Gemini/Ollama provider adapters, model routing
- [ ] **Phase 4: Multi-Locale Detection + Compliance Presets** — 8 locale-specific recognizer bundles, checksum validation, per-jurisdiction compliance presets
- [ ] **Phase 5: Configuration & Observability** — Prometheus metrics, token verification, post-restoration scan
- [ ] **Phase 6: Property-Based Tests** — Hypothesis-based correctness tests for all invariants
- [ ] **Phase 7: Developer Experience & Documentation** — Quickstarts in 5 languages, SDK examples, CHANGELOG, legal files

## Phase Details

### Phase 1: Foundation
**Goal**: Project scaffold runs as Docker Compose deployment, exposes health endpoint, logs structured audit entries, and validates all component health before accepting traffic
**Mode**: mvp
**Depends on**: Nothing (first phase)
**Requirements**: DOCK-01, DOCK-02, DOCK-03, DOCK-04, DOCK-05, DOCK-06, DOCK-07, FAIL-03, FAIL-04, AUDT-01, AUDT-02, AUDT-03
**Success Criteria** (what must be TRUE):
  1. Operator can deploy all 3 containers with `docker-compose up` — anonreq, presidio-analyzer, valkey — and all services start successfully
  2. Operator can hit `GET /health` and receive `{"status": "ok"}` with per-component status for detection engine, cache, and gateway
  3. Operator sees structured JSON audit log lines in container stdout with timestamp, session_id, provider, and entity_counts fields; no raw PII values appear
  4. Operator can verify that pre-flight checks prevent gateway startup when Valkey or Presidio is unreachable
  5. Operator can configure the gateway entirely through environment variables with documented defaults; missing required env vars cause startup failure
**Plans**: 4 plans

Plans:
- [ ] 01-01: Project scaffolding, configuration management, and dependency setup
- [ ] 01-02: Docker Compose deployment (multi-stage Dockerfile, valkey config, presidio sidecar, .env.example)
- [ ] 01-03: Health endpoint (`GET /health`) and pre-flight startup checks
- [ ] 01-04: Structured audit logging infrastructure (JSON stdout, field allowlist, no-PII enforcement)

### Phase 2: Core Pipeline (Non-Streaming)
**Goal**: Full non-streaming anonymization pipeline — receives OpenAI-compatible chat request, detects PII across all message roles, replaces entities with `[TYPE_N]` tokens, forwards sanitized payload to OpenAI, caches mapping in Valkey, restores original values in response, and cleans up cache — all with fail-secure guarantees
**Mode**: mvp
**Depends on**: Phase 1
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, FAIL-01, FAIL-02, DET-01, DET-02, DET-03, DET-04, DET-05, DET-06, TOKN-01, TOKN-02, TOKN-03, TOKN-04, TOKN-05, TOKN-06, TOKN-07, CACH-01, CACH-02, CACH-03, CACH-04, CACH-06, PROV-01, AUDT-04, AUDT-05
**Success Criteria** (what must be TRUE):
  1. User can send a valid OpenAI-compatible `POST /v1/chat/completions` with PII in any message role (system, user, assistant, tool, function) and receive a fully restored response with original values back
  2. PII is detected by both regex tier (email, phone, credit card, IBAN, IP, URL, DOB, national IDs, SWIFT, crypto addresses) and NER tier (person names, organizations, addresses, cities, job titles); regex wins on overlap
  3. Same entity value repeated across a prompt produces the same `[TYPE_N]` token (deduplication); different values of the same type produce distinct tokens
  4. When detection engine or cache is unhealthy, all requests return HTTP 503 with no data forwarded upstream
  5. Cache mapping is deleted within 100ms of response delivery; no entities in prompt means no mapping created and request forwarded unchanged
**Plans**: 5 plans

Plans:
- [ ] 02-01: Valkey cache manager (connection pool, persistence-disabled config, TTL, async DEL, health check, monitoring lockdown)
- [ ] 02-02: Detection engine — regex recognizer tier (10+ pattern types) and NER recognizer tier (Presidio Analyzer sidecar), conflict resolution, confidence threshold, exclusion lists, custom YAML loading
- [ ] 02-03: Tokenization engine — `[TYPE_N]` format, deduplication, reverse-offset replacement, cryptographically random session seed, no-entity passthrough
- [ ] 02-04: Pipeline orchestration — POST /v1/chat/completions route, text extraction across all roles, composed step sequence (detect → tokenize → forward → restore → cleanup), fail-secure error boundaries
- [ ] 02-05: OpenAI passthrough with API key injection, generic error forwarding, audit log wiring (fail-secure events, pre-flush log entry)

### Phase 3: SSE Streaming + Multi-Provider
**Goal**: Streaming responses with real-time token restoration via Tail_Buffer state machine, plus multi-provider support for Anthropic Claude, Google Gemini, and Ollama via Provider_Adapter translation layer — all with fail-secure error handling for streaming and provider-specific scenarios
**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: SSE-01, SSE-02, SSE-03, SSE-04, SSE-05, SSE-06, SSE-07, SSE-08, PROV-02, PROV-03, PROV-04, PROV-05, PROV-06, PROV-07, PROV-08, CACH-05
**Success Criteria** (what must be TRUE):
  1. User can send `stream: true` and receive `text/event-stream` response with tokens restored in real-time; no full-response buffering occurs
  2. Tokens split across SSE chunk boundaries are correctly restored via Tail_Buffer; every chunk boundary position produces byte-for-byte match with the non-streamed response
  3. User can route prompts to Anthropic Claude, Google Gemini, and Ollama via model alias, receiving correctly formatted responses with restored PII
  4. User can call `GET /v1/models` and see all configured model aliases with their upstream provider mappings
  5. Provider errors return generic HTTP error messages containing no keys, URLs, or raw content; TTL auto-extends at 80% elapsed during long streams
**Plans**: 4 plans

Plans:
- [ ] 03-01: SSE streaming route path with Tail_Buffer state machine, HGETALL pre-fetch, case-insensitive + bracket-optional matching, flush heuristics, anti-buffering headers
- [ ] 03-02: Anthropic provider adapter (message format translation, API key injection, streaming support)
- [ ] 03-03: Gemini and Ollama provider adapters (contents[] format, OpenAI-compatible passthrough, streaming)
- [ ] 03-04: Model alias routing, GET /v1/models endpoint, generic error forwarding, CACH-05 TTL extension for streams

### Phase 4: Multi-Locale Detection + Compliance Presets
**Goal**: PII detection in 8 locales via `X-AnonReq-Locale` header with locale-specific regex recognizer bundles and checksum validation for national IDs, plus per-jurisdiction compliance presets that enforce mandated entity detection
**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: LOCL-01, LOCL-02, LOCL-03, LOCL-04, LOCL-05, LOCL-06, LOCL-07, COMP-01, COMP-02, COMP-03, COMP-04, COMP-05
**Success Criteria** (what must be TRUE):
  1. User can set `X-AnonReq-Locale: de-DE` and have German-specific PII detected (Steuer-ID, etc.); `fr-FR` detects NIR; `pt-BR` detects CPF/CNPJ; en, nl-NL, es, it-IT, ar each activate their locale-specific bundles
  2. User can specify multiple locales (e.g., `X-AnonReq-Locale: de-DE, fr-FR`) and get merged detection results
  3. Invalid or unsupported locale header returns HTTP 400 with descriptive error; missing locale header uses universal recognizers
  4. User can activate a compliance preset (`X-AnonReq-Preset: gdpr`) and have mandated entity types enforced at startup with rejection of misconfigured presets
  5. Audit log entries include `compliance_preset` field; merging multiple active presets produces union of entity types with highest confidence threshold
**Plans**: 3 plans

Plans:
- [ ] 04-01: Locale recognizer bundles (8 locale-specific YAML/config files with regex patterns for national IDs, phones, addresses, etc.)
- [ ] 04-02: Locale negotiation (header parsing, validation, multi-locale merging, fallback to universal, checksum validation for national IDs)
- [ ] 04-03: Compliance preset engine (GDPR, LGPD, PDPA, POPIA, Privacy Act, PIPEDA — startup validation, merged presets, audit field, GET /v1/compliance/presets endpoint)

### Phase 5: Configuration & Observability
**Goal**: Operational monitoring with Prometheus metrics and post-restoration token verification to detect any tokens that failed to restore
**Mode**: mvp
**Depends on**: Phase 3
**Requirements**: METR-01, METR-02, METR-03
**Success Criteria** (what must be TRUE):
  1. Operator can access `GET /metrics` and see Prometheus-formatted counters for total requests, detection latency (ms), entities detected, tokens restored, fail-secure events, and audit log failures
  2. Non-streaming responses are scanned for `[A-Z]+_\d+` patterns post-restoration; any residual tokens increment the `unrestored_tokens` counter
  3. Streaming responses are scanned on the fully assembled text after stream completion; residual tokens increment the same counter
**Plans**: 2 plans

Plans:
- [ ] 05-01: Prometheus metrics endpoint with counters (requests, latency, entities, unrestored tokens, fail-secure events, audit failures)
- [ ] 05-02: Post-restoration token verification scan (non-streaming + post-stream assembly scan)

### Phase 6: Property-Based Tests
**Goal**: Hypothesis-based generative test suite proving correctness of all core invariants — round-trip fidelity, token uniqueness, fail-secure guarantees, locale checksum, no-PII-in-logs, streaming integrity, and cross-request randomization
**Mode**: mvp
**Depends on**: Phase 4, Phase 5
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06, TEST-07, TEST-08
**Success Criteria** (what must be TRUE):
  1. Hypothesis generates 1000+ random inputs and confirms round-trip correctness: anonymize → restore produces byte-for-byte match with original input
  2. Hypothesis confirms token uniqueness invariant: N distinct entity values produce exactly N distinct tokens; same value K times produces exactly 1 token
  3. Hypothesis confirms fail-secure invariant: detection failure, cache failure, or timeout always produce HTTP 500 with 0 bytes forwarded
  4. Hypothesis confirms streaming round-trip at every possible token split index position: byte-for-byte match with non-streamed response
  5. Hypothesis confirms cross-request randomization over 1000+ session pairs with probability ≥ 1 − 2⁻³²
**Plans**: 3 plans

Plans:
- [ ] 06-01: Round-trip correctness, token uniqueness, and deduplication tests (TEST-01, TEST-02, TEST-03)
- [ ] 06-02: Fail-secure, locale checksum, and no-PII-in-logs tests (TEST-04, TEST-05, TEST-06)
- [ ] 06-03: Streaming round-trip and cross-request randomization tests (TEST-07, TEST-08)

### Phase 7: Developer Experience & Documentation
**Goal**: Open-source ready repository with integration quickstarts in 5 languages, SDK examples, CHANGELOG, Apache 2.0 license, SECURITY.md, and a comprehensive README
**Mode**: mvp
**Depends on**: Phase 6
**Requirements**: DOCS-01, DOCS-02, DOCS-03, DOCS-04, DOCS-05
**Success Criteria** (what must be TRUE):
  1. Developer can follow the English quickstart and have AnonReq processing requests in under 5 minutes with `docker-compose up` and `curl`
  2. Developer can copy-paste Python, Node.js, and curl SDK examples from the documentation and see a working anonymization round-trip
  3. Repository includes Apache 2.0 LICENSE, NOTICE file (with third-party attributions), SECURITY.md (with reporting policy), and README covering "Why AnonReq" and "License and Commercial Use"
  4. CHANGELOG.md follows Keep a Changelog format with entries for all previous phases
**Plans**: 3 plans

Plans:
- [ ] 07-01: Integration quickstarts in EN, DE, FR, ES, PT-BR
- [ ] 07-02: SDK examples (Python, Node.js, curl) and README with "Why AnonReq" and "License and Commercial Use"
- [ ] 07-03: CHANGELOG.md (Keep a Changelog), Apache 2.0 LICENSE, NOTICE file, SECURITY.md

## Progress

**Execution Order:** Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7
**Parallelism:** Plans within a phase execute in parallel where independent (config: parallelization = true)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/4 | Not started | - |
| 2. Core Pipeline (Non-Streaming) | 0/5 | Not started | - |
| 3. SSE Streaming + Multi-Provider | 0/4 | Not started | - |
| 4. Multi-Locale Detection + Compliance Presets | 0/3 | Not started | - |
| 5. Configuration & Observability | 0/2 | Not started | - |
| 6. Property-Based Tests | 0/3 | Not started | - |
| 7. Developer Experience & Documentation | 0/3 | Not started | - |
