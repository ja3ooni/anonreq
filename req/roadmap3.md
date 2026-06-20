# Roadmap: AnonReq

## Overview

AnonReq is the **AI Security Gateway for regulated enterprises**, enforcing data
sovereignty, compliance, and IP protection between employees and AI providers. It
intercepts outbound AI traffic, classifies payloads, anonymizes PII, forwards
sanitized requests to external LLM providers, and restores original values in
responses — all within the customer's secure perimeter.

It ships as 7 phases, each delivering a working, independently verifiable vertical
slice of the gateway.

**Three hardening decisions embedded in this roadmap:**

1. **Fail-secure error boundaries and auth are Phase 1, Plans 01-02 and 01-05** —
   the global exception handler, structured logging (no-PII enforcement), and static
   bearer token middleware are built before any pipeline code. An unhandled exception
   must never leak PII into logs or HTTP responses. An unauthenticated request must
   never reach the pipeline.

2. **Classification runs before anonymization (Phase 2, Plan 02-02)** — payloads
   are classified into BLOCK / ROUTE_LOCAL / ANONYMIZE / PASS before they reach
   Presidio. Confidential IP that cannot be meaningfully anonymized (entire
   architecture documents, source code + financial identifiers combined) is blocked
   at the gateway, never forwarded.

3. **Property-based tests are written alongside the phases they prove** — round-trip
   correctness and token uniqueness tests land in Phase 2; streaming split-token tests
   land in Phase 3. Tests prove each phase before the next begins.

---

## Phases

- [ ] **Phase 1: Foundation & Fail-Secure** — Scaffold, auth middleware, exception
  handler, audit logging, Docker Compose deployment, health endpoint, pre-flight
  checks.
- [ ] **Phase 2: Core Pipeline & Classification** — Payload classification
  (Block/Route), regex/NER detection, tokenization, caching, restoration, OpenAI
  passthrough, and initial property tests.
- [ ] **Phase 3: SSE Streaming + Multi-Provider** — SSE streaming with Tail_Buffer,
  Anthropic/Gemini/Ollama adapters, model routing, and streaming property tests.
- [ ] **Phase 4: Multi-Locale Detection + Compliance Presets** — 8 locale-specific
  recognizer bundles, checksum validation, per-jurisdiction compliance presets.
- [ ] **Phase 5: Configuration & Observability** — Prometheus metrics, P95 load
  test, post-restoration token verification.
- [ ] **Phase 6: Advanced Property-Based Tests** — Exhaustive Hypothesis tests for
  cross-request randomization, fail-secure scenarios, and locale checksums.
- [ ] **Phase 7: Developer Experience & Documentation** — Quickstarts in 5
  languages, SDK examples, CHANGELOG, legal files.

---

## Phase Details

### Phase 1: Foundation & Fail-Secure

**Goal**: Establish a leak-free, authenticated scaffold. The global exception handler,
no-PII logging, and bearer token middleware must exist before any pipeline code.
Nothing that touches request data ships until these three guarantees are in place.

**Mode**: mvp
**Depends on**: Nothing (first phase)
**Requirements**: DOCK-01 to DOCK-07, FAIL-01 to FAIL-04, AUDT-01 to AUDT-03,
AUTH-MINIMAL-01

**Success Criteria**:

1. Global exception handler intercepts all errors and returns a static
   `{"error":"internal_error"}` HTTP 500 body. No request body, stack trace, token
   value, or PII substring appears in the response or in log output. Verified by
   injecting synthetic PII into the pipeline, triggering a forced exception, and
   asserting zero PII substrings in log output.
2. Structured JSON logger writes to stdout using a strict field allowlist.
   `logger.exception()` calls sanitize tracebacks before writing. Non-allowlisted
   fields are stripped, not redacted.
3. Operator can deploy all three containers (`anonreq`, `presidio-analyzer`, `valkey`)
   with `docker-compose up`. All services reach healthy state within 60 seconds.
4. Pre-flight checks prevent gateway startup when Valkey or Presidio is unreachable.
   Gateway returns a clear error message identifying the unhealthy component.
