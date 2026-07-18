# Architecture

**Analysis Date:** 2026-07-18

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                          Client Application                          │
│              (OpenAI-compatible chat completions request)             │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Middleware Stack                              │
│  IngressMTLS → MetricsMiddleware → ClassificationMiddleware          │
│  → PolicyMiddleware → ClassificationResponseMiddleware               │
│  → ContentTypeMiddleware → set_request_context (request_id)          │
│  → auth_context (Bearer token validation)                            │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    POST /v1/chat/completions                          │
│                     (routing/chat.py)                                 │
├───────────────────────────┬──────────────────────────────────────────┤
│   Non-streaming path       │    Streaming path                       │
│   (PipelineManager.run)    │    (pre_provider + adapter.stream_events)│
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Anonymization Pipeline                            │
│                  (pipeline/manager.py — sequential)                   │
├─────────────────────────────────────────────────────────────────────┤
│ ClassificationStage → LocaleNegotiationStage → DetectionStage       │
│ → SensitivityClassificationStage → PolicyEnforcementStage           │
│ → InboundDLPStage → ToolGovernanceStage → TokenizationStage         │
│ → ForwardingGuard → ProviderStage → OutboundDLPStage                │
│ → RestorationStage → CleanupStage                                    │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
┌─────────────────────┐   ┌──────────────────────────────────┐
│   Provider Adapter   │   │       Cache Manager (Valkey)      │
│  (OpenAI/Anthropic/  │   │   anonreq:{tenant_id}:{session}  │
│   Gemini/Ollama)     │   │   Token → original_value mapping  │
└─────────────────────┘   └──────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Application Factory | Wires middleware, routes, lifespan, exception handlers | `src/anonreq/main.py` |
| PipelineManager | Sequential stage executor with fail-secure abort | `src/anonreq/pipeline/manager.py` |
| PipelineStage (ABC) | Interface for all pipeline stages | `src/anonreq/pipeline/base.py` |
| ProcessingContext | Shared state object flowing through all stages | `src/anonreq/models/processing_context.py` |
| TextExtractor | Recursive JSON walker extracting text nodes from OpenAI payloads | `src/anonreq/pipeline/extraction.py` |
| ClassificationStage | Rule-based action determination (BLOCK/PASS/ANONYMIZE/ROUTE_LOCAL) | `src/anonreq/pipeline/classification.py` |
| LocaleNegotiationStage | Resolves locale header and prepares merged recognizer config | `src/anonreq/pipeline/stages.py` |
| DetectionStage | Hybrid regex + Presidio NER + MNPI + enterprise detection | `src/anonreq/pipeline/detection.py` |
| RegexDetector | Deterministic pattern matching with Luhn checksum validation | `src/anonreq/detection/regex_detector.py` |
| PresidioClient | Async HTTP client for Presidio Analyzer sidecar (NER detection) | `src/anonreq/detection/presidio_client.py` |
| SpanArbiter | Merges regex + NER results with overlap resolution (regex wins exact) | `src/anonreq/detection/span_arbiter.py` |
| ExclusionList | Exact-match and wildcard false-positive suppression | `src/anonreq/detection/exclusion_list.py` |
| ContextBooster | Confidence boosting for financial crime entities near high-risk words | `src/anonreq/detection/boost.py` |
| SensitivityClassificationStage | Post-detection sensitivity-level classification (Phase 12) | `src/anonreq/pipeline/stages.py` |
| PolicyEnforcementStage | PDP/PEP policy enforcement integration into pipeline | `src/anonreq/pipeline/stages.py` |
| InboundDLPStage | Pre-forwarding DLP inspection of request text | `src/anonreq/pipeline/dlp.py` |
| ToolGovernanceStage | Agent/tool call permission policy evaluation | `src/anonreq/pipeline/tool_governance.py` |
| TokenizationStage | Replaces PII spans with `[TYPE_N]` tokens, stores mapping in Valkey | `src/anonreq/pipeline/tokenization.py` |
| Tokenizer | Core token generator with deduplication and random seed offsets | `src/anonreq/tokenization/tokenizer.py` |
| ForwardingGuard | Fail-secure gate verifying all prerequisites before provider call | `src/anonreq/pipeline/forwarding_guard.py` |
| ProviderStage | Async HTTP passthrough to OpenAI-compatible upstream | `src/anonreq/pipeline/provider.py` |
| OutboundDLPStage | Post-response DLP inspection before client delivery | `src/anonreq/pipeline/dlp.py` |
| RestorationStage | Replaces `[TYPE_N]` tokens with original values in provider response | `src/anonreq/pipeline/restoration.py` |
| Restorer | Case-insensitive token→value replacement (brackets optional) | `src/anonreq/tokenization/restorer.py` |
| RestoreEngine | Path-aware token restoration with PathTracker integration | `src/anonreq/restore/engine.py` |
| PathTracker | Records JSON paths where each token appeared | `src/anonreq/restore/path_tracker.py` |
| CleanupStage | Deletes Valkey mapping and writes structured audit log | `src/anonreq/pipeline/cleanup.py` |
| AliasRegistry | YAML-backed model alias → provider/model resolution | `src/anonreq/routing/alias_registry.py` |
| ProviderRegistry | YAML-based adapter resolution with lazy import | `src/anonreq/providers/registry.py` |
| ProviderAdapter (ABC) | Abstract base for provider-specific schema translation | `src/anonreq/providers/adapter.py` |
| OpenAIAdapter | OpenAI Chat Completions API adapter | `src/anonreq/providers/openai.py` |
| AnthropicAdapter | OpenAI→Anthropic Messages API translation | `src/anonreq/providers/anthropic.py` |
| GeminiAdapter | OpenAI→Google Gemini translation | `src/anonreq/providers/gemini.py` |
| OllamaAdapter | OpenAI→Ollama local inference translation | `src/anonreq/providers/ollama.py` |
| CacheManager | Async Valkey-backed token mapping store with retry | `src/anonreq/cache/manager.py` |
| TailBuffer | Streaming FSM for safe partial-token reassembly | `src/anonreq/streaming/tail_buffer.py` |
| StreamingRestorationStage | In-stream token restoration for assembled chunks | `src/anonreq/streaming/restoration.py` |
| SSEEmitter | Server-Sent Event formatting for streaming responses | `src/anonreq/streaming/emitter.py` |
| SessionCleanup | Post-stream cleanup and audit logging | `src/anonreq/streaming/cleanup.py` |
| PolicyDecisionPoint (PDP) | Evaluates classification, rate, spend, residency policies | `src/anonreq/policy/pdp.py` |
| PolicyEnforcementPoint (PEP) | Enforces PDP decisions (ALLOW/BLOCK/FLAG_AND_FORWARD/ROUTE_LOCAL) | `src/anonreq/policy/pep.py` |
| PolicyStore | Policy rule persistence and retrieval | `src/anonreq/policy/store.py` |
| UsageLimiter | Rate limiting per tenant | `src/anonreq/policy/usage_limiter.py` |
| SpendController | Cost/spend budget enforcement per tenant | `src/anonreq/policy/spend_controller.py` |
| ResidencyRouter | Data residency/routing policy enforcement | `src/anonreq/policy/residency_router.py` |
| ClassificationMiddleware | Parses X-AnonReq-Classification header, blocks HIGHLY_RESTRICTED | `src/anonreq/middleware/classification.py` |
| PolicyMiddleware | Pre-route PDP/PEP evaluation on chat-completion routes | `src/anonreq/middleware/policy.py` |
| MetricsMiddleware | Request timing and Prometheus counter increment | `src/anonreq/monitoring/middleware.py` |
| IngressMTLSMiddleware | Forwarded mTLS client certificate validation | `src/anonreq/middleware/mtls.py` |
| ContentTypeMiddleware | Content-Type enforcement for multimodal requests | `src/anonreq/middleware/content_type.py` |
| AppState | Typed container for all lifespan-managed services | `src/anonreq/state.py` |
| Settings | Pydantic Settings loaded from ANONREQ_* env vars | `src/anonreq/config/__init__.py` |
| AnonReqError hierarchy | Exception types + global fail-secure exception handlers | `src/anonreq/exceptions.py` |
| Bootstrap services | Lifespan startup wiring for all enterprise subsystems | `src/anonreq/bootstrap/services.py` |

