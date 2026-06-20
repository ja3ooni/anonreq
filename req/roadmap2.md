# Roadmap: AnonReq

## Overview

AnonReq is positioned as the **AI Security Gateway for regulated enterprises**, enforcing data sovereignty, compliance, and IP protection between employees and AI providers.

It ships as 7 phases, each delivering a working, independently verifiable vertical slice.
Based on strategic review (v1) and gap analysis (v2), the execution order has been hardened:

1. **Fail-secure error boundaries and logging** are the very first things built in Phase 1, ensuring zero PII leaks during development.
2. **Static bearer token authentication** (AUTH-MINIMAL-01) is added to Phase 1 — the gateway must not ship open.
3. **Classification & Routing** (Block/Route) is integrated into Phase 2 with explicit YAML-configurable acceptance criteria.
4. **Property-based testing** is pulled forward into Phase 2 and 3 to prove invariants immediately.
5. **Phase 3 plans execute in strict serial order** (03-02 → 03-01 → 03-03 → 03-04) because provider wire formats must be understood before the Tail_Buffer FSM is built.
6. **Client disconnect handling** is an explicit acceptance criterion in Plan 03-01.
7. **P95 latency SLO** is measured with a load test in Phase 5 using `en_core_web_sm` as the default Presidio model.

## Phases

- [ ] **Phase 1: Foundation, Fail-Secure & Auth** — Project scaffold, Docker Compose deployment, global exception handlers, structured audit logging, health endpoint, and static bearer token middleware.
- [ ] **Phase 2: Core Pipeline & Classification** — YAML-configurable classification (Block/Route/Anonymize/Pass), regex/NER detection, tokenization, caching, OpenAI passthrough, and initial property tests.
- [ ] **Phase 3: SSE Streaming + Multi-Provider** — Provider adapters first (03-02), then Tail_Buffer FSM with client disconnect handling (03-01), model routing, and streaming property tests.
- [ ] **Phase 4: Multi-Locale Detection + Compliance Presets** — 8 locale-specific recognizer bundles, checksum validation, per-jurisdiction compliance presets.
- [ ] **Phase 5: Configuration & Observability** — Prometheus metrics, P95 load test (k6/locust), post-restoration scan.
- [ ] **Phase 6: Advanced Property-Based Tests** — Exhaustive Hypothesis tests for cross-request randomization, fail-secure scenarios, and locale checksums.
- [ ] **Phase 7: Developer Experience & Documentation** — Quickstarts in 5 languages, SDK examples, CHANGELOG, legal files.

---

## Phase Details

### Phase 1: Foundation, Fail-Secure & Auth
**Goal**: Establish a bulletproof, leak-free, authenticated scaffold. The global exception handler and structured logging must be built *before* any pipeline code. Static bearer token auth must be in place before any route is exposed.
**Mode**: mvp
**Depends on**: Nothing (first phase)
**Requirements**: DOCK-01 to DOCK-07, FAIL-01 to FAIL-04, AUDT-01 to AUDT-03, **AUTH-MINIMAL-01**
**Success Criteria**:
  1. Global exception handler intercepts all errors and returns static HTTP 500 without request bodies.
  2. Structured JSON logger uses a strict allowlist; `logger.exception()` sanitizes tracebacks.
  3. Operator can deploy all 3 containers with `docker-compose up`.
  4. Pre-flight checks prevent gateway startup if Valkey or Presidio is unreachable.
  5. All routes return HTTP 401 if the `Authorization: Bearer <token>` header is missing or does not match `ANONREQ_API_KEY`. Missing env var causes startup failure.

Plans:
- [ ] 01-01: Project scaffolding, configuration management, and dependency setup.
- [ ] 01-02: Global exception handler and structured audit logging infrastructure (no-PII enforcement).
- [ ] 01-03: Docker Compose deployment (multi-stage Dockerfile, valkey config, presidio sidecar).
- [ ] 01-04: Health endpoint (`GET /health`) and pre-flight startup checks.
- [ ] **01-05: Static bearer token middleware** — single env var `ANONREQ_API_KEY`, FastAPI dependency injected on all routes, returns HTTP 401 if missing or invalid. Does not implement OAuth/RBAC (deferred). Covers AUTH-MINIMAL-01.