5. All routes return HTTP 401 with body `{"error":"unauthorized"}` when the
   `Authorization: Bearer <token>` header is absent or does not match
   `ANONREQ_API_KEY`. Gateway startup fails with a clear error if `ANONREQ_API_KEY`
   is unset or fewer than 32 characters.

**Plans**:

- [ ] **01-01**: Project scaffolding, configuration management, and dependency setup.
  Python 3.12, FastAPI, uvicorn, HTTPX, redis-py, Presidio Analyzer client,
  prometheus-client, pyyaml, pydantic-settings. `pyproject.toml` with pinned
  versions. `.env.example` documenting every env var with defaults and validation
  rules. Startup fails on missing required vars with a descriptive error naming the
  missing key.

- [ ] **01-02**: Global exception handler and structured audit logging
  infrastructure. Single top-level `@app.exception_handler(Exception)` returns
  static HTTP 500 — never includes request content, tracebacks, or token values.
  Structured JSON logger configured via `logging.config.dictConfig` with a field
  allowlist enforced before every write. Allowlisted fields: `timestamp`,
  `session_id`, `provider`, `model`, `entity_counts`, `latency_ms`,
  `compliance_preset`, `locale`, `classification_tier`, `http_status`,
  `failure_type`. Any other field is stripped silently.

- [ ] **01-03**: Docker Compose deployment. Multi-stage Dockerfile using
  `python:3.12-slim` with final image ≤ 2 GB. `docker-compose.yml` with three
  services: `anonreq`, `presidio` (`mcr.microsoft.com/presidio-analyzer:latest`),
  `valkey` (`valkey/valkey:7.2-alpine` — pin to a specific verified patch version).
  Valkey configured with `--save "" --appendonly no --maxmemory 256mb
  --maxmemory-policy allkeys-lru`. All services bound to an internal Docker network;
  no external port exposure without an override file. `depends_on` with
  `service_healthy` for both Presidio and Valkey.

- [ ] **01-04**: Health endpoint and pre-flight startup checks. `GET /health` returns
  `{"status":"ok","components":{"detection":"ok","cache":"ok"}}` when all components
  are reachable, or HTTP 503 with per-component status when degraded. Pre-flight
  check on FastAPI lifespan startup: ping Presidio `/health` and Valkey `PING`.
  Gateway does not accept traffic until both pass. `CACH-06`: health check verifies
  Valkey persistence is disabled at runtime (assert `CONFIG GET save` returns empty).

- [ ] **01-05**: Static bearer token middleware. FastAPI dependency injected on all
  non-health routes. Reads `Authorization: Bearer <token>` header. Returns HTTP 401
  with body `{"error":"unauthorized"}` if header is absent or token does not match
  `ANONREQ_API_KEY`. Token value never appears in logs, error bodies, or tracebacks.
  Gateway startup fails if `ANONREQ_API_KEY` is unset or fewer than 32 characters,
  with error: `ANONREQ_API_KEY must be set and at least 32 characters. Refusing to
  start with no authentication.`

---

### Phase 2: Core Pipeline & Classification (Non-Streaming)

**Goal**: Full non-streaming pipeline. Classifies the payload first (Block/Route for
confidential IP that cannot be anonymized), then detects PII via regex and NER,
tokenizes with context-preserving placeholders, forwards the sanitized request to
OpenAI, caches the mapping in Valkey, restores original values in the response, and
cleans up. Correctness is proven by Hypothesis tests before Phase 3 begins.

**Mode**: mvp
**Depends on**: Phase 1
**Requirements**: PIPE-01 to PIPE-06, FAIL-01 to FAIL-02, DET-01 to DET-06,
TOKN-01 to TOKN-07, CACH-01 to CACH-06, PROV-01, AUDT-04 to AUDT-05,
TEST-01 to TEST-03

**Success Criteria**:

1. Payload classification runs before Presidio is called. Payloads matching BLOCK
   rules return HTTP 403 with audit log entry and zero bytes forwarded to any
   provider. ROUTE_LOCAL payloads are forwarded to the configured on-prem endpoint,
   not the external provider.
2. PII is detected by both the regex tier (email, phone, credit card, IBAN, IP, URL,
   DOB, national IDs, SWIFT, crypto addresses) and NER tier (names, orgs, addresses,
   job titles). Regex wins on overlap.
