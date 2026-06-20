# Roadmap: AnonReq

## Overview

AnonReq is positioned as the **AI Security Gateway for regulated enterprises**, enforcing data sovereignty, compliance, and IP protection between employees and AI providers.

It ships as 7 phases, each delivering a working, independently verifiable vertical slice. 
Based on strategic review, the execution order has been hardened:
1. **Fail-secure error boundaries and logging** are now the very first things built in Phase 1, ensuring zero PII leaks during development.
2. **Classification & Routing** (Block/Route) is integrated into Phase 2 to handle confidential IP that cannot be anonymized.
3. **Property-based testing** is pulled forward into Phase 2 and 3 to prove invariants immediately, rather than waiting until the end.

## Phases

- [ ] **Phase 1: Foundation & Fail-Secure** — Project scaffold, Docker Compose deployment, global exception handlers (no PII leaks), health endpoint, and structured audit logging.
- [ ] **Phase 2: Core Pipeline & Classification** — Payload classification (Block/Route), regex/NER detection, tokenization, caching, restoration, OpenAI passthrough, and initial property tests (round-trip, token uniqueness).
- [ ] **Phase 3: SSE Streaming + Multi-Provider** — SSE streaming with Tail_Buffer, Anthropic/Gemini/Ollama adapters, model routing, and streaming property tests.
- [ ] **Phase 4: Multi-Locale Detection + Compliance Presets** — 8 locale-specific recognizer bundles, checksum validation, per-jurisdiction compliance presets.
- [ ] **Phase 5: Configuration & Observability** — Prometheus metrics, token verification, post-restoration scan.
- [ ] **Phase 6: Advanced Property-Based Tests** — Exhaustive Hypothesis tests for cross-request randomization, fail-secure scenarios, and locale checksums.
- [ ] **Phase 7: Developer Experience & Documentation** — Quickstarts in 5 languages, SDK examples, CHANGELOG, legal files.

## Phase Details

### Phase 1: Foundation & Fail-Secure
**Goal**: Establish a bulletproof, leak-free scaffold. The global exception handler and structured logging must be built *before* any pipeline code to ensure unhandled exceptions never leak PII into logs or HTTP responses.
**Mode**: mvp
**Depends on**: Nothing (first phase)
**Requirements**: DOCK-01 to DOCK-07, FAIL-01 to FAIL-04, AUDT-01 to AUDT-03
**Success Criteria**:
  1. Global exception handler intercepts all errors and returns static HTTP 500 without request bodies.
  2. Structured JSON logger uses a strict allowlist; `logger.exception()` sanitizes tracebacks.
  3. Operator can deploy all 3 containers with `docker-compose up`.
  4. Pre-flight checks prevent gateway startup if Valkey or Presidio is unreachable.

Plans:
- [ ] 01-01: Project scaffolding, configuration management, and dependency setup.
- [ ] 01-02: Global exception handler and structured audit logging infrastructure (no-PII enforcement).
- [ ] 01-03: Docker Compose deployment (multi-stage Dockerfile, valkey config, presidio sidecar).
- [ ] 01-04: Health endpoint (`GET /health`) and pre-flight startup checks.

### Phase 2: Core Pipeline & Classification (Non-Streaming)
**Goal**: Full non-streaming pipeline that classifies payloads (Block/Route for IP), detects PII, tokenizes, forwards to OpenAI, restores, and proves correctness via Hypothesis tests immediately.
**Mode**: mvp
**Depends on**: Phase 1
**Requirements**: PIPE-01 to PIPE-06, DET-01 to DET-06, TOKN-01 to TOKN-07, CACH-01 to CACH-06, PROV-01, AUDT-04 to AUDT-05, TEST-01 to TEST-03
**Success Criteria**:
  1. Payload classification blocks or routes "Highly Restricted" content before anonymization.
  2. PII is detected by regex and NER tiers; tokenized with `[TYPE_N]`; deduplicated correctly.
  3. OpenAI passthrough works and responses are fully restored.
  4. Cache mapping is deleted within 100ms of response delivery.
  5. **Hypothesis tests** pass for round-trip correctness and token uniqueness.