## Pattern Overview

**Overall:** Staged Pipeline with Fail-Secure Abort

**Key Characteristics:**
- Sequential pipeline execution via `PipelineManager` — each stage reads from and writes to a shared `ProcessingContext`
- **Fail-secure by default:** any stage failure appends to `ctx.errors`, and `has_errors()` prevents all downstream stages (especially the provider call) from executing
- **Session-scoped ephemeral token mappings** stored in Valkey with TTL, deleted after response
- **OpenAI-compatible wire protocol** maintained at the edge; provider adapters translate internally
- **Hybrid detection engine** combining deterministic regex patterns with Presidio NER, merged via span arbitration (regex wins on exact overlap)
- **Middleware stack** ordered for request_id → auth → metrics → classification → policy → content-type

## Layers

**Middleware Layer:**
- Purpose: Cross-cutting concerns executed before route handlers (auth, metrics, classification, policy enforcement, content-type, mTLS)
- Location: `src/anonreq/middleware/`, `src/anonreq/monitoring/middleware.py`
- Contains: ASGI middleware classes and FastAPI dependency injection
- Depends on: `app.state` (AppState), structlog contextvars
- Used by: FastAPI app in `main.py`

**Routing Layer:**
- Purpose: HTTP route handlers that create `ProcessingContext` and invoke the pipeline
- Location: `src/anonreq/routing/chat.py`, `src/anonreq/routes/`
- Contains: FastAPI `APIRouter` instances, pipeline construction helpers
- Depends on: Pipeline layer, CacheManager, AppState, auth dependency
- Used by: FastAPI app (registered in `main.py`)