3. Same entity value repeated across a prompt produces the same `[TYPE_N]` token
   (deduplication). Different values of the same type produce distinct tokens with
   different indices.
4. When the detection engine or cache is unhealthy, all requests return HTTP 503 with
   zero data forwarded upstream.
5. Cache mapping is deleted within 100ms of response delivery. No mapping is created
   when zero entities are detected; request is forwarded unchanged.
6. Hypothesis tests pass for round-trip correctness (anonymize → restore produces
   byte-for-byte match) and token uniqueness (N distinct values → N distinct tokens;
   same value K times → 1 token).

**Plans**:

- [ ] **02-01**: Valkey cache manager. Async `redis.asyncio` client with connection
  pool. Key format: `anonreq:{session_id}` (hash type). TTL range 60–3600s (default
  300s, configurable). `HSET` mapping on write, `HGETALL` on read, async `DEL`
  within 100ms post-response (TTL as fallback). `CACH-03`: disable `MONITOR` and
  `SLOWLOG` via ACL or config. `CACH-05`: TTL extension at 80% elapsed during long
  streams (implemented here, used in Phase 3). Health check verifies reachability,
  read/write roundtrip, and persistence disabled.

- [ ] **02-02**: Classification engine and Detection engine.

  **Classification engine** runs first in the pipeline. Four tiers evaluated in
  order:

  | Tier         | Action                                       | HTTP behaviour       |
  |--------------|----------------------------------------------|----------------------|
  | BLOCK        | Reject immediately                           | HTTP 403, audit log  |
  | ROUTE_LOCAL  | Forward to configured on-prem model endpoint | Bypass external LLM  |
  | ANONYMIZE    | Default — detect PII, tokenize, forward      | Normal pipeline      |
  | PASS         | Forward unchanged, no detection              | Normal passthrough   |

  Rules are YAML-configurable at startup via `ANONREQ_CLASSIFICATION_RULES` env var
  pointing to a rules file. Hot-reload is out of scope for v1 — restart required.

  Default rules shipped with the gateway:
  - BLOCK if detected entity types include both `SOURCE_CODE` and
    `FINANCIAL_IDENTIFIER` in the same request.
  - BLOCK if request body exceeds `ANONREQ_BLOCK_SIZE_KB` (default 500 KB) and
    contains any financial entity — full architecture documents cannot be meaningfully
    anonymized.
  - BLOCK if content matches `MNPI_PATTERNS` keyword list (configurable).
  - ANONYMIZE for all other requests containing detected PII.
  - PASS for requests where Presidio detects zero entities above confidence threshold.

  Every audit log entry includes: `classification_tier`, `classification_rule_matched`,
  and `action_taken`.

  **Detection engine**: Hybrid regex + NER pipeline via Presidio Analyzer sidecar
  (HTTP, not in-process). Regex recognizer tier: email, phone (E.164), credit card
  (Luhn), IBAN, IP, URL, DOB, national IDs, SWIFT, crypto addresses. NER recognizer
  tier: person names, organizations, addresses, cities, job titles via `en_core_web_sm`
  (not `lg` — sm delivers < 10ms per 1,000 tokens vs lg's 15–30ms with spike
  potential above 200ms on cold requests). Regex wins on span overlap. Configurable
  `Confidence_Threshold` per entity type (default 0.7, recommended 0.85 for
  structured types). `Exclusion_List` with exact match and wildcard support. Custom
  recognizer patterns loaded from YAML at startup. Ship a default exclusion list seed
  file with common financial sector false positives (fund codes, internal reference
  numbers, account-code-like sequences that Presidio would otherwise flag).

- [ ] **02-03**: Tokenization engine. Token format `[TYPE_N]` with uppercase TYPE
  (1–20 chars) and positive integer N. Same entity value → same token (deduplication
  map keyed on normalized value). Different values of same type → distinct tokens with
  different indices. Reverse character-offset replacement to prevent position drift.
  Cryptographically random seed per session (`secrets.token_hex(32)`) drives token
  index assignment — same PII in different sessions produces different token strings,
  preventing cross-session correlation. No mapping created when zero entities detected;
  request forwarded unchanged.