Plans:
- [ ] 02-01: Valkey cache manager (atomic SETEX, volatile-lru, async DEL).
- [ ] 02-02: Classification engine (Block/Route logic for confidential IP) and Detection engine (regex/NER).
- [ ] 02-03: Tokenization engine (`[TYPE_N]` format, deduplication, reverse-offset).
- [ ] 02-04: Pipeline orchestration (POST /v1/chat/completions) and OpenAI passthrough.
- [ ] 02-05: Property tests (Hypothesis) for round-trip correctness and token uniqueness.

### Phase 3: SSE Streaming + Multi-Provider
**Goal**: Streaming responses with real-time token restoration via Tail_Buffer, multi-provider support, and streaming property tests.
**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: SSE-01 to SSE-08, PROV-02 to PROV-08, CACH-05, TEST-07
**Success Criteria**:
  1. `stream: true` requests return tokens restored in real-time without full buffering.
  2. Tail_Buffer correctly restores tokens split across SSE chunk boundaries.
  3. Prompts route successfully to Anthropic Claude, Google Gemini, and Ollama.
  4. **Hypothesis tests** confirm streaming round-trip matches non-streamed byte-for-byte at all split indices.

Plans:
- [ ] 03-01: SSE streaming route path with Tail_Buffer FSM and anti-buffering headers.
- [ ] 03-02: Anthropic, Gemini, and Ollama provider adapters.
- [ ] 03-03: Model alias routing and `GET /v1/models` endpoint.
- [ ] 03-04: Property tests (Hypothesis) for streaming split-token restoration.

### Phase 4: Multi-Locale Detection + Compliance Presets
**Goal**: PII detection in 8 locales with checksum validation and per-jurisdiction compliance presets.
**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: LOCL-01 to LOCL-07, COMP-01 to COMP-05

Plans:
- [ ] 04-01: Locale recognizer bundles (8 locale-specific YAML configs).
- [ ] 04-02: Locale negotiation and checksum validation for national IDs.
- [ ] 04-03: Compliance preset engine (GDPR, LGPD, etc.) and startup validation.

### Phase 5: Configuration & Observability
**Goal**: Operational monitoring with Prometheus metrics and post-restoration token verification.
**Mode**: mvp
**Depends on**: Phase 3
**Requirements**: METR-01 to METR-03

Plans:
- [ ] 05-01: Prometheus metrics endpoint (`/metrics`).
- [ ] 05-02: Post-restoration token verification scan (non-streaming + post-stream).

### Phase 6: Advanced Property-Based Tests
**Goal**: Complete the generative test suite for edge cases not covered in Phase 2/3.
**Mode**: mvp
**Depends on**: Phase 4, Phase 5
**Requirements**: TEST-04 to TEST-06, TEST-08

Plans:
- [ ] 06-01: Fail-secure and no-PII-in-logs property tests.
- [ ] 06-02: Cross-request randomization probability tests.
- [ ] 06-03: Locale checksum invalidation tests.

### Phase 7: Developer Experience & Documentation
**Goal**: Open-source ready repository.
**Mode**: mvp
**Depends on**: Phase 6
**Requirements**: DOCS-01 to DOCS-05

Plans:
- [ ] 07-01: Integration quickstarts (EN, DE, FR, ES, PT-BR).
- [ ] 07-02: SDK examples (Python, Node.js, curl).
- [ ] 07-03: CHANGELOG, Apache 2.0 LICENSE, SECURITY.md, and README.

## Progress

**Execution Order:** Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Fail-Secure | 0/4 | Not started | - |
| 2. Core Pipeline & Classification | 0/5 | Not started | - |
| 3. SSE Streaming + Multi-Provider | 0/4 | Not started | - |
| 4. Multi-Locale Detection + Compliance Presets | 0/3 | Not started | - |
| 5. Configuration & Observability | 0/2 | Not started | - |
| 6. Advanced Property-Based Tests | 0/3 | Not started | - |
| 7. Developer Experience & Documentation | 0/3 | Not started | - |