**Pipeline Layer:**
- Purpose: Staged orchestration of the anonymization flow
- Location: `src/anonreq/pipeline/`
- Contains: `PipelineStage` implementations, `PipelineManager`, `TextExtractor`
- Depends on: Detection, Tokenization, Restore, Providers, Cache, Policy layers
- Used by: Routing layer

**Detection Layer:**
- Purpose: PII/entity detection via regex patterns, Presidio NER, MNPI recognizers, enterprise recognizers, and context boosting
- Location: `src/anonreq/detection/`
- Contains: `RegexDetector`, `PresidioClient`, `SpanArbiter`, `ExclusionList`, `ContextBooster`, locale recognizers
- Depends on: Locale bundles, Presidio sidecar HTTP API
- Used by: DetectionStage in pipeline

**Tokenization Layer:**
- Purpose: Replace detected PII spans with `[TYPE_N]` tokens; restore tokens in responses
- Location: `src/anonreq/tokenization/`, `src/anonreq/restore/`
- Contains: `Tokenizer`, `Restorer`, `RestoreEngine`, `PathTracker`
- Depends on: Detection results, CacheManager for mapping storage
- Used by: TokenizationStage, RestorationStage in pipeline

**Streaming Layer:**
- Purpose: Handle SSE streaming with safe partial-token reassembly and in-stream restoration
- Location: `src/anonreq/streaming/`
- Contains: `TailBuffer` FSM, `StreamingRestorationStage`, `SSEEmitter`, `SessionCleanup`
- Depends on: CacheManager (for mapping retrieval), token pattern regex
- Used by: `_stream_chat_completions()` in routing/chat.py

**Provider Adapter Layer:**
- Purpose: Translate OpenAI-compatible requests to provider-specific formats and normalize responses back
- Location: `src/anonreq/providers/`
- Contains: `ProviderAdapter` ABC, `OpenAIAdapter`, `AnthropicAdapter`, `GeminiAdapter`, `OllamaAdapter`, `ProviderRegistry`
- Depends on: `ProcessingContext`, httpx for HTTP calls, `resolve_api_key()` for secrets
- Used by: ProviderStage (legacy), streaming path via `adapter.stream_events()`