- [ ] **02-04**: Pipeline orchestration and OpenAI passthrough. `POST
  /v1/chat/completions` route handler. Composable step sequence using `RequestContext`
  dataclass passed through each stage: classify → extract text → detect → tokenize →
  cache write → provider call → restore → cache cleanup → audit log. Fail-secure
  error boundary: any step setting `ctx.errors` short-circuits to HTTP 500 via
  `fail_secure(ctx)` — no data forwarded. OpenAI passthrough via
  `httpx.AsyncClient` with API key injected from env at network boundary. Provider
  errors forwarded as generic HTTP 502/504 — no keys, URLs, or raw content in error
  body. Audit log entry written before HTTP response is flushed.

- [ ] **02-05**: Property tests (Hypothesis) for round-trip correctness and token
  uniqueness.
  - `TEST-01`: Hypothesis generates 1,000+ random inputs; anonymize → restore produces
    byte-for-byte match with original.
  - `TEST-02`: N distinct entity values → exactly N distinct tokens.
  - `TEST-03`: Same value K times → exactly 1 token.
  - `CLASS-TEST-01`: Known-restricted content (source code + financial identifiers
    combined) always produces BLOCK tier; zero bytes forwarded to provider. Verified
    by asserting no outbound HTTPX calls during the test.
  - `CLASS-TEST-02`: ROUTE_LOCAL tier forwards to the configured local endpoint and
    makes no calls to external provider URLs.

---

### Phase 3: SSE Streaming + Multi-Provider

**Goal**: Streaming responses with real-time token restoration via Tail_Buffer state
machine. Multi-provider support for Anthropic, Gemini, and Ollama via Provider_Adapter
translation layer. Streaming correctness proven by Hypothesis tests.

**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: SSE-01 to SSE-08, PROV-02 to PROV-08, CACH-05, TEST-07

**Plan execution order (not parallel)**: `03-02` → `03-01` → `03-03` → `03-04`.
Provider wire formats (03-02) must be fully understood before the Tail_Buffer FSM
(03-01) is built. Anthropic's SSE format
(`data: {"type":"content_block_delta","delta":{"text":"..."}}`) and OpenAI's format
(`data: {"choices":[{"delta":{"content":"..."}}]}`) differ structurally and affect
token boundary detection logic in the FSM. Building the Tail_Buffer before adapters
are finalised means rewriting it.

**Success Criteria**:

1. `stream: true` requests return `text/event-stream` without full-response buffering.
   Tokens are restored in real-time as chunks arrive. Anti-buffering headers
   (`Cache-Control: no-cache`, `X-Accel-Buffering: no`) are present on all streaming
   responses.
2. Tokens split across SSE chunk boundaries are correctly restored via Tail_Buffer.
   Every possible split position produces byte-for-byte match with the non-streamed
   response.
3. Prompts route successfully to Anthropic Claude, Google Gemini, and Ollama via
   model alias. `GET /v1/models` returns all configured aliases with upstream
   provider mappings.
4. Provider errors during streaming return generic error content in-band as a
   terminal SSE event — no keys, URLs, or raw provider content.
5. On client disconnect (browser tab close, network drop, user hits Stop), the
   upstream HTTPX stream is cancelled within one chunk-yield cycle. Valkey mapping is
   deleted. No orphaned provider connections remain after 100 concurrent disconnect
   events under load test.
6. Hypothesis streaming tests pass: all split-token positions produce byte-for-byte
   match with non-streamed response.

**Plans**:

- [ ] **03-02**: Provider adapters — Anthropic, Gemini, and Ollama (execute first,
  before 03-01). Each adapter implements `ProviderAdapter` protocol:
  `translate_request(openai_body) -> dict`, `parse_response(raw) -> dict`,
  `parse_stream_event(sse_line) -> dict`. Registration-based `ADAPTER_REGISTRY`
  with wildcard match for `ollama/*`. Anthropic: translate OpenAI `messages[]` to
  Anthropic `messages[]` + `system` field; handle `tool_use` / `tool_result` blocks.
  Gemini: translate to `contents[]` + `functionDeclarations`; strip empty
  `tool_calls: []` arrays before forwarding to prevent silent content drop (known
  LiteLLM issue). Ollama: OpenAI-compatible passthrough to configurable base URL.
  API key injected from env at network boundary for each provider. Non-streaming
  path fully working and tested before 03-01 begins.