---

### Phase 2: Core Pipeline & Classification (Non-Streaming)
**Goal**: Full non-streaming pipeline with YAML-configurable classification, PII detection, tokenization, caching, OpenAI passthrough, and immediate Hypothesis property tests.
**Mode**: mvp
**Depends on**: Phase 1
**Requirements**: PIPE-01 to PIPE-06, DET-01 to DET-06, TOKN-01 to TOKN-07, CACH-01 to CACH-06, PROV-01, AUDT-04 to AUDT-05, TEST-01 to TEST-03
**Success Criteria**:
  1. Classification is rule-based and configurable via YAML at startup. Default rules ship with the gateway.
  2. Rules match on: entity type detected (e.g., `FINANCIAL_DATA`, `SOURCE_CODE`), keyword patterns, and/or content length thresholds.
  3. Four tiers enforced: `PASS` (no action), `ANONYMIZE` (default), `ROUTE_LOCAL` (forward to configured on-prem endpoint), `BLOCK` (return HTTP 403 with audit log entry).
  4. Classification decision and tier are included in every audit log entry.
  5. PII is detected by regex and NER tiers; tokenized with `[TYPE_N]`; deduplicated correctly.
  6. OpenAI passthrough works and responses are fully restored.
  7. Cache mapping is deleted within 100ms of response delivery.
  8. **Hypothesis test**: known-restricted content always produces `BLOCK`, never reaches provider.
  9. **Hypothesis tests** pass for round-trip correctness and token uniqueness.

Plans:
- [ ] 02-01: Valkey cache manager (atomic SETEX, volatile-lru, async DEL).
- [ ] **02-02: Classification engine** — YAML-configurable rules (entity type, keyword, length), four tiers (PASS / ANONYMIZE / ROUTE_LOCAL / BLOCK), audit log field, startup validation. Detection engine (regex/NER) integrated in same plan.
- [ ] 02-03: Tokenization engine (`[TYPE_N]` format, deduplication, reverse-offset).
- [ ] 02-04: Pipeline orchestration (POST /v1/chat/completions) and OpenAI passthrough.
- [ ] 02-05: Property tests (Hypothesis) for round-trip correctness, token uniqueness, and BLOCK invariant.

---

### Phase 3: SSE Streaming + Multi-Provider
**Goal**: Streaming responses with real-time token restoration via Tail_Buffer, multi-provider support, client disconnect handling, and streaming property tests.
**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: SSE-01 to SSE-08, PROV-02 to PROV-08, CACH-05, TEST-07

> **Execution Order (serial, not parallel):** `03-02 → 03-01 → 03-03 → 03-04`
> Provider wire formats must be fully understood before the Tail_Buffer state machine is built.
> Anthropic's SSE format (`data: {"type":"content_block_delta"}`) differs structurally from OpenAI's (`data: {"choices":[{"delta":...}]}`). Building Tail_Buffer before understanding these formats will produce a broken FSM.

**Success Criteria**:
  1. `stream: true` requests return tokens restored in real-time without full buffering.
  2. Tail_Buffer correctly restores tokens split across SSE chunk boundaries.
  3. On client disconnect (detected via `await request.is_disconnected()`), the upstream HTTPX stream is cancelled, the Valkey mapping is deleted, and a disconnect event is logged with `session_id` and `bytes_delivered`.
  4. Prompts route successfully to Anthropic Claude, Google Gemini, and Ollama.
  5. **Hypothesis tests** confirm streaming round-trip matches non-streamed byte-for-byte at all split indices.

Plans:
- [ ] 03-02: **Anthropic, Gemini, and Ollama provider adapters** — wire format translation, API key injection, streaming support. *Must be completed before 03-01.*
- [ ] **03-01: SSE streaming route path with Tail_Buffer FSM** — built after 03-02 so provider token formats are known. Includes: anti-buffering headers, HGETALL pre-fetch, case-insensitive matching, flush heuristics, and **client disconnect handling** (`await request.is_disconnected()` → cancel upstream stream → DEL mapping → log event).
- [ ] 03-03: Model alias routing and `GET /v1/models` endpoint.
- [ ] 03-04: Property tests (Hypothesis) for streaming split-token restoration.

---