**Routing & Alias Layer:**
- Purpose: Map client-visible model names to provider/model pairs
- Location: `src/anonreq/routing/`
- Contains: `AliasRegistry`, `ModelAlias`
- Depends on: YAML config (`config/model_aliases.yaml`), `ProviderRegistry`
- Used by: ProviderStage, streaming path

**Cache Layer:**
- Purpose: Session-scoped ephemeral token mapping storage in Valkey (Redis-compatible)
- Location: `src/anonreq/cache/`
- Contains: `CacheManager` with standalone/sentinel/cluster topology support
- Depends on: `redis.asyncio` (Valkey), tenacity retry
- Used by: TokenizationStage (store), CleanupStage (delete), StreamingRestorationStage (fetch)

**Policy Layer:**
- Purpose: Enterprise policy decision and enforcement (PDP/PEP pattern)
- Location: `src/anonreq/policy/`
- Contains: `PolicyDecisionPoint`, `PolicyEnforcementPoint`, `PolicyStore`, `UsageLimiter`, `SpendController`, `ResidencyRouter`
- Depends on: `ProcessingContext`, Redis (for rate/spend counters)
- Used by: PolicyMiddleware (pre-route), PolicyEnforcementStage (in-pipeline)

**Enterprise Services Layer:**
- Purpose: Audit, compliance, governance, DLP, breach, SOC, SLO, lifecycle, and other enterprise capabilities
- Location: `src/anonreq/services/`, `src/anonreq/governance/`, `src/anonreq/compliance/`, `src/anonreq/soc/`
- Contains: Service classes bootstrapped during lifespan
- Depends on: AppState, SQLAlchemy, webhooks
- Used by: Bootstrap services, admin routes

**Configuration Layer:**
- Purpose: Application settings from environment variables + YAML files
- Location: `src/anonreq/config/`
- Contains: `Settings` (Pydantic BaseSettings), `RestrictedNamesManager`
- Depends on: `pydantic-settings`, YAML files
- Used by: Every layer

**Exception Layer:**
- Purpose: Fail-secure error handling with OpenAI-compatible error envelopes
- Location: `src/anonreq/exceptions.py`
- Contains: `AnonReqError` hierarchy, global exception handlers
- Used by: Every layer (fail-secure abort pattern)

## Data Flow

### Primary Request Path (Non-Streaming)

1. **Request arrives** → `set_request_context` middleware assigns `request_id` and creates `RequestContext` (`src/anonreq/main.py:365-375`)
2. **Auth validates** → `auth_context` dependency checks Bearer token via constant-time comparison (`src/anonreq/dependencies.py:98-124`)
3. **Route handler** creates `ProcessingContext` and extracts `text_nodes` via `TextExtractor.extract()` (`src/anonreq/routing/chat.py:220-238`)
4. **PipelineManager.run()** iterates stages sequentially (`src/anonreq/pipeline/manager.py:59-117`)
5. **ClassificationStage** determines action (BLOCK/PASS/ANONYMIZE/ROUTE_LOCAL) (`src/anonreq/pipeline/classification.py:41-88`)
6. **DetectionStage** runs regex + Presidio + MNPI + enterprise detection, merges via SpanArbiter, applies exclusion list and context boosting (`src/anonreq/pipeline/detection.py:102-326`)
7. **TokenizationStage** replaces PII spans with `[TYPE_N]` tokens, stores mapping in Valkey (`src/anonreq/pipeline/tokenization.py:46-172`)
8. **ForwardingGuard** verifies all prerequisites before provider call (`src/anonreq/pipeline/forwarding_guard.py:42-133`)
9. **ProviderStage** forwards sanitized request to upstream LLM (`src/anonreq/pipeline/provider.py:64-209`)
10. **RestorationStage** replaces tokens with original values in provider response (`src/anonreq/pipeline/restoration.py:49-142`)
11. **CleanupStage** deletes Valkey mapping and writes audit log entry (`src/anonreq/pipeline/cleanup.py:40-86`)
12. **Response** returned with custom headers (`X-AnonReq-Request-ID`, `X-AnonReq-Processed`, `X-AnonReq-Entity-Count`)

### Streaming Path

