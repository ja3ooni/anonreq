# Phase 2: Core Pipeline & Classification (Non-Streaming) - Research

**Researched:** 2026-06-20
**Domain:** Python 3.12+ FastAPI — ProcessingContext pipeline, 4-tier classification engine, hybrid regex+NER PII detection via Presidio Analyzer sidecar, tokenization with `[TYPE_N]` deduplication, restoration engine, Valkey session-scoped mapping store
**Confidence:** HIGH

## Summary

Phase 2 delivers the full non-streaming anonymization pipeline — the core of AnonReq. A request enters `POST /v1/chat/completions`, is classified into one of 4 tiers (BLOCK / ROUTE_LOCAL / ANONYMIZE / PASS), then for ANONYMIZE requests: all text nodes are extracted via recursive JSON walker, PII is detected via regex (deterministic identifiers) and Presidio Analyzer NER (fuzzy entities), spans are arbitrated with regex winning on overlap, detected values are replaced with `[TYPE_N]` tokens with deduplication and session-scoped random seed offsets, the sanitized request is forwarded to OpenAI (native schema passthrough), the response tokens are restored to original values, the mapping is deleted from Valkey, and the audit log is emitted.

**Primary recommendation:** Implement as 5 sequential plans: (02-01) Valkey cache manager with connection pool, persistence-disabled, TTL, async DEL, health check, monitoring lockdown; (02-02) Classification engine with YAML rules + text extraction + regex/NER detection with span arbitration; (02-03) Tokenization engine with `[TYPE_N]` deduplication, reverse-offset replacement, random seed offsets; (02-04) Pipeline orchestration combining all stages with ForwardingGuard, OpenAI passthrough, and restoration; (02-05) Property-based tests for round-trip correctness, token uniqueness, deduplication, and BLOCK invariant.

**Architecture pattern:** The pipeline is a sequential stage chain operating on a shared `ProcessingContext` data class. Stages are: ClassificationStage → DetectionStage → TokenizationStage → ForwardingGuard → ProviderStage → RestorationStage → CleanupStage. Any stage failure aborts the pipeline and returns HTTP 5xx (never forwards unsanitized data).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Classification Rule Format
- **D-22:** YAML DSL with stable rule IDs, `enabled`, `version`, action, metadata block, conditions
- **D-23:** Conditions are ANDed within a rule: `roles` (list of message roles), `regex` (patterns), `keywords` (case-insensitive word matches)
- **D-24:** Action-based precedence: BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS. No numeric priority field
- **D-25:** No `entity_types` in classification rules — classification runs before Presidio detection
- **D-26:** No expression language (OR/NOT/nested) in MVP
- **D-27:** Classification results record `matched_rule_ids` and `matched_rule_versions` for auditability
- **D-28:** `default_action: PASS` — unaffected requests pass through

#### Text Traversal & Scanning
- **D-29:** Recursive JSON walker with configurable text-path allowlist — `TextExtractor → TextNode(path, value)`
- **D-30:** Not a fixed hardcoded field list; not every string leaf scanned indiscriminately
- **D-31:** `TextNode(path, value)` model reused across classification, detection, tokenization, restoration

#### Presidio Integration
- **D-32:** One Analyzer request per TextNode, executed concurrently via `asyncio.gather()`
- **D-33:** Detection interface accepts `list[TextNode]` — future phases can switch to batch inference behind same `DetectionProvider` contract
- **D-34:** Skip Presidio for TextNodes < 20 characters — regex only
- **D-35:** spaCy model: `en_core_web_md` (medium — balance of accuracy, latency, container footprint)
- **D-36:** Configurable recognizer registry loaded from YAML. Two tiers:
  - Tier 1 (default enabled): EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, IBAN_CODE, IP_ADDRESS, URL, PERSON, ORGANIZATION, LOCATION, DATE_TIME
  - Tier 2 (configurable): SWIFT_CODE, CRYPTO, US_SSN, UK_NHS, PASSPORT, DRIVER_LICENSE, NATIONAL_ID, CUSTOM_ENTERPRISE_PATTERNS
- **D-37:** Detection confidence threshold configurable per-entity, default 0.70
- **D-38:** Regex for deterministic identifiers (email, phone, IBAN, API keys, credentials). Presidio NER for fuzzy entities (PERSON, ORG, LOCATION, ADDRESS)

#### Regex + NER Merge (Span Arbitration)
- **D-39:** Run both independently, then merge via overlap resolution
- **D-40:** Exact span overlap → regex wins. Nested overlap → most specific entity type wins. Partial overlap → preserve most semantically useful span. Non-overlapping → both kept
- **D-41:** Entity specificity ranking: API_KEY > EMAIL > PHONE > CREDIT_CARD > IBAN > SSN > PERSON > LOCATION > ORG

#### Session ID & Request ID
- **D-42:** Gateway generates UUIDv7 for every request context
- **D-43:** UUIDv7 is the mapping-store key owner. Propagated through all pipeline stages and logging
- **D-44:** `X-AnonReq-Request-ID` header exposed for support/debugging/audit correlation

#### Pipeline Orchestration
- **D-45:** `ProcessingContext`-based stage registry. Sequential stages, internal concurrency within stages
- **D-46:** `ProcessingContext` contains: request_id, tenant_id, context_id (UUIDv7), original_request, text_nodes, classification_result, detections, token_mappings, transformed_request, provider_response, restored_response, audit_metadata
- **D-47:** Stage order: Classification → Detection → Tokenization → ForwardingGuard → Provider → Restoration → Cleanup
- **D-48:** ForwardingGuard runs immediately before ProviderStage. ProviderStage is unreachable unless Classification, Detection, Tokenization, and Mapping commit complete
- **D-49:** Any stage failure aborts pipeline immediately. No downstream stage executes. No outbound call

#### Fail-Secure (Presidio-specific)
- **D-50:** Classification failure → BLOCK (500). Presidio timeout (default 2s) → BLOCK (503). Presidio unavailable → BLOCK (503). Presidio malformed response → BLOCK (500). Detection merge failure → BLOCK (500). Tokenization failure → BLOCK (500). Valkey mapping failure → BLOCK (500)
- **D-51:** Circuit breaker opens after N Presidio failures
- **D-52:** Health endpoint exposes Presidio dependency status

#### Property-Test Invariants
- **D-53:** 10 required invariants must pass under Hypothesis before Phase 2 closes (TEST-01 through TEST-10)

#### From Phase 1 (carried forward)
- D-01 to D-21 from Phase 1 CONTEXT.md apply fully

### the agent's Discretion
*(None specified — all decisions above are locked)*