- [ ] **03-01**: SSE streaming route path with Tail_Buffer FSM (execute after 03-02).
  `stream: true` branch in the route handler returns `EventSourceResponse` (not
  `BaseHTTPMiddleware` — it buffers the full body). `HGETALL` mapping pre-fetched
  from Valkey once at stream start and held in memory — never per-chunk cache lookup.
  Tail_Buffer: 512-char rolling buffer, flush after 50 consecutive chunks or 500ms
  (whichever comes first), flush on terminal event. Token matching: case-insensitive,
  bracket-optional (`[NAME_1]` and `NAME_1` at word boundaries both match).
  TTL extension at 80% elapsed (from `CACH-05` built in 02-01).
  Client disconnect handling: poll `await request.is_disconnected()` after each chunk
  yield. On disconnect: cancel upstream HTTPX stream, issue async `DEL` for the
  Valkey mapping, write audit log entry with `session_id`, `bytes_delivered`, and
  `disconnect_reason: client_closed`. Handle `CancelledError` silently within the
  generator — do not propagate to caller.

- [ ] **03-03**: Model alias routing and `GET /v1/models` endpoint. Alias config in
  env or YAML maps `gpt-4o` → OpenAI, `claude-3-5-sonnet` → Anthropic,
  `gemini-1.5-pro` → Gemini, `ollama/llama3` → Ollama. `GET /v1/models` returns all
  configured aliases with provider and upstream model name. Unknown model alias →
  HTTP 400 with list of valid aliases.

- [ ] **03-04**: Streaming property tests (Hypothesis).
  - `TEST-07`: Hypothesis generates random token split positions across all chunk
    boundaries. Every position produces byte-for-byte match with the non-streamed
    response.
  Disconnect load test: 100 concurrent clients connect and immediately disconnect.
  Assert zero orphaned HTTPX connections after 10 seconds (verified via
  `httpx.AsyncClient` connection pool metrics).

---

### Phase 4: Multi-Locale Detection + Compliance Presets

**Goal**: PII detection in 8 locales via `X-AnonReq-Locale` header with
locale-specific regex recognizer bundles and checksum validation for national IDs.
Per-jurisdiction compliance presets enforce mandated entity detection at startup.

**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: LOCL-01 to LOCL-07, COMP-01 to COMP-05

**Success Criteria**:

1. `X-AnonReq-Locale: de-DE` activates German-specific PII detection (Steuer-ID with
   checksum). `fr-FR` detects NIR. `pt-BR` detects CPF and CNPJ. `en`, `nl-NL`,
   `es`, `it-IT`, `ar` each activate their locale bundles.
2. Multiple locales (`X-AnonReq-Locale: de-DE, fr-FR`) produce merged detection
   results (union of entity types).
3. Unsupported or malformed locale header returns HTTP 400 with a descriptive error.
   Missing locale header uses universal recognizers and writes a log entry.
4. Compliance preset (`X-AnonReq-Preset: gdpr`) enforces mandated entity types.
   Startup rejects config that disables preset-mandated types.
5. Audit log entries include `compliance_preset`. Merging multiple active presets
   produces union of entity types with the highest confidence threshold.

**Plans**:

- [ ] **04-01**: Locale recognizer bundles. 8 locale-specific YAML config files, one
  per locale: `en`, `de-DE`, `fr-FR`, `nl-NL`, `es`, `it-IT`, `ar`, `pt-BR`. Each
  file defines regex patterns with confidence scores for locale-specific national IDs,
  phone formats, and address patterns. Checksum validation for: German Steuer-ID,
  Dutch BSN, French NIR, Brazilian CPF and CNPJ, Italian Codice Fiscale. Bundles are
  extensible — adding a new locale requires only a new YAML file, no code change.

- [ ] **04-02**: Locale negotiation. Parse and validate `X-AnonReq-Locale` header.
  Map to recognizer bundle(s). Multi-locale: merge bundles as union of patterns,
  deduplicate overlapping spans by highest confidence. Invalid locale → HTTP 400.
  Missing header → universal recognizers only + log entry `locale: null`. Checksum
  validation runs as a post-detection filter on national ID candidates.