### Phase 4: Multi-Locale Detection + Compliance Presets
**Goal**: PII detection in 8 locales with checksum validation and per-jurisdiction compliance presets.
**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: LOCL-01 to LOCL-07, COMP-01 to COMP-05

Plans:
- [ ] 04-01: Locale recognizer bundles (8 locale-specific YAML configs).
- [ ] 04-02: Locale negotiation and checksum validation for national IDs.
- [ ] 04-03: Compliance preset engine (GDPR, LGPD, PDPA, POPIA, Privacy Act, PIPEDA) and startup validation.

---

### Phase 5: Configuration & Observability
**Goal**: Operational monitoring with Prometheus metrics, P95 latency load test, and post-restoration token verification.
**Mode**: mvp
**Depends on**: Phase 3
**Requirements**: METR-01 to METR-03, **PIPE-06 (P95 ≤ 100ms)**

**Success Criteria**:
  1. Operator can access `GET /metrics` and see Prometheus-formatted counters for total requests, detection latency (ms), entities detected, tokens restored, fail-secure events, and audit log failures.
  2. Non-streaming and streaming responses are scanned for residual `[A-Z]+_\d+` patterns post-restoration.
  3. **Load test passes**: 50 concurrent users, 1,000-word prompts, P95 processing overhead ≤ 100ms. Default Presidio model is `en_core_web_sm` (not `lg`) — `sm` delivers <10ms/1K tokens vs `lg`'s 15–30ms with spike potential over 200ms.

Plans:
- [ ] **05-01: Prometheus metrics endpoint** (`/metrics`) with counters (requests, latency, entities, unrestored tokens, fail-secure events, audit failures). Includes **k6 or locust load test**: 50 concurrent users, 1,000-word prompts, assert P95 ≤ 100ms. Documents `en_core_web_sm` as default model with rationale.
- [ ] 05-02: Post-restoration token verification scan (non-streaming + post-stream assembly scan).

---

### Phase 6: Advanced Property-Based Tests
**Goal**: Complete the generative test suite for edge cases not covered in Phase 2/3.
**Mode**: mvp
**Depends on**: Phase 4, Phase 5
**Requirements**: TEST-04 to TEST-06, TEST-08

Plans:
- [ ] 06-01: Fail-secure and no-PII-in-logs property tests.
- [ ] 06-02: Cross-request randomization probability tests.
- [ ] 06-03: Locale checksum invalidation tests.

---

### Phase 7: Developer Experience & Documentation
**Goal**: Open-source ready repository.
**Mode**: mvp
**Depends on**: Phase 6
**Requirements**: DOCS-01 to DOCS-05

Plans:
- [ ] 07-01: Integration quickstarts (EN, DE, FR, ES, PT-BR).
- [ ] 07-02: SDK examples (Python, Node.js, curl).
- [ ] 07-03: CHANGELOG, Apache 2.0 LICENSE, SECURITY.md, and README.

---

## Progress

**Execution Order:** Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7
**Phase 3 plans execute in serial order:** 03-02 → 03-01 → 03-03 → 03-04

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation, Fail-Secure & Auth | 0/5 | Not started | - |
| 2. Core Pipeline & Classification | 0/5 | Not started | - |
| 3. SSE Streaming + Multi-Provider | 0/4 | Not started | - |
| 4. Multi-Locale Detection + Compliance Presets | 0/3 | Not started | - |
| 5. Configuration & Observability | 0/2 | Not started | - |
| 6. Advanced Property-Based Tests | 0/3 | Not started | - |
| 7. Developer Experience & Documentation | 0/3 | Not started | - |

---

## New Requirements Added

| Req ID | Phase | Description |
|--------|-------|-------------|
| AUTH-MINIMAL-01 | 1 | Static bearer token middleware — `ANONREQ_API_KEY` env var, HTTP 401 on missing/invalid token |
| CLASS-AC-01 to 05 | 2 | Classification acceptance criteria: YAML rules, four tiers, audit log field, BLOCK Hypothesis test |
| SSE-DISCONNECT-01 | 3 | Client disconnect → cancel upstream stream → DEL mapping → log event |
| PERF-LOAD-01 | 5 | k6/locust load test: 50 concurrent users, 1K-word prompts, P95 ≤ 100ms; `en_core_web_sm` default |