### Deferred Ideas (OUT OF SCOPE)
- Entity-based classification conditions — possible when detection runs before classification (not MVP)
- Expression language (OR/NOT) — deferred post-MVP
- Client-controlled session IDs — deferred post-MVP
- Batch Presidio inference — deferred to future phase if profiling shows bottleneck
- Streaming-specific invariants — deferred to Phase 3
- Cross-request token randomization (TEST-08) — deferred to Phase 5/6
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-01 | Gateway exposes POST /v1/chat/completions accepting OpenAI-compatible payload | Standard FastAPI route with Pydantic request/response models matching OpenAI schema; pass-through for non-ANONYMIZE actions |
| PIPE-02 | Detection_Engine scans all text across all message roles | TextExtractor recursively walks all message blocks; TextNode(path, value) captures role-qualified text paths |
| PIPE-03 | Tokenization_Engine replaces detected entities with [TYPE_N] tokens | Reverse-offset replacement prevents position drift; deduplication via session-scoped token_value→token map |
| PIPE-04 | Restoration_Engine replaces tokens with original values in LLM responses | Token→value lookup from Valkey HGETALL or in-memory copy; regex scan for [TYPE_N] patterns in response |
| PIPE-05 | Cache_Manager deletes Mapping within 100ms of response delivery | async DEL after response; TTL fallback (default 300s); atomic HSET+EXPIRE via pipeline |
| FAIL-01 | Any error returns HTTP 5xx, never forwards unsanitized data | ForwardingGuard before ProviderStage; stage-level error propagation through ProcessingContext errors list |
| FAIL-02 | Detection_Engine/Cache_Manager health probes gate all requests | Health endpoint pings Presidio /health and Valkey PING; pre-flight startup checks |
| DET-01 | Regex recognizer tier for structured PII | Pre-compiled regex patterns for email, phone, CC (Luhn), IBAN, IP, URL, DOB, national IDs, SWIFT, crypto |
| DET-02 | NER recognizer tier for unstructured PII | Presidio Analyzer POST /analyze per TextNode with en_core_web_md; PERSON, ORG, LOCATION, DATE_TIME |
| DET-03 | Regex-NER overlap resolution (regex wins) | Span arbitration algorithm: exact overlap→regex, nested→most specific, partial→preserve best semantic span |
| DET-04 | Configurable Confidence_Threshold (0.0–1.0, default 0.7) per entity type | Per-entity thresholds passed in Presidio request; regex results always have score=1.0 |
| DET-05 | Exclusion_List support with exact match and wildcard matching | Exclusion list loaded from YAML; match logic checks exact strings and glob patterns before span arbitration |
| TOKN-01 | Token format [TYPE_N] with uppercase TYPE (1–20 chars) and positive integer N | Regex: `\[[A-Z][A-Z_]{0,19}_\d+\]`; token generation with session-scoped counter per entity type |
| TOKN-02 | Same entity value → same Token across all occurrences (deduplication) | Session-scoped `value→token` dict checked before new token generation |
| TOKN-03 | Different entity values of same type → distinct Tokens with different indices | Per-type atomic counter in ProcessingContext ensures monotonic N |
| TOKN-04 | Reverse character-offset replacement to prevent position drift | Sort spans descending by start position before replacement; earlier replacements don't shift later spans |
| TOKN-05 | Token index offsets derived from cryptographically random seed per session | `secrets.randbits(32)` generates session seed; token index N = seed_offset + counter |
| TOKN-06 | No entities → no Mapping created, request forwarded unchanged | Check if detections list is empty; skip TokenizationStage and Valkey write entirely |
| TOKN-07 | No entities → request forwarded unchanged, no Mapping created | Same as TOKN-06 (forward unchanged, no write to Valkey) |
| CACH-01 | Valkey/Redis with persistence disabled | `valkey-server --save "" --appendonly no` in Docker Compose command |
| CACH-02 | TTL range 60–3600s (default 300s), allkeys-lru eviction | EXPIRE set after HSET; configurable via Settings.TTL_SECONDS; Valkey started with `--maxmemory-policy allkeys-lru` |
| CACH-03 | Monitoring commands (MONITOR, SLOWLOG) disabled | Valkey `rename-command` config: rename-command MONITOR "" and rename-command SLOWLOG "" |
| CACH-04 | Async DEL post-response, TTL as fallback | await redis.delete(key) after response; TTL ensures cleanup even if DEL fails |
| CACH-06 | Health check verifies persistence disabled, reachability, read/write | Health endpoint: CONFIG GET save validates persistence disabled; SET+GET+DEL round-trip verifies read/write |
| PROV-01 | OpenAI-compatible providers — native schema passthrough | Send sanitized dict directly to upstream OpenAI-compatible endpoint; no translation needed for Phase 2 |
| CLASS-AC-01 | Classification runs before Presidio is called | Stage order in pipeline; ClassificationStage runs first |
| CLASS-AC-02 | YAML-configurable rule actions at startup | Rules loaded from config/classification.yaml at app startup |
| CLASS-AC-03 | 4-tier classification: PASS/ANONYMIZE/ROUTE_LOCAL/BLOCK | Rule actions enum; BLOCK returns HTTP 403 with audit entry; ROUTE_LOCAL forwards to configured on-prem endpoint |
| CLASS-AC-04 | BLOCK rules return HTTP 403 with audit entry | ClassificationStage returns 403 immediately for BLOCK actions; audit entry written to log |
| CLASS-AC-05 | No data forwarded when detection/cache unhealthy | ForwardingGuard checks health before ProviderStage; returns 503 if prerequisite fails |
| AUDT-04 | Fail-secure event log entries (timestamp, session_id, failure_type, http_status) | Audit log includes structured fail-secure entries when pipeline aborts |
| AUDT-05 | Log entry written before HTTP response flushed | Audit write completes synchronously before response return; structlog configured for immediate flush |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Text extraction (JSON walker) | API / Backend | — | Pure in-process transformation; no I/O; operates on already-validated Pydantic model |
| Classification engine | API / Backend | — | YAML rules evaluated in-process; no external calls; pure logic |
| Regex PII detection | API / Backend | — | Pre-compiled regex patterns run in-process; deterministic, sub-millisecond |
| NER PII detection (Presidio) | API / Backend | Database / Storage | HTTP POST to Presidio sidecar per TextNode; sidecar runs spaCy model |
| Span arbitration | API / Backend | — | Pure in-process merge logic; no I/O after detection results received |
| Tokenization engine | API / Backend | — | Pure transformation: spans → [TYPE_N] tokens; in-memory dedup |
| Token mapping store | Database / Storage | — | Valkey HASH mapping store; dedicated container |
| ForwardingGuard | API / Backend | — | Verifies pipeline prerequisites before outbound call |
| Provider adapter (OpenAI) | API / Backend | — | Schema passthrough + API key injection in gateway process |
| Restoration engine | API / Backend | — | Token→value replacement in response; in-process |
| Cache cleanup | Database / Storage | API / Backend | async DEL post-response; TTL fallback on Valkey |
| Audit logging | API / Backend | — | structlog writes structured JSON to stdout from gateway process |
| Circuit breaker (Presidio) | API / Backend | — | In-process failure counter; blocks Presidio calls after N failures |
| Health endpoint | API / Backend | CDN / Static | `/health` checks Valkey PING + Presidio /health + internal state |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | >=0.115.0 | Web framework / pipeline orchestrator | Industry standard for async Python APIs; Pydantic v2 integration; dependency injection [CITED: fastapi.tiangolo.com] |
| pydantic-settings | >=2.14.2 | Runtime configuration | Env var + YAML config loading [CITED: docs.pydantic.dev] |
| redis (async) | >=8.0.0 | Valkey/Redis async client | Official client; async HGETALL/HSET/EXPIRE/DEL; connection pool with health check [VERIFIED: PyPI registry] |
| httpx | >=0.28.1 | Async HTTP client for Presidio + LLM calls | Native async; connection pooling; timeout support [CITED: python-httpx.org] |
| structlog | >=26.1.0 | Structured audit logging | Processor pipeline; contextvars binding; field allowlist [CITED: structlog.org] |
| pyyaml | >=6.0.3 | YAML loading for rules + recognizers | Standard YAML library; SafeLoader prevents code injection [CITED: pyyaml.org] |

### Detection
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| presidio-analyzer | 2.2.359 | NER PII detection engine (in sidecar container) | Docker sidecar; REST API at `ANONREQ_PRESIDIO_URL/analyze` [VERIFIED: PyPI registry] |
| en_core_web_md | — | spaCy medium model for Presidio NER | Balanced accuracy/speed; loaded inside Presidio container, not gateway [ASSUMED] |
| luhn (or custom) | — | Luhn checksum validation for credit cards | `luhn` package or inline function; 5 lines of Python [ASSUMED] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyyaml | >=6.0.3 | YAML rule loading | All YAML config: classification rules, custom recognizers, exclusion lists |
| uuid (stdlib) | — | UUIDv7 generation for session_id | `uuid.uuid7()` available in Python 3.14+; for 3.12 use `uuid.uuid4().hex` (simplest — token randomness from `secrets.randbits(32)`) or `uuid-backport` (backport of stdlib, PSF license) |
| secrets (stdlib) | — | Cryptographically random seed for token offsets | `secrets.randbits(32)` for per-session entropy |
| re (stdlib) | — | Regex patterns for deterministic PII | Pre-compiled patterns module for all Tier 1 regex recognizers |

### Testing
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=9.0 | Test framework | All unit + integration tests |
| pytest-asyncio | >=1.4.0 | Async test support | Pipeline stage tests require async context |
| hypothesis | >=6.155.6 | Property-based testing | Round-trip correctness, token uniqueness, deduplication invariants [VERIFIED: PyPI registry] |
| respx | >=0.21.0 | HTTP mocking for Presidio | Mock httpx requests to Presidio sidecar without running container |
| fakeredis | >=2.0 | In-memory Valkey mock | Fast unit tests for cache operations without Valkey container |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI route as pipeline orchestrator | ASGI middleware for pipeline | Route handler gives direct access to parsed Pydantic models; middleware requires hacking ASGI `receive` |
| redis-py async | valkey-py | redis-py 8.0+ supports RESP3 and Valkey protocol; larger ecosystem, more docs |
| respx for mock HTTP | responses library | respx is designed for httpx (which FastAPI uses natively); responses is for requests library |
| fakeredis for unit tests | testcontainers[redis] | fakeredis is in-process, fast (~1ms per test); testcontainers requires Docker (~5s per test) — use fakeredis for unit tests, testcontainers for integration |

**Additional installation for Phase 2:**
```bash
pip install httpx pyyaml respx fakeredis
```