1. **Pre-provider pipeline** runs stages 1-8 above via `build_pre_provider_pipeline()` (`src/anonreq/routing/chat.py:76-142`)
2. **Alias resolution** maps model name to provider/model pair (`src/anonreq/routing/alias_registry.py:64-68`)
3. **Adapter selection** via `ProviderRegistry.get_adapter()` (`src/anonreq/providers/registry.py:123-140`)
4. **`adapter.translate_request()`** converts to provider-specific format (`src/anonreq/providers/adapter.py:151-163`)
5. **`adapter.stream_events()`** yields `StreamEvent` instances (`src/anonreq/providers/adapter.py:184-200`)
6. **TailBuffer FSM** reassembles chunks ensuring no partial tokens (`src/anonreq/streaming/tail_buffer.py:86-117`)
7. **StreamingRestorationStage** restores tokens in assembled text chunks (`src/anonreq/streaming/restoration.py:30-44`)
8. **SSEEmitter** formats restored text as SSE events (`src/anonreq/streaming/emitter.py`)
9. **SessionCleanup** deletes mapping and writes audit log after stream ends (`src/anonreq/streaming/cleanup.py`)

**State Management:**
- Request-scoped: `ProcessingContext` flows through pipeline stages, created per-request, destroyed after response
- Session-scoped: Valkey HASH key `anonreq:{tenant_id}:{session_id}` with TTL, holds `token → original_value` mapping
- Application-scoped: `AppState` dataclass on `app.state` holds all lifespan-managed services (cache, presidio, policy, etc.)
- No global mutable state beyond `AppState` singletons

## Key Abstractions

**PipelineStage:**
- Purpose: Interface for all stages in the anonymization pipeline
- Examples: `src/anonreq/pipeline/classification.py`, `src/anonreq/pipeline/detection.py`, `src/anonreq/pipeline/tokenization.py`
- Pattern: Template method — `execute(ctx) → ctx`; stages read/write `ProcessingContext` fields

**ProcessingContext:**
- Purpose: Single shared state object carrying request data, intermediate results, and final response through all stages
- Examples: `src/anonreq/models/processing_context.py`
- Pattern: Dataclass with `fail_secure(error)` method for pipeline abort

**ProviderAdapter:**
- Purpose: Abstract base for provider-specific schema translation
- Examples: `src/anonreq/providers/openai.py`, `src/anonreq/providers/anthropic.py`, `src/anonreq/providers/gemini.py`, `src/anonreq/providers/ollama.py`
- Pattern: Strategy pattern — `translate_request()`, `execute()`, `stream_events()`, `translate_response()`

**RuntimeSecretStore:**
- Purpose: Thread-local secret store for provider API keys, with rotation support
- Examples: `src/anonreq/secrets/store.py`
- Pattern: Context-variable scoped store with push/pop for per-request isolation during secret rotation

## Entry Points

**`create_app()` — Application Factory:**
- Location: `src/anonreq/main.py:201-428`
- Triggers: Module import (`app = create_app()` at line 460)
- Responsibilities: Creates FastAPI app, registers middleware (metrics → classification → policy → content-type → mTLS → request_id), registers routes, sets up lifespan context manager for startup/shutdown

**Lifespan Context Manager:**
- Location: `src/anonreq/main.py:241-311`
- Triggers: FastAPI startup/shutdown events
- Responsibilities: Bootstrap secrets → run startup checks → create CacheManager → bootstrap locale detection → bootstrap policy engine → bootstrap MITM proxy → bootstrap audit services → bootstrap SLO → bootstrap governance → bootstrap gateway → bootstrap SOC → bootstrap deployment proxy → bootstrap trust center → bootstrap compliance

**`POST /v1/chat/completions` — Primary Route:**
- Location: `src/anonreq/routing/chat.py:421-496`
- Triggers: HTTP POST from client
- Responsibilities: Creates ProcessingContext, runs full pipeline (non-streaming) or pre-provider pipeline + adapter streaming

**Module-level `app`:**
- Location: `src/anonreq/main.py:460`
- Triggers: `uvicorn anonreq.main:app`
- Responsibilities: Uvicorn entry point

## Architectural Constraints