- [ ] **04-03**: Compliance preset engine. Named presets: GDPR, LGPD, PDPA, POPIA,
  Privacy Act (AU), PIPEDA. Each preset defines mandatory entity types and minimum
  confidence thresholds. Startup validation: if active preset mandates `EMAIL` and
  config has `EMAIL` disabled, gateway refuses to start with a clear error. Merged
  preset when multiple active: union of entity types, highest threshold wins per
  type. `GET /v1/compliance/presets` returns all available presets with their entity
  type lists and thresholds. `compliance_preset` field written to every audit log
  entry.

---

### Phase 5: Configuration & Observability

**Goal**: Operational monitoring with Prometheus metrics, P95 latency validation, and
post-restoration token verification to detect any tokens that failed to restore.

**Mode**: mvp
**Depends on**: Phase 3
**Requirements**: METR-01 to METR-03

**Success Criteria**:

1. `GET /metrics` returns Prometheus-formatted counters for: total requests,
   detection latency (ms histogram), entities detected by type, tokens unrestored,
   fail-secure events, and audit log failures.
2. Non-streaming responses are scanned for residual `\[[A-Z]+_\d+\]` patterns
   post-restoration. Any match increments `anonreq_unrestored_tokens_total` and
   writes a warning log entry.
3. Streaming responses are scanned on the fully assembled text after stream
   completion. Residual tokens increment the same counter.
4. Load test passes: P95 processing overhead (time added by AnonReq, excluding LLM
   response time) ≤ 100ms at 50 concurrent users with 1,000-word prompts sustained
   for 60 seconds. If P95 exceeds 100ms, confirm Presidio is using `en_core_web_sm`
   (< 10ms per 1,000 tokens) not `en_core_web_lg` (15–30ms, spike potential > 200ms
   on cold requests). Load test result is logged as a build artifact.

**Plans**:

- [ ] **05-01**: Prometheus metrics endpoint (`/metrics`). Counters:
  `anonreq_requests_total` (labels: provider, model, classification_tier, status),
  `anonreq_entities_detected_total` (label: entity_type),
  `anonreq_unrestored_tokens_total`, `anonreq_fail_secure_events_total`,
  `anonreq_audit_failures_total`. Histograms: `anonreq_detection_latency_ms`,
  `anonreq_total_processing_latency_ms` (gateway overhead only, LLM time excluded).
  Load test with k6 or locust: 50 concurrent users, 1,000-word prompts with mixed
  PII, 60 seconds sustained. Assert P95 of `anonreq_total_processing_latency_ms`
  ≤ 100ms. Document chosen Presidio model in `.env.example` with latency rationale.

- [ ] **05-02**: Post-restoration token verification scan. After restoration on
  non-streaming responses: regex scan `\[[A-Z]+_\d+\]` on full response body.
  After streaming: scan assembled full text. Any match: increment
  `anonreq_unrestored_tokens_total`, write warning log with `session_id` and
  `residual_tokens` list (token names only, not values). Never block delivery on
  verification failure — warn and pass through.

---

### Phase 6: Advanced Property-Based Tests

**Goal**: Complete the generative test suite for edge cases not covered in Phases 2
and 3. Proves fail-secure, no-PII-in-logs, locale checksum, and cross-request
randomization invariants.

**Mode**: mvp
**Depends on**: Phase 4, Phase 5
**Requirements**: TEST-04 to TEST-06, TEST-08

**Success Criteria**:

1. Hypothesis confirms fail-secure invariant: detection failure, cache failure, or
   timeout always produces HTTP 500 with zero bytes forwarded to any provider.
2. Hypothesis confirms no-PII-in-logs: synthetic PII injected across all pipeline
   paths (including exception handler path) produces zero PII substrings in log
   output.
3. Hypothesis confirms cross-request randomization: 1,000+ session pairs where the
   same PII value produces different token strings across sessions, with probability
   ≥ 1 − 2⁻³².
4. Locale checksum tests: invalid checksum national IDs (Steuer-ID, BSN, NIR, CPF,
   CNPJ, Codice Fiscale) are not flagged as valid detections.

**Plans**:

- [ ] **06-01**: Fail-secure and no-PII-in-logs property tests.
  - `TEST-04`: Inject failures at detection engine (Presidio timeout), cache (Valkey
    down), and request timeout. Assert HTTP 500, zero forwarded bytes, and
    `anonreq_fail_secure_events_total` incremented.
  - `TEST-06`: Hypothesis generates random PII values; injects them into all pipeline
    paths including the exception handler path. Scans all log output. Asserts zero
    PII substring matches.

- [ ] **06-02**: Cross-request randomization probability test.
  - `TEST-08`: Generate 1,000+ session pairs each containing the same PII value.
    Assert token strings differ across sessions. Verify P(duplicate) ≥ 1 − 2⁻³²
    bound holds. Run with `hypothesis.settings(derandomize=True)` in CI for
    reproducibility.

- [ ] **06-03**: Locale checksum invalidation tests.
  - `TEST-05`: For each locale with checksum-validated national IDs (de-DE, nl-NL,
    fr-FR, pt-BR, it-IT), generate strings that match the pattern but fail the
    checksum. Assert they are not returned as valid detections by the locale bundle.

---

### Phase 7: Developer Experience & Documentation

**Goal**: Open-source ready repository. A developer unfamiliar with AnonReq can
follow the English quickstart and have the gateway processing requests in under 5
minutes.

**Mode**: mvp
**Depends on**: Phase 6
**Requirements**: DOCS-01 to DOCS-05

**Success Criteria**:

1. Developer can follow the English quickstart — `docker-compose up`, set API key,
   run `curl` example — and see a working anonymization round-trip in under 5 minutes.
2. Python, Node.js, and curl SDK examples are copy-paste runnable and demonstrate
   both non-streaming and streaming round-trips.
3. Repository includes Apache 2.0 `LICENSE`, `NOTICE` file with third-party
   attributions (Presidio, Valkey, FastAPI, spaCy), `SECURITY.md` with responsible
   disclosure policy, and `README.md` covering "Why AnonReq", architecture overview,
   quick start, and "License and Commercial Use" sections.
4. `CHANGELOG.md` follows Keep a Changelog format with entries for all seven phases.

**Plans**:

- [ ] **07-01**: Integration quickstarts in EN, DE, FR, ES, PT-BR. Each covers:
  prerequisites, `docker-compose up`, setting `ANONREQ_API_KEY`, first request via
  curl, verifying the audit log, and a troubleshooting section for the three most
  common startup failures (Presidio not healthy, Valkey not healthy, missing API key).

- [ ] **07-02**: SDK examples and README. Python example using `openai` library with
  `base_url` override. Node.js example using `openai` npm package. curl example for
  both non-streaming and streaming. README with architecture diagram (ASCII),
  "Why AnonReq" section contrasting with direct LLM API usage, and "License and
  Commercial Use" section explaining Apache 2.0 terms and the commercial enterprise
  tier roadmap.

- [ ] **07-03**: CHANGELOG, Apache 2.0 LICENSE, NOTICE file, and SECURITY.md.
  CHANGELOG entries for all phases in Keep a Changelog format. NOTICE lists all
  third-party dependencies with their licenses. SECURITY.md describes the
  responsible disclosure process, expected response SLA (48 hours acknowledgement,
  90 days to patch), and contact method.

---

## Progress

**Execution order**: 1 → 2 → 3 → 4 → 5 → 6 → 7
**Within Phase 3**: plans execute in order 03-02 → 03-01 → 03-03 → 03-04
**All other phases**: plans within a phase may execute in parallel where independent

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 1. Foundation & Fail-Secure | 0/5 | Not started | — |
| 2. Core Pipeline & Classification | 0/5 | Not started | — |
| 3. SSE Streaming + Multi-Provider | 0/4 | Not started | — |
| 4. Multi-Locale Detection + Compliance Presets | 0/3 | Not started | — |
| 5. Configuration & Observability | 0/2 | Not started | — |
| 6. Advanced Property-Based Tests | 0/3 | Not started | — |
| 7. Developer Experience & Documentation | 0/3 | Not started | — |
| **Total** | **0/25** | | |

---

*Last updated: 2026-06-19 — full rewrite incorporating all review findings*