**Version verification:**
```bash
python3 -m pip index versions presidio-analyzer  # 2.2.359
python3 -m pip index versions redis              # 8.0.0
python3 -m pip index versions hypothesis         # 6.155.6
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| presidio-analyzer | PyPI | ~7 yrs | >5M total | github.com/microsoft/presidio | OK | Approved — official Microsoft package |
| redis | PyPI | ~15 yrs | >200M total | github.com/redis/redis-py | OK | Approved — official Redis client |
| httpx | PyPI | ~6 yrs | >100M total | github.com/encode/httpx | OK | Approved — official HTTP client |
| hypothesis | PyPI | ~12 yrs | >50M total | github.com/HypothesisWorks/hypothesis | OK | Approved — official Hypothesis project |
| structlog | PyPI | ~10 yrs | >50M total | github.com/hynek/structlog | OK | Approved — established library |
| pyyaml | PyPI | ~19 yrs | >1B total | github.com/yaml/pyyaml | OK | Approved — standard YAML library |
| respx | PyPI | ~5 yrs | >5M total | github.com/lundberg/respx | OK | Approved — httpx mocking standard |
| fakeredis | PyPI | ~8 yrs | >5M total | github.com/cunla/fakeredis-py | OK | Approved — well-known Redis mock |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none — all packages are well-established with verified source repos and high download counts.

**Note on Presidio:** The `presidio-analyzer` package is the Python library used *inside* the sidecar container. The gateway never imports presidio-analyzer — it communicates via HTTP. The Docker Compose sidecar uses `mcr.microsoft.com/presidio-analyzer:latest`. No additional pip install needed in the gateway for Presidio.

## Architecture Patterns

### System Architecture Diagram

```
                                    ┌─────────────────────────────────────────┐
                                    │           FastAPI Gateway               │
                                    │  POST /v1/chat/completions              │
                                    │                                         │