- **Fail-secure/fail-closed:** Every pipeline stage, middleware, exception handler, and forwarding guard defaults to blocking rather than permissive fallback. Any ambiguity or component failure returns an error and prevents data from reaching the external provider.
- **No PII in logs or telemetry:** Audit/log/SOC/metrics/events use metadata-only fields (entity counts, token counts, classification levels). Raw request bodies, detected values, and token mappings are never emitted.
- **Ephemeral sensitive mappings:** Token mappings are stored in Valkey with TTL (`anonreq:{tenant_id}:{session_id}`), deleted after response/cleanup, and never persisted to durable storage.
- **OpenAI-compatible wire protocol:** `/v1/chat/completions` and `/v1/models` maintain OpenAI format; provider adapters translate internally. Clients never see provider-specific formats.
- **Classification before anonymization/forwarding:** BLOCK, ROUTE_LOCAL, ANONYMIZE, PASS decisions occur before external provider forwarding.
- **Multi-locale/compliance:** `X-AnonReq-Locale` header drives locale negotiation, recognizer merging, compliance preset activation, and entity type filtering.
- **Tenant isolation:** Tenant-scoped policy, usage, spend, audit, cache keys, metrics labels, and governance records do not bleed across tenants.
- **Sequential pipeline only:** No concurrent stage execution; `PipelineManager` iterates stages one at a time. Streaming path reuses the pre-provider pipeline stages.
- **Secrets never enter ProcessingContext:** API keys are resolved only at the network boundary inside `ProviderAdapter.translate_request()` or `resolve_api_key()`.
- **Single global exception handler:** `global_exception_handler` in `src/anonreq/exceptions.py` catches all unhandled exceptions and returns OpenAI-compatible error envelopes with no internal details.

## Anti-Patterns

### Bypassing PipelineManager to Forward Requests

**What happens:** Directly calling the provider from a route handler without going through `PipelineManager`.
**Why it's wrong:** Skips classification, detection, tokenization, forwarding guard, DLP, and cleanup stages — PII crosses the network boundary unanonymized.
**Do this instead:** Always construct a `PipelineManager` (via `build_pipeline()` or `build_pre_provider_pipeline()`) and call `manager.run(ctx)`. See `src/anonreq/routing/chat.py:451-458`.

### Storing Secrets in ProcessingContext

**What happens:** Attaching API keys or raw credentials to `ProcessingContext` fields.
**Why it's wrong:** `ProcessingContext` may be logged, serialized to audit, or leaked via error responses.
**Do this instead:** Resolve secrets only at the network boundary inside `ProviderAdapter.translate_request()` or `resolve_api_key()`. See `src/anonreq/providers/registry.py:147-189`.

### Skipping ForwardingGuard Checks

**What happens:** Removing or bypassing `ForwardingGuard` to allow forwarding when tokenization is incomplete.
**Why it's wrong:** The transformed request may contain untokenized PII that crosses the network boundary.
**Do this instead:** Always include `ForwardingGuard` as the last stage before `ProviderStage`. See `src/anonreq/routing/chat.py:108-136`.

### Catching Exceptions Without fail_secure()

**What happens:** Using `try/except` in pipeline stages without calling `ctx.fail_secure()`.
**Why it's wrong:** The pipeline continues executing with incomplete state, potentially forwarding unanonymized data.
**Do this instead:** Always call `ctx.fail_secure(PipelineAbortError(...))` in exception handlers within stages. See `src/anonreq/pipeline/detection.py:295-325`.

### Emitting Raw Values in Audit Logs

**What happens:** Logging detected PII values, token mappings, or raw request/response bodies.
**Why it's wrong:** Violates the no-PII-in-logs invariant and creates compliance risk.
**Do this instead:** Emit only metadata: entity counts, token counts, classification levels, action taken. See `src/anonreq/pipeline/cleanup.py:88-165`.

## Error Handling

**Strategy:** Fail-secure — every error blocks forwarding and returns a safe response. No internals leak.