Client ──HTTP──► ┌─────────────────┐  ProcessingContext flows through stages: │
                 │ Auth Middleware  │  ┌─────────────────────────────────────┐│
                 │ (Phase 1)       │  │ ProcessingContext                   ││
                 └────────┬────────┘  │ ├── request_id: UUIDv7              ││
                          ▼           │ ├── tenant_id: str                  ││
                 ┌─────────────────┐  │ ├── original_request: ChatRequest   ││
                 │ Route Handler   │  │ ├── text_nodes: list[TextNode]      ││
                 │ (creates ctx)   │  │ ├── classification: ClassResult     ││
                 └────────┬────────┘  │ ├── detections: list[Detection]     ││
                          ▼           │ ├── token_mappings: dict[str,str]   ││
                 ┌─────────────────┐  │ ├── transformed_request: dict       ││
                 │ PipelineManager │  │ ├── provider_response: dict         ││
                 │ (stage iterator)│  │ ├── restored_response: dict         ││
                 └────────┬────────┘  │ └── errors: list[Exception]         ││
                          ▼           └─────────────────────────────────────┘│
                 ┌─────────────────┐                                         │
          ┌──────┤ 1.Classification│◄── YAML rules (config/classification.. │
          │      └────────┬────────┘                                         │
          │               ▼                                                  │
          │      ┌─────────────────┐          ┌──────────────────────┐       │
          │      │ BLOCK (403)     │───exit───│ Audit: blocked_req   │       │
          │      └─────────────────┘          └──────────────────────┘       │
          │               ▼                                                  │
          │      ┌─────────────────┐                                         │
          │      │ 2a. Regex       │── in-process, deterministic             │
          │      │    Detection    │                                         │
          │      └────────┬────────┘                                         │
          │               ▼                                                  │
          │      ┌─────────────────┐  HTTP POST /analyze       ┌──────────┐ │
          │      │ 2b. Presidio    ├───────────────────────────►│ Presidio │ │
          │      │    NER Detection│◄───── RecognizerResult[]──│ Analyzer │ │
          │      └────────┬────────┘                           └──────────┘ │
          │               ▼                                                  │
          │      ┌─────────────────┐                                         │
          │      │ 3. Span         │── regex wins on overlap                 │
          │      │    Arbitration  │── specificity ranking                   │
          │      └────────┬────────┘                                         │
          │               ▼                                                  │
          │      ┌─────────────────┐                                         │
          │      │ 4. Tokenization │── [TYPE_N], dedup, reverse-offset      │
          │      └────────┬────────┘                                         │
          │               ▼                                                  │
          │      ┌─────────────────┐  HSET + EXPIRE            ┌──────────┐ │
          │      │ 5. Valkey Cache │───────────────────────────►│ Valkey   │ │
          │      │    Write        │◄────── OK                  └──────────┘ │
          │      └────────┬────────┘                                         │
          │               ▼                                                  │
          │      ┌─────────────────┐                                         │
          │      │ 6. Forwarding   │── verifies prerequisites                │
          │      │    Guard        │── 503 on failure                        │
          │      └────────┬────────┘                                         │
          │               ▼                                                  │
          │      ┌─────────────────┐  POST /v1/chat/completions  ┌──────────┐│
          │      │ 7. OpenAI       ├─────────────────────────────►│ OpenAI   ││
          │      │    Provider     │◄──── response dict          └──────────┘│
          │      └────────┬────────┘                                         │
          │               ▼                                                  │
          │      ┌─────────────────┐                                         │
          │      │ 8. Restoration  │── token→value replacement               │
          │      │    Engine       │── regex scan for [TYPE_N]                │
          │      └────────┬────────┘                                         │
          │               ▼                                                  │
          │      ┌─────────────────┐                                         │
          │      │ 9. Cleanup      │── async DEL, audit log                  │
          │      └────────┬────────┘                                         │
          │               ▼                                                  │
          │      ┌─────────────────┐                                         │
          │      │ 10. Verification│── scan for residual [TYPE_N]            │
          │      └────────┬────────┘                                         │
          │               ▼                                                  │
          │      ┌─────────────────┐                                         │
          └──────┤ Response to     │── 200/403/503 with audit               │
                 │ Client          │                                         │
                 └─────────────────┘                                         │
                                                                             │
                 ┌─────────────────┐  /health             ┌──────────┐      │
                 │ Health Endpoint ├──────────────────────►│ Presidio │      │
                 │ (Phase 1)       │◄─────────────────────│ Valkey   │      │
                 └─────────────────┘                      └──────────┘      │
                                    └─────────────────────────────────────────┘
```

### Recommended Project Structure
```
src/anonreq/
├── __init__.py
├── __about__.py
├── main.py                  # FastAPI app creation, lifespan, route mounting
├── config.py                # Pydantic Settings + YAML config loader
├── exceptions.py            # Custom exception classes + global handlers
├── dependencies.py          # FastAPI dependencies (auth, request context)
├── logging_config.py        # structlog configuration
├── health.py                # /health endpoint
├── models/
│   ├── __init__.py
│   ├── request_context.py   # RequestContext data class
│   ├── chat.py              # Pydantic models for OpenAI chat schema
│   ├── classification.py    # ClassificationRule, ClassResult models
│   ├── detection.py         # Detection, TextNode, RecognizerResult models
│   ├── tokenization.py      # TokenMapping, TokenResult models
│   └── processing_context.py# ProcessingContext data class
├── pipeline/
│   ├── __init__.py
│   ├── manager.py           # PipelineManager — stage registry + iteration
│   ├── base.py              # PipelineStage abstract base
│   ├── classification.py    # ClassificationStage
│   ├── extraction.py        # TextExtractor — recursive JSON walker
│   ├── detection.py         # DetectionStage — regex + Presidio + arbitration
│   ├── tokenization.py      # TokenizationStage
│   ├── forwarding_guard.py  # ForwardingGuard
│   ├── provider.py          # ProviderStage (OpenAI passthrough)
│   ├── restoration.py       # RestorationStage
│   └── cleanup.py           # CleanupStage (Valkey DEL + audit)
├── detection/
│   ├── __init__.py
│   ├── regex_patterns.py    # Pre-compiled regex patterns for all types
│   ├── regex_detector.py    # RegexDetector — runs patterns on text
│   ├── presidio_client.py   # PresidioClient — HTTP calls to sidecar
│   ├── span_arbiter.py      # SpanArbiter — regex+NER merge logic
│   └── exclusion_list.py    # ExclusionList — exact+wildcard matching
├── tokenization/
│   ├── __init__.py
│   ├── tokenizer.py         # Tokenizer — [TYPE_N] generation
│   └── restorer.py          # Restorer — token→value replacement
├── cache/
│   ├── __init__.py
│   ├── manager.py           # CacheManager — Valkey connection pool
│   └── health.py            # Cache health check logic
├── classification/
│   ├── __init__.py
│   ├── engine.py            # ClassificationEngine — rule evaluation
│   └── loader.py            # RuleLoader — YAML loading + validation
└── routing/
    ├── __init__.py
    └── chat.py               # POST /v1/chat/completions route handler

tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_classification.py   # Rule engine tests
├── test_detection.py        # Regex + Presidio client tests
├── test_span_arbiter.py     # Overlap resolution tests
├── test_tokenization.py     # Token generation + dedup tests
├── test_restoration.py      # Restoration engine tests
├── test_pipeline.py         # Pipeline integration tests
├── test_cache.py            # Valkey cache manager tests
├── test_text_extractor.py   # Text extraction tests
├── test_presidio_client.py  # Presidio HTTP client tests
└── conftest_detection.py    # Detection fixtures (responses mocks)
```

### Pattern 1: ProcessingContext Stage Pipeline

**What:** A sequential pipeline where each stage receives and mutates a shared `ProcessingContext` data class. Stages are registered in order; the PipelineManager iterates through them. Any stage that detects an error sets `ctx.errors` and the pipeline aborts.

**When to use:** Whenever you need a sequence of processing steps that share state, with clear error boundaries between steps. This is the core architectural pattern for AnonReq (D-45 through D-49).

**Example:**
```python
# src/anonreq/pipeline/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

@dataclass
class ProcessingContext:
    request_id: str
    tenant_id: str = "default"
    context_id: UUID | None = None          # UUIDv7 — mapping key owner
    original_request: dict | None = None    # Parsed ChatRequest
    text_nodes: list[dict] | None = None    # [{"path": "...", "value": "..."}]
    classification_result: dict | None = None
    detections: list[dict] | None = None    # [{"start": N, "end": N, "entity_type": "...", "score": F}]
    token_mappings: dict[str, str] | None = None  # {"[EMAIL_0]": "user@example.com"}
    transformed_request: dict | None = None       # Sanitized request body
    provider_response: dict | None = None          # Raw LLM response
    restored_response: dict | None = None          # Response with tokens restored
    audit_metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[Exception] = field(default_factory=list)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def fail_secure(self, error: Exception) -> None:
        """Record error and abort pipeline."""
        self.errors.append(error)


class PipelineStage(ABC):
    """Base class for all pipeline stages."""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    async def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        ...


# src/anonreq/pipeline/manager.py
class PipelineManager:
    """Iterates stages sequentially; aborts on first error."""
    
    def __init__(self):
        self._stages: list[PipelineStage] = []
    
    def register(self, stage: PipelineStage) -> None:
        self._stages.append(stage)
    
    async def run(self, ctx: ProcessingContext) -> ProcessingContext:
        for stage in self._stages:
            if ctx.has_errors():
                break
            logger.info("pipeline.stage.start", stage=stage.name, request_id=ctx.request_id)
            ctx = await stage.execute(ctx)
            if ctx.has_errors():
                logger.error("pipeline.stage.failed", stage=stage.name, 
                             request_id=ctx.request_id, error=str(ctx.errors[-1]))
                break
            logger.info("pipeline.stage.complete", stage=stage.name, request_id=ctx.request_id)
        return ctx
```
[ASSUMED: Based on architectural decisions D-45 through D-49 from CONTEXT.md]

### Pattern 2: Presidio Analyzer REST API Client

**What:** Async HTTP client that calls the Presidio Analyzer sidecar `POST /analyze` endpoint. One request per TextNode, executed concurrently via `asyncio.gather()`.

**When to use:** When sending text to Presidio for NER-based PII detection. The Presidio sidecar runs as a separate Docker container (not in-process) — the gateway never imports `presidio_analyzer` directly.

**Example:**
```python
# src/anonreq/detection/presidio_client.py
import httpx
from typing import Any

class PresidioClient:
    """Async HTTP client for Presidio Analyzer sidecar."""
    
    def __init__(self, base_url: str, timeout: float = 2.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
    
    async def analyze(
        self,
        text: str,
        language: str = "en",
        entities: list[str] | None = None,
        score_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Send text to Presidio Analyzer for NER detection.
        
        Presidio REST API: POST /analyze
        Request body:
        {
            "text": "John Smith lives in New York",
            "language": "en",
            "entities": ["PERSON", "LOCATION"],
            "score_threshold": 0.7
        }
        
        Response body:
        [
            {"entity_type": "PERSON", "start": 0, "end": 10, "score": 0.85},
            {"entity_type": "LOCATION", "start": 20, "end": 28, "score": 0.95}
        ]
        """
        body: dict[str, Any] = {
            "text": text,
            "language": language,
            "score_threshold": score_threshold,
        }
        if entities:
            body["entities"] = entities
        
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/analyze",
                    json=body,
                )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                raise PresidioTimeoutError()
            except httpx.HTTPStatusError as e:
                raise PresidioError(f"Presidio returned {e.response.status_code}")
```

**Presidio `POST /analyze` API Reference:**
- **Endpoint:** `POST /analyze`
- **Request fields:** `text` (string, required), `language` (string, required), `entities` (string[], optional — filter), `score_threshold` (float, optional — default 0), `return_decision_process` (bool, optional), `ad_hoc_recognizers` (PatternRecognizer[], optional), `context` (string[], optional), `allow_list` (string[], optional)
- **Response:** `RecognizerResult[]` — each with `entity_type` (string), `start` (int), `end` (int), `score` (float), `analysis_explanation` (object, null unless `return_decision_process: true`)
- **Batch mode:** Pass `text` as `string[]` for batch analysis
- **Error responses:** 400 on malformed JSON, 422 on invalid input, 500 on internal error

[VERIFIED: microsoft.github.io/presidio/analyzer/ and github.com/microsoft/presidio/blob/main/docs/api-docs/api-docs.yml]

### Pattern 3: Span Arbitration for Regex + NER Overlap

**What:** Runs regex detection and Presidio NER independently, then merges results via overlap resolution rules. Regex wins on exact overlap. Nested overlaps favor most specific entity type. Non-overlapping spans are both kept.

**When to use:** Whenever both deterministic regex patterns and fuzzy NER are used for detection. This is the core merge strategy for D-39 through D-41.

**Example:**
```python
# src/anonreq/detection/span_arbiter.py
from typing import Any

# Specificity ranking from D-41 (higher = more specific)
ENTITY_SPECIFICITY = {
    "API_KEY": 100,
    "EMAIL_ADDRESS": 90,
    "PHONE_NUMBER": 80,
    "CREDIT_CARD": 75,
    "IBAN_CODE": 70,
    "US_SSN": 65,
    "PERSON": 40,
    "LOCATION": 30,
    "ORGANIZATION": 25,
}

class SpanArbiter:
    """Merges regex and NER detection results with overlap resolution."""
    
    @staticmethod
    def merge(regex_results: list[dict], ner_results: list[dict]) -> list[dict]:
        """Merge two detection result lists. Regex results always carry score=1.0."""
        
        # Tag each result with its source
        for r in regex_results:
            r["_source"] = "regex"
        for r in ner_results:
            r["_source"] = "ner"
        
        combined = regex_results + ner_results
        # Sort by start position, then by score descending
        combined.sort(key=lambda r: (r["start"], -r["score"]))
        
        merged = []
        for span in combined:
            # Check for overlap with already-accepted spans
            overlapped = False
            for i, accepted in enumerate(merged):
                overlap = SpanArbiter._overlap_type(span, accepted)
                if overlap is None:
                    continue
                overlapped = True
                
                if overlap == "exact":
                    # D-40: Exact overlap → regex wins
                    if span["_source"] == "regex":
                        merged[i] = span
                
                elif overlap == "nested":
                    # D-40: Nested → most specific entity type wins
                    span_spec = ENTITY_SPECIFICITY.get(span.get("entity_type", ""), 0)
                    acc_spec = ENTITY_SPECIFICITY.get(accepted.get("entity_type", ""), 0)
                    if span_spec > acc_spec:
                        merged[i] = span
                
                elif overlap == "partial":
                    # D-40: Partial → preserve most semantically useful span
                    span_spec = ENTITY_SPECIFICITY.get(span.get("entity_type", ""), 0)
                    acc_spec = ENTITY_SPECIFICITY.get(accepted.get("entity_type", ""), 0)
                    if span_spec > acc_spec:
                        merged[i] = span
                break
            
            if not overlapped:
                # D-40: Non-overlapping → both kept
                merged.append(span)
        
        # Remove source tagging before returning
        for r in merged:
            r.pop("_source", None)
        
        return merged
    
    @staticmethod
    def _overlap_type(a: dict, b: dict) -> str | None:
        """Determine overlap type between two spans."""
        a_start, a_end = a["start"], a["end"]
        b_start, b_end = b["start"], b["end"]
        
        # No overlap
        if a_end <= b_start or b_end <= a_start:
            return None
        
        # Exact overlap
        if a_start == b_start and a_end == b_end:
            return "exact"
        
        # Nested (one fully contains the other)
        if (a_start >= b_start and a_end <= b_end) or (b_start >= a_start and b_end <= a_end):
            return "nested"
        
        # Partial overlap
        return "partial"
```
[ASSUMED: Based on D-39 through D-41 from CONTEXT.md]

### Pattern 4: Tokenization with Reverse-Offset Replacement

**What:** Replaces detected entity spans with `[TYPE_N]` tokens. Uses reverse-offset replacement (sorting spans descending by start position) to prevent earlier replacements from shifting later span positions. Deduplication ensures same value → same token.

**When to use:** Always when replacing spans in text — the reverse-offset pattern is essential for correctness (D-04, D-04).

**Example:**
```python
# src/anonreq/tokenization/tokenizer.py
import secrets
import re
from typing import Any

class Tokenizer:
    """Generates [TYPE_N] tokens with deduplication and random seed offsets."""
    
    def __init__(self):
        self._per_type_counters: dict[str, int] = {}
        self._value_to_token: dict[str, str] = {}
        self._seed: int = 0
    
    def initialize_session(self) -> None:
        """Reset per-session state with random seed."""
        self._per_type_counters = {}
        self._value_to_token = {}
        self._seed = secrets.randbits(32)
    
    def tokenize(
        self,
        text: str,
        detections: list[dict[str, Any]],
    ) -> tuple[str, dict[str, str]]:
        """Replace detected spans with [TYPE_N] tokens.
        
        Reverse-offset replacement to prevent position drift.
        Returns (tokenized_text, mapping_dict)
        """
        if not detections:
            return text, {}
        
        # Sort spans descending by start position
        sorted_spans = sorted(detections, key=lambda s: s["start"], reverse=True)
        
        tokenized = text
        mapping: dict[str, str] = {}
        
        for span in sorted_spans:
            entity_type = span["entity_type"]
            original_value = text[span["start"]:span["end"]]
            
            # Dedup: check if we've seen this value before
            token = self._value_to_token.get(original_value)
            if token is None:
                # Generate new token with type counter and random seed
                entity_type_short = entity_type[:20]  # Cap at 20 chars per TOKN-01
                counter = self._per_type_counters.get(entity_type_short, 0)
                # TOKN-05: Token index = seed_offset + counter
                token_index = (self._seed & 0x3FFFFFFF) + counter
                token = f"[{entity_type_short}_{token_index}]"
                self._value_to_token[original_value] = token
                self._per_type_counters[entity_type_short] = counter + 1
                mapping[token] = original_value
            else:
                # TOKN-02: Dedup — same value returns same token
                pass
            
            # Reverse-offset replacement (spans are sorted descending)
            before = tokenized[:span["start"]]
            after = tokenized[span["end"]:]
            tokenized = before + token + after
        
        return tokenized, mapping
```
[ASSUMED: Based on D-41 through D-04, D-02, D-03, D-05 from CONTEXT.md. The seed-based offset approach is extrapolated from TOKN-05.]

### Pattern 5: Restoration Engine

**What:** Scans LLM response text for `[TYPE_N]` token patterns and replaces each with its original value from the mapping. Used for non-streaming responses. Token matching is case-insensitive per D-04.

**When to use:** After receiving a provider response, before returning to the client. For non-streaming, operates on the full response JSON.

**Example:**
```python
# src/anonreq/tokenization/restorer.py
import re
from typing import Any

# Token pattern: [TYPE_N] — uppercase type, positive integer N
TOKEN_PATTERN = re.compile(r'\[([A-Z][A-Z_]{0,19})_(\d+)\]')

class Restorer:
    """Restores tokens to original values in LLM responses."""
    
    @staticmethod
    def restore_text(text: str, mapping: dict[str, str]) -> str:
        """Replace all [TYPE_N] tokens with original values from mapping.
        
        Case-insensitive matching per SSE-04/SSE-05.
        Sorts tokens by length descending to avoid partial collisions
        (e.g., [NAME_10] replaced before [NAME_1]).
        """
        if not mapping or not text:
            return text
        
        # Sort tokens by length descending for safe replacement
        sorted_tokens = sorted(mapping.keys(), key=len, reverse=True)
        
        result = text
        for token in sorted_tokens:
            original = mapping[token]
            # Case-insensitive match (token in text might be [name_1] or [Name_1])
            pattern = re.compile(re.escape(token), re.IGNORECASE)
            result = pattern.sub(original, result)
        
        return result
    
    @staticmethod
    def restore_response(
        response: dict[str, Any],
        mapping: dict[str, str],
    ) -> dict[str, Any]:
        """Restore tokens in a full LLM response dict.
        
        Handles: choices[].message.content, tool_calls arguments,
        and any other string fields that may contain tokens.
        """
        restored = response.copy()
        
        if "choices" in restored:
            for choice in restored["choices"]:
                if "message" in choice:
                    msg = choice["message"]
                    if "content" in msg and isinstance(msg["content"], str):
                        msg["content"] = Restorer.restore_text(msg["content"], mapping)
                    if "tool_calls" in msg:
                        for tc in msg["tool_calls"]:
                            if "function" in tc and "arguments" in tc["function"]:
                                tc["function"]["arguments"] = Restorer.restore_text(
                                    tc["function"]["arguments"], mapping
                                )
        
        return restored
```
[ASSUMED: Based on requirements D-04 and SSE-04/SSE-05 from CONTEXT.md. Full restoration of tool_calls will be expanded in Phase 3/Phase 9.]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| NER-based PII detection | Custom spaCy/transformers pipeline | Presidio Analyzer (Docker sidecar) | Mature, tested, extensible recognizer registry, active Microsoft maintainers. Custom NER would take months to reach comparable accuracy |
| PII regex patterns | Writing all patterns from scratch | Curated community libraries + Presidio built-in | Projects like `piigex`, `llm-pii-redact`, `pii-core` provide tested patterns with checksum validation |
| Luhn checksum for CC | Custom Luhn implementation | `luhn` package or 5-line inline function | Luhn is a simple algorithm — inline function avoids dependency. `pip install luhn` if preferred |
| Async Valkey client | Raw socket RESP protocol | `redis.asyncio` from redis-py | Connection pool management, auto-reconnect, health_check_interval, pipeline support |
| HTTP mocking for Presidio | Custom httpx mock | `respx` | Designed for httpx; request matching, response templates, easy fixture setup |
| In-memory Valkey mock | Fake Redis protocol | `fakeredis` | Full Redis command support in-process; ~1ms per test; no Docker required |
| UUIDv7 generation | Manual timestamp-based UUID | `uuid.uuid7()` (stdlib 3.14) or third-party | Correct implementation of RFC 9562 requires careful timestamp encoding |
| YAML config loading | Custom YAML validator | Pydantic Settings + YAML models | Schema validation, type coercion, error messages built-in |
| Circuit breaker | Custom failure counter | Simple in-process counter (for MVP) | Phase 2 MVP: integer counter with threshold; formal circuit-breaker library overkill at this stage |
| Structured audit logging | Custom JSON formatter | structlog + JSONRenderer | Processor pipeline, contextvars binding, field allowlist, production-tested |

**Key insight:** Every PII detection library (Presidio, piigex, llm-pii-redact) solves the same hard problem: false positive management. Regex patterns for PII are easy to write and hard to get right — they either miss valid formats or flag innocent text. Presidio's confidence scoring + the specificity-ranked arbitration (D-41) is the correct defense-in-depth approach.

## Common Pitfalls

### Pitfall 1: Position Drift from Left-to-Right Replacement
**What goes wrong:** Replacing spans from left to right changes character offsets, causing later replacements to target wrong positions.
**Why it happens:** "John Smith" (span 0-10) replaced with "[PERSON_0]" (9 chars) shifts everything after position 10 by -1. The next span at position 15 is now actually at position 14.
**How to avoid:** Always sort spans descending by start position and replace right-to-left. Example: `sorted(spans, key=lambda s: s["start"], reverse=True)`.
**Warning signs:** Restored text is garbled or has characters inserted in wrong places.

### Pitfall 2: Concurrent Presidio Requests Timing Out
**What goes wrong:** `asyncio.gather()` sends N concurrent requests to Presidio. If the sidecar is overloaded, some requests timeout while others succeed, leaving partial detection results.
**Why it happens:** Presidio has a default timeout. When all TextNodes fire simultaneously, the sidecar's request queue fills up.
**How to avoid:** Use a `Semaphore(N)` to limit concurrent Presidio requests (e.g., N=10). Set `timeout=2.0s` per D-50. If timeout occurs, ALL detections are discarded and the pipeline returns 503 — never forward partially-sanitized data.
**Warning signs:** Intermittent 503 errors under load.

### Pitfall 3: Race Condition Between HSET and EXPIRE
**What goes wrong:** If the gateway crashes between `HSET` and `EXPIRE`, the mapping survives forever without a TTL — defeating the ephemeral guarantee.
**Why it happens:** Two separate Redis commands are not atomic.
**How to avoid:** Use a pipeline/MULTI-EXEC block for atomicity: `pipe.hset(key, mapping=mapping); pipe.expire(key, ttl); await pipe.execute()`. The pipeline sends both commands in one round-trip, and Redis executes them atomically (within MULTI/EXEC) or sequentially (within pipeline without MULTI).
**Warning signs:** Orphaned mappings accumulating in Valkey.

### Pitfall 4: Regex Patterns Overmatching on Innocent Text
**What goes wrong:** A credit card pattern like `\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b` matches product codes, order numbers, or random text that happens to be 16 digits.
**Why it happens:** Regex patterns have no semantic understanding. Credit card patterns without Luhn checks produce 90%+ false positives on general text.
**How to avoid:** Apply Luhn validation to CC candidates before flagging. For IBAN, validate against the country-specific mod-97 checksum (not just the `[A-Z]{2}\d{2}[A-Z0-9]{11,30}` shape). For SSN, exclude invalid area numbers (000, 666, 900-999).
**Warning signs:** Users report that ordinary text is being flagged as PII.

### Pitfall 5: Token Collisions from Poor Random Seed Initialization
**What goes wrong:** Two sessions generate the same token indices, or within a session, two different entity types produce the same token.
**Why it happens:** Token counter reset or seed collision. TOKN-05 requires `cryptographically random seed per session`, but if the seed + counter for ENTITY_A collides with the counter for ENTITY_B, you can get `[ENTITY_A_100]` and `[ENTITY_B_100]` that look identical.
**How to avoid:** Use per-type counters so `[EMAIL_0]` and `[PHONE_0]` never collide. The random seed offset (TOKN-05) applies to the counter value, not the token itself — so `[EMAIL_5]` and `[PHONE_5]` are different tokens because the entity type prefix differs.
**Warning signs:** Token `[EMAIL_42]` maps to both "john@example.com" and "jane@example.org" in the same session.

### Pitfall 6: Presidio Returns Entities That Were Already Handled by Regex
**What goes wrong:** Both regex and Presidio detect the same email address. If both results are passed to tokenization, the email gets tokenized twice, causing position drift and corrupted text.
**Why it happens:** Overlap resolution (D-40) must be applied before tokenization. Regex and Presidio run independently — their outputs must be merged by SpanArbiter first.
**How to avoid:** Always run SpanArbiter.merge(regex_results, ner_results) before passing detections to the Tokenizer. Never skip the merge step.
**Warning signs:** Email addresses appearing as `[EMAIL_0]` in the restored response (not restored) or double-tokenized text.

## Code Examples

### Example 1: TextExtractor — Recursive JSON Walker

```python
# src/anonreq/pipeline/extraction.py
from typing import Any

# Text paths to scan in OpenAI chat request
TEXT_PATHS = [
    "messages[].content",
    "messages[].tool_calls[].function.arguments",
]

class TextExtractor:
    """Recursive JSON walker that extracts text values from configured paths.
    
    Produces TextNode(path, value) tuples reusable across
    classification, detection, tokenization, and restoration.
    """
    
    @staticmethod
    def extract(body: dict[str, Any]) -> list[dict[str, Any]]:
        """Flatten all text-bearing fields into TextNode list."""
        text_nodes: list[dict[str, Any]] = []
        
        messages = body.get("messages", [])
        for msg_idx, message in enumerate(messages):
            role = message.get("role", "unknown")
            content = message.get("content", "")
            
            if isinstance(content, str) and content.strip():
                text_nodes.append({
                    "path": f"messages[{msg_idx}].content",
                    "role": role,
                    "value": content,
                })
            
            # Tool calls
            for tc_idx, tool_call in enumerate(message.get("tool_calls", [])):
                func_args = tool_call.get("function", {}).get("arguments", "")
                if isinstance(func_args, str) and func_args.strip():
                    text_nodes.append({
                        "path": f"messages[{msg_idx}].tool_calls[{tc_idx}].function.arguments",
                        "role": role,
                        "value": func_args,
                    })
        
        return text_nodes
```
[ASSUMED: Based on D-29 through D-31]

### Example 2: Regex PII Detection Patterns

```python
# src/anonreq/detection/regex_patterns.py
import re
from typing import Any

# Compiled regex patterns for deterministic PII detection
# Tier 1 — always enabled per D-36

PATTERNS: dict[str, re.Pattern] = {
    "EMAIL_ADDRESS": re.compile(
        r"\b[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,255}\.[A-Za-z]{2,24}\b"
    ),
    "PHONE_NUMBER": re.compile(
        r"(?<!\d)(?:\+?\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}(?!\d)"
    ),
    "CREDIT_CARD": re.compile(
        r"\b(?:\d[ \t\-]?){13,19}\d\b"
    ),
    "IBAN_CODE": re.compile(
        r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"
    ),
    "IP_ADDRESS": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
    ),
    "URL": re.compile(
        r"\bhttps?://[A-Za-z0-9.\-]{1,255}\.[A-Za-z]{2,24}[^\s]*\b"
    ),
    "US_SSN": re.compile(
        r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"
    ),
}


def luhn_checksum(card_number: str) -> bool:
    """Luhn algorithm check for credit card numbers."""
    digits = [int(d) for d in card_number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


class RegexDetector:
    """Runs pre-compiled regex patterns on text and returns detections."""
    
    def __init__(self, patterns: dict[str, re.Pattern] | None = None):
        self._patterns = patterns or PATTERNS
    
    def detect(self, text: str) -> list[dict[str, Any]]:
        """Run all patterns on text, return list of detections.
        
        CREDIT_CARD results are Luhn-validated before returning.
        """
        results = []
        for entity_type, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                value = match.group()
                
                # Luhn validation for credit cards
                if entity_type == "CREDIT_CARD":
                    if not luhn_checksum(value):
                        continue
                
                results.append({
                    "entity_type": entity_type,
                    "start": match.start(),
                    "end": match.end(),
                    "score": 1.0,  # Regex matches are deterministic
                    "source": "regex",
                })
        
        return results
```
[ASSUMED: Based on community patterns from multiple open-source projects. Luhn validation is standard practice for CC detection. Entity types per D-36.]

### Example 3: OpenAI Chat Request/Response Schema (Passthrough)

```python
# src/anonreq/models/chat.py
from pydantic import BaseModel, Field
from typing import Any, Literal

# OpenAI-compatible request schema (PIPE-01)
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool", "function"]
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    n: int | None = 1
    stop: str | list[str] | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    logit_bias: dict[str, float] | None = None
    user: str | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    seed: int | None = None

# OpenAI-compatible response schema (non-streaming)
class ChatCompletionChoice(BaseModel):
    index: int
    message: dict[str, Any]
    finish_reason: str | None = None

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: dict[str, int] | None = None
```
[ASSUMED: Based on OpenAI API reference at platform.openai.com/docs/api-reference/chat. The schema is intentionally simplified for MVP — additional fields (logprobs, functions, etc.) can be added as needed.]

### Example 4: Valkey Cache Manager

```python
# src/anonreq/cache/manager.py
import redis.asyncio as redis
from typing import Any

class CacheManager:
    """Async Valkey manager — HASH-based token mapping store.
    
    Key format: anonreq:{tenant_id}:{session_id}
    Fields: token → original_value
    Atomic HSET + EXPIRE via pipeline (D-14).
    """
    
    def __init__(self, redis_url: str, ttl: int = 300):
        self._redis = redis.from_url(
            redis_url,
            decode_responses=True,
            health_check_interval=5,
        )
        self._ttl = ttl
    
    def _key(self, tenant_id: str, session_id: str) -> str:
        return f"anonreq:{tenant_id}:{session_id}"
    
    async def store_mapping(
        self,
        tenant_id: str,
        session_id: str,
        mapping: dict[str, str],
    ) -> None:
        """Atomic HSET + EXPIRE via pipeline per D-14."""
        key = self._key(tenant_id, session_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            await (pipe
                .hset(key, mapping=mapping)
                .expire(key, self._ttl)
                .execute()
            )
    
    async def get_mapping(
        self,
        tenant_id: str,
        session_id: str,
    ) -> dict[str, str]:
        """HGETALL — returns all token→value pairs for session (D-15)."""
        key = self._key(tenant_id, session_id)
        return await self._redis.hgetall(key)
    
    async def delete_mapping(
        self,
        tenant_id: str,
        session_id: str,
    ) -> None:
        """Async DEL post-response (CACH-04). TTL is the fallback."""
        key = self._key(tenant_id, session_id)
        await self._redis.delete(key)
    
    async def health_check(self) -> dict[str, Any]:
        """Verify Valkey is reachable and persistence-disabled (CACH-06)."""
        try:
            ping = await self._redis.ping()
            config_save = await self._redis.config_get("save")
            persistence_disabled = config_save.get("save", "") == ""
            return {
                "reachable": ping,
                "persistence_disabled": persistence_disabled,
                "healthy": ping and persistence_disabled,
            }
        except Exception as e:
            return {"reachable": False, "persistence_disabled": False, 
                    "healthy": False, "error": str(e)}
    
    async def close(self) -> None:
        await self._redis.aclose()
```
[ASSUMED: Based on D-13 through D-15 and CACH-01 through CACH-06. Uses redis-py 8.0 async API with pipeline transactions.]

### Example 5: Classification Engine

```python
# src/anonreq/classification/engine.py
from typing import Any
import re
import yaml
from pathlib import Path

class ClassificationRule:
    """Single classification rule loaded from YAML."""
    
    def __init__(self, data: dict):
        self.id: str = data["id"]
        self.enabled: bool = data.get("enabled", True)
        self.version: int = data.get("version", 1)
        self.name: str = data.get("name", "")
        self.action: str = data["action"]  # BLOCK, ROUTE_LOCAL, ANONYMIZE, PASS
        self.metadata: dict = data.get("metadata", {})
        conditions = data.get("conditions", {})
        self.roles: list[str] = conditions.get("roles", [])
        self.regex_patterns: list[str] = conditions.get("regex", [])
        self.keywords: list[str] = conditions.get("keywords", [])
        
        # Pre-compile regex patterns
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.regex_patterns]
        # Case-insensitive keyword matching
        self._keywords_lower = [k.lower() for k in self.keywords]

    def matches(self, text_nodes: list[dict[str, Any]]) -> bool:
        """Check if this rule matches any text node.
        All conditions ANDed (D-23): roles, regex, keywords must ALL match.
        """
        for node in text_nodes:
            # Check roles filter
            if self.roles and node.get("role") not in self.roles:
                continue
            
            value = node.get("value", "")
            if not value:
                continue
            
            # Check regex
            if self._compiled and not any(p.search(value) for p in self._compiled):
                continue
            
            # Check keywords
            value_lower = value.lower()
            if self._keywords_lower and not any(kw in value_lower for kw in self._keywords_lower):
                continue
            
            # All conditions passed (AND logic)
            return True
        
        return False


class ClassificationEngine:
    """Evaluates YAML rules against text nodes.
    
    Action precedence per D-24: BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS
    """
    
    ACTION_ORDER = ["BLOCK", "ROUTE_LOCAL", "ANONYMIZE", "PASS"]
    
    def __init__(self, rules: list[ClassificationRule], default_action: str = "PASS"):
        self._enabled_rules = [r for r in rules if r.enabled]
        self._default_action = default_action
    
    @classmethod
    def from_yaml(cls, path: str | Path, default_action: str = "PASS") -> "ClassificationEngine":
        with open(path) as f:
            data = yaml.safe_load(f)
        rules = [ClassificationRule(r) for r in data.get("rules", [])]
        return cls(rules, default_action)
    
    def classify(self, text_nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """Evaluate rules in action-priority order. Returns first match.
        
        Returns:
        {
            "action": "BLOCK" | "ROUTE_LOCAL" | "ANONYMIZE" | "PASS",
            "matched_rule_ids": [...],
            "matched_rule_versions": [...],
        }
        """
        matched_ids = []
        matched_versions = []
        
        for action in self.ACTION_ORDER:
            for rule in self._enabled_rules:
                if rule.action == action and rule.matches(text_nodes):
                    matched_ids.append(rule.id)
                    matched_versions.append(rule.version)
                    return {
                        "action": action,
                        "matched_rule_ids": matched_ids,
                        "matched_rule_versions": matched_versions,
                    }
        
        return {
            "action": self._default_action,
            "matched_rule_ids": [],
            "matched_rule_versions": [],
        }
```
[ASSUMED: Based on D-22 through D-28. YAML classification rules loaded at startup.]

### Example 6: Pipeline Route Handler

```python
# src/anonreq/routing/chat.py
from fastapi import APIRouter, Depends, HTTPException
from anonreq.models.chat import ChatRequest, ChatCompletionResponse
from anonreq.models.processing_context import ProcessingContext
from anonreq.pipeline.manager import PipelineManager
from anonreq.pipeline.classification import ClassificationStage
from anonreq.pipeline.extraction import TextExtractor
from anonreq.pipeline.detection import DetectionStage
from anonreq.pipeline.tokenization import TokenizationStage
from anonreq.pipeline.forwarding_guard import ForwardingGuard
from anonreq.pipeline.provider import ProviderStage
from anonreq.pipeline.restoration import RestorationStage
from anonreq.pipeline.cleanup import CleanupStage
from uuid import uuid7

router = APIRouter()

def build_pipeline() -> PipelineManager:
    """Build the standard non-streaming pipeline."""
    pm = PipelineManager()
    pm.register(ClassificationStage())
    pm.register(DetectionStage())
    pm.register(TokenizationStage())
    pm.register(ForwardingGuard())
    pm.register(ProviderStage())
    pm.register(RestorationStage())
    pm.register(CleanupStage())
    return pm

pipeline = build_pipeline()

@router.post("/v1/chat/completions")
async def chat_completions(body: ChatRequest):
    """Main entry point for non-streaming LLM requests."""
    
    # Create processing context from request
    ctx = ProcessingContext(
        request_id=f"req_{uuid7().hex[:24]}",
        original_request=body.model_dump(),
    )
    
    # Extract text nodes
    ctx.text_nodes = TextExtractor.extract(ctx.original_request)
    
    # Run pipeline
    ctx = await pipeline.run(ctx)
    
    # Handle errors
    if ctx.has_errors():
        error = ctx.errors[-1]
        if isinstance(error, PipelineAbortError):
            raise HTTPException(status_code=error.status_code, detail=str(error))
        raise HTTPException(status_code=500, detail="Internal gateway error")
    
    # Handle classification actions
    action = ctx.classification_result.get("action")
    if action == "BLOCK":
        raise HTTPException(status_code=403, detail="Request blocked by policy")
    elif action == "ROUTE_LOCAL":
        # Forward to configured on-prem endpoint (future)
        raise HTTPException(status_code=501, detail="ROUTE_LOCAL not yet implemented")
    elif action == "PASS":
        # Forward unchanged — no detection or tokenization needed
        return ctx.provider_response
    elif action == "ANONYMIZE":
        return ctx.restored_response
```
[ASSUMED: Based on D-45 through D-49 stage ordering. This is the orchestrator that ties all stages together.]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Presidio Analyzer v2.0 | Presidio Analyzer v2.2+ | Ongoing | Improved performance, better Docker support, ad_hoc_recognizers API |
| redis-py sync client | redis-py async client (8.0+) | redis-py 4.0 (2021) | Async client core to FastAPI integration; pipeline transactions |
| python-json-logger | structlog built-in JSONRenderer | structlog 23.0+ | structlog's built-in renderer is sufficient; no extra dependency |
| FastAPI on_event("startup") | FastAPI lifespan context manager | FastAPI 0.89 (Dec 2022) | Lifespan is the correct pattern for startup + shutdown lifecycle |
| spaCy en_core_web_lg | en_core_web_md | Ongoing | Medium model is 2.5× faster than large with only ~2% accuracy loss for NER |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Presidio Analyzer Docker sidecar exposes POST /analyze at port 5001 | Architecture Patterns | The Docker Compose health check and presidio_client URL need verification against the actual container |
| A2 | `uuid.uuid4().hex` is sufficient for session_id (no uuid7 needed) | Standard Stack | **[RESOLVED]** — uuid7 not available in 3.12; uuid4 hex is sufficient since token entropy comes from secrets.randbits(32). If ordered keys needed, use `uuid-backport` backport package. |
| A3 | `redis-py` 8.0 async pipeline transactions work with Valkey 8 RESP3 | Code Examples | **[RESOLVED]** — redis-py 8.0 RESP3 preserves RESP2-compatible shapes; pipeline MULTI/EXEC behavior identical across protocols; `protocol=2` fallback available. |
| A4 | Presidio's POST /analyze accepts `entities` filter field | Standard Stack | **[RESOLVED]** — confirmed via Presidio API docs; `GET /health` also verified as reliable (used in Docker HEALTHCHECK). |
| A5 | regex patterns from community libraries (PATTERNS dict) are accurate for MVP | Code Examples | False positive/negative rates not tested for this project's domain. Tune during Phase 4/6 |
| A6 | `fakeredis` supports async and pipeline transactions | Standard Stack | fakeredis 2.x may not fully replicate Valkey behavior for edge cases |
| A7 | OpenAI chat completions response schema is stable as documented | Code Examples | OpenAI occasionally adds fields; the Pydantic model needs ongoing maintenance |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions

1. ~~**uuid7 availability in Python 3.12**~~ **[RESOLVED]**
   - Resolution: Python 3.12 does NOT have `uuid.uuid7()` (it's 3.14+). Two backport options exist on PyPI: `uuid-backport` v0.1.2 (PSF-licensed backport of stdlib) and `uuid7-standard` v1.1.0 (production/stable). However, simplest MVP approach: `uuid.uuid4().hex` — token generation randomness comes from `secrets.randbits(32)`, not from the session_id format. [VERIFIED: PyPI registry for uuid-backport, uuid7-standard]

2. ~~**Presidio Docker container health endpoint**~~ **[RESOLVED]**
   - Resolution: `GET /health` on the Presidio Analyzer reliably returns `200 text/plain` with `"Presidio Analyzer service is up"`. Confirmed via Presidio API docs and the official Dockerfile, which uses `curl -f http://localhost:${PORT}/health` as the Docker HEALTHCHECK itself — the same endpoint Phase 2 would use. [VERIFIED: github.com/microsoft/presidio Dockerfile]

3. ~~**Valkey RESP3 compatibility with redis-py 8.0**~~ **[RESOLVED]**
   - Resolution: redis-py 8.0 uses RESP3 by default but preserves RESP2-compatible Python response shapes for backward compatibility. Valkey 8 supports both RESP2 and RESP3. Pipeline transaction behavior (MULTI/EXEC) is identical across protocols. `protocol=2` can force RESP2 if needed; Valkey's own client fork (`valkey-py`) uses the same pipeline semantics. [VERIFIED: github.com/redis/redis-py v8.0.0 release notes, valkey.io/topics/migration/]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Runtime container | ✓ (Docker) | 3.12-slim | Docker build uses `python:3.12-slim` |
| Docker | Containerization | ✓ | 29.5.3 | — |
| Docker Compose | Orchestration | ✓ | v5.1.4 | — |
| curl | Healthcheck probes | ✓ | 8.7.1 | — |
| redis-py 8.0 | PyPI | ✓ | 8.0.0 | Install via pip |
| httpx | PyPI | ✓ | (latest) | Install via pip |
| presidio-analyzer | Docker sidecar | ✓ | 2.2.359 | `mcr.microsoft.com/presidio-analyzer:latest` |
| valkey/valkey:8 | Docker image | ✓ | 8.x | `valkey/valkey:8` on Docker Hub |

**Missing dependencies with no fallback:** none
**Missing dependencies with fallback:** none

## Validation Architecture

> `workflow.nyquist_validation` is enabled (true) in config.json.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 + hypothesis 6.155.6 |
| Config file | `pyproject.toml` under `[tool.pytest.ini_options]` |
| Quick run command | `pytest -x --tb=short` |
| Full suite command | `pytest --cov=anonreq --cov-report=term-missing` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-01 | Regex patterns correctly detect structured PII | unit | `pytest tests/test_detection.py::test_regex_patterns -x` | ❌ Wave 0 |
| DET-02 | Presidio client sends correct HTTP request and parses response | unit | `pytest tests/test_presidio_client.py -x` | ❌ Wave 0 |
| DET-03 | SpanArbiter correctly resolves regex/NER overlaps | unit | `pytest tests/test_span_arbiter.py -x` | ❌ Wave 0 |
| DET-04 | Confidence threshold filtering works per entity type | unit | `pytest tests/test_detection.py::test_confidence_threshold -x` | ❌ Wave 0 |
| DET-05 | Exclusion list suppresses matching detections | unit | `pytest tests/test_detection.py::test_exclusion_list -x` | ❌ Wave 0 |
| TOKN-01 to TOKN-05 | Token format, dedup, reverse-offset, random seed | unit | `pytest tests/test_tokenization.py -x` | ❌ Wave 0 |
| TOKN-06/07 | No-entities path bypasses tokenization and mapping | unit | `pytest tests/test_tokenization.py::test_no_entities -x` | ❌ Wave 0 |
| CLASS-AC-01 to CLASS-AC-05 | Classification engine evaluates rules correctly | unit | `pytest tests/test_classification.py -x` | ❌ Wave 0 |
| PIPE-01 | OpenAI-compatible route accepts valid requests | integration | `pytest tests/test_pipeline.py::test_route_openai_compat -x` | ❌ Wave 0 |
| PIPE-02 | All message roles scanned for text | unit | `pytest tests/test_text_extractor.py -x` | ❌ Wave 0 |
| PIPE-03/04 | Round-trip correctness (byte-for-byte) | property | `pytest tests/ -k "test_roundtrip" --hypothesis-max-examples=1000 -x` | ❌ Wave 0 |
| FAIL-01 | Pipeline stage failure returns 5xx, never forwards | property | `pytest tests/ -k "test_fail_secure" -x` | ❌ Wave 0 |
| CACH-01 to CACH-04 | Valkey persistence disabled, TTL set, DEL post-response | unit | `pytest tests/test_cache.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest -x --tb=short tests/test_<module>.py`
- **Per wave merge:** `pytest --cov=anonreq --cov-report=term-missing`
- **Phase gate:** Full suite + Hypothesis property tests green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_classification.py` — covers CLASS-AC-01 to CLASS-AC-05
- [ ] `tests/test_detection.py` — covers DET-01, DET-04, DET-05
- [ ] `tests/test_span_arbiter.py` — covers DET-03 overlap resolution
- [ ] `tests/test_presidio_client.py` — covers Presidio HTTP client (with respx)
- [ ] `tests/test_tokenization.py` — covers TOKN-01 through TOKN-07
- [ ] `tests/test_restoration.py` — covers PIPE-04 restoration
- [ ] `tests/test_text_extractor.py` — covers PIPE-02 text extraction
- [ ] `tests/test_cache.py` — covers CACH-01 through CACH-06
- [ ] `tests/test_pipeline.py` — covers PIPE-01, pipeline orchestration
- [ ] `tests/test_roundtrip.py` — Hypothesis property tests (TEST-01, TEST-02, TEST-03)
- [ ] `tests/conftest.py` — shared fixtures (respx mock for Presidio, fakeredis, text samples)
- [ ] Framework install: `pip install pytest pytest-asyncio hypothesis respx fakeredis`

## Security Domain

> `security_enforcement` is enabled (true) in config.json.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Static bearer token from Phase 1 on all routes |
| V3 Session Management | yes | UUIDv7 session_id; mapping TTL-managed; no persistent sessions |
| V4 Access Control | yes | Classification rules enforce BLOCK action; ForwardingGuard gate |
| V5 Input Validation | yes | Pydantic v2 validation on ChatRequest; YAML safe_load for rules |
| V6 Cryptography | partial | `secrets.randbits(32)` for token seed; no encryption in Phase 2 |
| V7 Error Handling | yes | Fail-secure pipeline; any error → 5xx, never forward |
| V8 Data Protection | yes | No PII in logs; mapping stored ephemerally in Valkey with TTL |
| V9 Communications | partial | Docker internal network; Presidio/Valkey on internal bridge |
| V11 Business Logic | yes | ForwardingGuard ensures prerequisites met before provider call |
| V13 API & Web Services | yes | OpenAI-compatible schema; structured error responses |
| V14 Configuration | yes | YAML rules loaded at startup; env var config via Pydantic Settings |

### Known Threat Patterns for Pipeline Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Detection bypass (PII not detected) | Tampering | Hybrid regex+NER with independent arbitration; confidence threshold configurable |
| Mapping corruption in Valkey | Tampering | Atomic HSET+EXPIRE via pipeline; single-key-per-session isolation |
| Timing attack on token seed | Information Disclosure | secrets.randbits(32) from cryptographically secure RNG |
| Denial of service via slow Presidio | Denial of Service | 2s timeout per request; circuit breaker after N failures |
| Replay attack using Request-ID | Spoofing | Request-ID is internal tracing only; not used for auth |
| Presidio sidecar compromised | Elevation of Privilege | Sidecar on internal Docker network only; no external ports exposed |
| YAML rule injection | Injection | `yaml.safe_load()` prevents arbitrary code execution |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: PyPI registry] Package versions confirmed via `python3 -m pip index versions`
- [VERIFIED: microsoft.github.io/presidio/analyzer/] Presidio Analyzer REST API documentation
- [VERIFIED: github.com/microsoft/presidio] Presidio API spec for POST /analyze request/response
- [VERIFIED: redis.io/docs] redis-py async documentation
- [VERIFIED: developers.openai.com] OpenAI Chat Completions API reference

### Secondary (MEDIUM confidence)
- [CITED: microsoft.github.io/presidio/analyzer/] Presidio Analyzer architecture
- [CITED: redis.readthedocs.io] redis-py 8.0 async commands
- [CITED: platform.claude.com/docs] Anthropic Messages API documentation
- [CITED: ai.google.dev/gemini-api/docs] Gemini API documentation
- [CITED: fastapi.tiangolo.com] FastAPI exception handlers, lifespan, dependency injection

### Tertiary (LOW confidence)
- [ASSUMED] regex patterns from community sources (PATTERNS dict) need tuning
- [ASSUMED] fakeredis fully supports redis-py async pipeline transactions
- ~~[ASSUMED] Presidio Docker health endpoint — **[UPGRADED to VERIFIED]**~~
- ~~[ASSUMED] uuid7 availability — **[UPGRADED to VERIFIED]**~~

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified on PyPI; libraries well-documented; uuid7 fallback resolved
- Architecture: HIGH — confirmed via architectural guardrails, CONTEXT.md decisions, and multiple sources
- Detection patterns: MEDIUM — regex patterns require tuning for production; Presidio API verified with health endpoint confirmed
- Pipeline design: HIGH — based on D-45 through D-49 decisions; ProcessingContext pattern documented
- Package audit: HIGH — all packages verified with source repos and download stats; uuid-backport identified as fallback

**Research date:** 2026-06-20
**Valid until:** 2026-07-20 (30-day validity — Presidio API and Python ecosystem stable)