**Patterns:**
- **Pipeline stage failure:** Stage calls `ctx.fail_secure(PipelineAbortError(...))` → `PipelineManager` checks `has_errors()` before next stage → provider call never executes → route handler raises `HTTPException` based on error type
- **Global exception handler:** Catches all unhandled exceptions → returns OpenAI-compatible error envelope `{"error": {"message": "...", "type": "...", "code": "...", "request_id": "..."}}` with no stack traces, request bodies, or header content
- **HTTPException handler:** Formats FastAPI `HTTPException` into the same envelope, with special handling for 451 (classification block) to include classification metadata
- **Dependency unavailable:** `DependencyUnavailableError` → HTTP 503 with generic message
- **Cache failure:** `CacheManager` retries with exponential backoff → `DependencyUnavailableError` if exhausted → pipeline aborts
- **Provider timeout/error:** `ProviderStage` maps `httpx.TimeoutException` → 504, `ConnectError` → 503, HTTP error → 502 with generic messages

## Cross-Cutting Concerns

**Logging:** Structured logging via `structlog` with field allowlist. `request_id` bound to contextvars by middleware. No PII in log fields. Audit log entries contain only metadata (entity counts, token counts, classification levels).

**Validation:** Pydantic Settings validates required env vars at import time (`src/anonreq/config/__init__.py:27-200`). Pydantic models validate request/response schemas. YAML files loaded with `yaml.safe_load()` to prevent code injection.

**Authentication:** Bearer token via `HTTPBearer(auto_error=True)` → constant-time comparison against `settings.API_KEY`. Optional OIDC verification for admin endpoints via `src/anonreq/auth/oidc.py`. Optional mTLS via `IngressMTLSMiddleware`.

**Metrics:** Prometheus counters and histograms via `prometheus_client`. Key metrics: `requests_total`, `detection_latency`, `entities_detected`, `processing_overhead`, `unrestored_tokens`, `fail_secure_events_total`. All metric labels are metadata-only (no PII).

**Middleware Stack Order (innermost to outermost on request):**
1. `set_request_context` (inline middleware) — assigns `request_id`, creates `RequestContext`
2. `IngressMTLSMiddleware` — mTLS certificate validation
3. `ContentTypeMiddleware` — content-type enforcement
4. `ClassificationResponseMiddleware` — classification response headers
5. `PolicyMiddleware` — PDP/PEP evaluation
6. `ClassificationMiddleware` — parses `X-AnonReq-Classification` header, blocks HIGHLY_RESTRICTED
7. `MetricsMiddleware` — request timing and counter increment

**Configuration:** All settings use `ANONREQ_` prefix env vars via Pydantic Settings. YAML files for policies, providers, locales, compliance presets, DLP rules, SOC sinks, model aliases, and financial crime words. Startup validation ensures required vars are present.

## Bootstrap Sequence (Lifespan Startup)

1. `setup_logging()` — structured logging configuration
2. `mode_from_env()` — resolve proxy mode (immutable for process lifetime)
3. `ContentTypeDispatcher` creation — multimodal content analysis
4. OIDC verifier build (if configured)
5. `bootstrap_runtime_secrets()` — load provider API keys into `RuntimeSecretStore`
6. `CacheManager` creation — Valkey connection pool
7. `run_startup_checks()` — Valkey health, Presidio reachability
8. Alias registry creation
9. Domain-specific bootstrap sequence:
   - `bootstrap_locale_detection()` — locale registry, negotiator, merger
   - `bootstrap_policy_engine()` — PDP, PEP, policy store, usage/spend limits
   - `bootstrap_mitm_proxy()` — CA manager, MITM handler
   - `bootstrap_audit_services()` — audit engine, chain service
   - `bootstrap_slo_services()` — SLO engine
   - `bootstrap_governance_services()` — oversight, lifecycle, transparency, notifications, approval
   - `bootstrap_gateway_services()` — gateway status, AI detector, route table
   - `bootstrap_soc_services()` — SOC normalizer, sink router, health monitor
   - `bootstrap_deployment_proxy()` — reverse/transparent proxy
   - `bootstrap_trust_center()` — trust center service
   - `bootstrap_compliance_services()` — compliance evidence service

---

*Architecture analysis: 2026-07-18*
