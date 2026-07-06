<!-- refreshed: 2026-07-06 -->
# Architecture

**Analysis Date:** 2026-07-06

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          HTTP INGRESS (port 8080)                            │
│                 FastAPI + Uvicorn + Middleware Stack                          │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│   Auth Layer     │  Proxy Modes     │  Middleware       │  Admin Routes      │
│  `dependencies`  │  `proxy/modes`   │  `middleware/`    │  `admin/`          │
│  Bearer token    │  proxy-only      │  Metrics → Class  │  /v1/admin/*       │
│  validation      │  full            │  → Policy → Resp  │  Policy/Config     │
└────────┬─────────┴────────┬─────────┴─────────┬────────┴─────────┬──────────┘
         │                 │                   │                  │
         ▼                 ▼                   ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE ORCHESTRATION                               │
│                     `routing/chat.py` · `pipeline/manager.py`                │
│                                                                              │
│  ProcessingContext flows sequentially through registered PipelineStage(s):   │
│                                                                              │
│  [1] Classification ─ [2] LocaleNegotiation ─ [3] Detection ─ [4] Sensitivity│
│  ─ [5] PolicyEnforcement ─ [6] Tokenization ─ [7] ForwardingGuard            │
│  ─ [8] ProviderStage ─ [9] Restoration ─ [10] Cleanup                        │
└──────────────────────────────┬──────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       EXTERNAL SYSTEMS / DATA STORES                         │
│                                                                              │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐              │
│  │ Valkey   │  │   Presidio   │  │PostgreSQL│  │   LLM      │              │
│  │(ephemeral│  │  Analyzer    │  │ (audit   │  │ Providers  │              │
│  │ cache)   │  │  (NER+PII)   │  │  chain)  │  │OpenAI/Anthrop│             │
│  └──────────┘  └──────────────┘  └──────────┘  │ic/Gemini   │              │
│                                                  │/Ollama    │              │
│                                                  └────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Application Factory | Creates FastAPI app, wires middleware, exception handlers, lifespan, routes | `src/anonreq/main.py` |
| Auth Dependencies | Bearer token validation, RequestContext creation | `src/anonreq/dependencies.py` |
| Exception Hierarchy | Fail-secure error classes + global exception handler | `src/anonreq/exceptions.py` |
| Config / Settings | Pydantic-settings env vars + YAML provider registry | `src/anonreq/config/__init__.py` |
| Proxy Modes | Mode enum (proxy-only/full/transparent), mode-dependent pipeline | `src/anonreq/proxy/modes.py` |
| Pipeline Manager | Sequential stage executor with fail-secure abort | `src/anonreq/pipeline/manager.py` |
| Pipeline Stage Base | Abstract base for all pipeline stages | `src/anonreq/pipeline/base.py` |
| Chat Route Handler | POST /v1/chat/completions — streaming + non-streaming | `src/anonreq/routing/chat.py` |
| Detection Engine | Regex + Presidio NER + span arbitration + context boost | `src/anonreq/detection/pipeline.py`, `detection/` |
| Tokenization Engine | PII→`[TYPE_N]` replacement, in-memory mapping store | `src/anonreq/tokenization/tokenizer.py` |
| Restoration Engine | Token→original reverse in LLM responses | `src/anonreq/restore/engine.py`, `restore/path_tracker.py` |
| Streaming Handler | SSE streaming with TailBuffer for split tokens | `src/anonreq/streaming/` |
| Provider Adapters | OpenAI schema→Anthropic/Gemini/Ollama translation | `src/anonreq/providers/` |
| Policy Engine | PDP/PEP for rate limits, spend control, residency routing | `src/anonreq/policy/` |
| Governance | Agent tool call governance, approval, model/provider inventory | `src/anonreq/governance/` |
| Compliance Engine | Preset-based compliance checks (GDPR, POPIA, etc.) | `src/anonreq/compliance/` |
| Audit Chain | Immutable audit log with chain anchor | `src/anonreq/services/audit_chain.py` |
| SLO Engine | Service level objective tracking and breach detection | `src/anonreq/services/slo_engine.py` |
| Breach Detector | Webhook-based breach notification dispatch | `src/anonreq/services/breach_detector.py` |
| AI Firewall | Injection detection, jailbreak detection, DLP pipeline | `src/anonreq/firewall/` |
| SOC Integration | SIEM sink routing, MITRE ATT&CK mapping, event normalization | `src/anonreq/soc/` |
| Discovery | AI traffic discovery, hostname allowlist, flow analysis | `src/anonreq/discovery/` |
| Multimodal | Image/file content analysis for PII in non-text payloads | `src/anonreq/multimodal/` |
| Voice Pipeline | Voice sanitization, STT engine, detector | `src/anonreq/voice/` |
| Health Endpoints | GET /health, GET /health/ready for load balancers/Docker | `src/anonreq/health.py` |
| Startup Checks | Pre-flight Valkey + Presidio connectivity | `src/anonreq/startup_checks.py` |
| Logging Config | Structured JSON logging with strict field allowlist | `src/anonreq/logging_config.py` |

## Pattern Overview

**Overall:** Pipeline-based gateway architecture with sequential stage orchestration. The system is a FastAPI proxy that intercepts OpenAI-compatible chat requests, runs them through an anonymization pipeline, forwards to the target LLM provider, and restores tokens in the response.

**Key Characteristics:**
- **Pipeline pattern** — request processing is decomposed into ordered stages (`PipelineStage`), each operating on a shared `ProcessingContext`
- **Fail-secure** — any error in any pipeline stage aborts execution and returns HTTP 5xx; unsanitized data never reaches the provider
- **OpenAI-compatible wire protocol** — single input schema (`POST /v1/chat/completions`), provider-specific adapters for Anthropic/Gemini/Ollama
- **Proxy mode polymorphism** — three modes (proxy-only, full, transparent) determine which pipeline stages are active
- **Middleware-layered ingress** — MetricsMiddleware → ClassificationMiddleware → PolicyMiddleware → ClassificationResponseMiddleware before routes
- **In-memory tokenization** — PII→token mappings stored in Valkey/Redis with TTL, no persistent disk storage
- **Provider adapter pattern** — each LLM provider implements `ProviderAdapter` with `translate_request()` and `translate_response()`

## Layers

**Ingress Layer:**
- Purpose: HTTP entry point, authentication, middleware processing
- Location: `src/anonreq/main.py`
- Contains: FastAPI app factory, middleware registration, router inclusion, exception handler registration
- Depends on: `config/`, `dependencies.py`, `exceptions.py`, `middleware/`
- Used by: External HTTP clients

**Middleware Layer:**
- Purpose: Cross-cutting request processing before route handlers
- Location: `src/anonreq/middleware/`
- Contains: `MetricsMiddleware` (Prometheus), `ClassificationMiddleware` (data classification), `PolicyMiddleware` (PDP/PEP), `ClassificationResponseMiddleware` (response headers)
- Depends on: `monitoring/`, `classification/`, `policy/`
- Used by: All incoming HTTP requests

**Pipeline Layer:**
- Purpose: Core request processing — extract, classify, detect, tokenize, forward, restore
- Location: `src/anonreq/pipeline/`
- Contains: `PipelineManager` (orchestrator), `PipelineStage` (base), individual stages
- Depends on: `detection/`, `tokenization/`, `classification/`, `providers/`, `restore/`, `streaming/`, `cache/`
- Used by: Route handlers in `routing/chat.py`

**Domain Services Layer:**
- Purpose: Business logic services — audit chain, SLO, breach detection, lifecycle, governance
- Location: `src/anonreq/services/`
- Contains: `AuditChainService`, `SLOEngine`, `BreachDetector`, `OversightService`, `LifecycleService`, `TransparencyService`
- Depends on: `cache/`, `config/`, external DB
- Used by: Lifespan (initialized at startup), pipeline stages

**Detection Engine Layer:**
- Purpose: PII/PHI/MNPI detection via regex + Presidio NER + context boosting
- Location: `src/anonreq/detection/`
- Contains: `RegexDetector`, `PresidioClient`, `SpanArbiter`, `ExclusionList`, `ContextBooster`, MNPI recognizers
- Depends on: `config/locales/`, external Presidio service
- Used by: Pipeline `DetectionStage`

**Policy & Governance Layer:**
- Purpose: Enterprise policy enforcement (PDP/PEP), agent governance, compliance presets
- Location: `src/anonreq/policy/`, `src/anonreq/governance/`
- Contains: `PolicyDecisionPoint`, `PolicyEnforcementPoint`, `UsageLimiter`, `SpendController`, `ResidencyRouter`, `ApprovalManager`
- Depends on: `cache/`, `config/`
- Used by: Pipeline `PolicyEnforcementStage`, admin routes

**Provider Abstraction Layer:**
- Purpose: Unified interface to multiple LLM providers
- Location: `src/anonreq/providers/`
- Contains: `ProviderAdapter` base, concrete adapters (OpenAI, Anthropic, Gemini, Ollama), `ProviderRegistry`
- Depends on: `config/providers.yaml`
- Used by: Pipeline `ProviderStage`

**Security Layer:**
- Purpose: AI firewall, DLP, exfiltration detection, SOC integration
- Location: `src/anonreq/firewall/`, `src/anonreq/soc/`, `src/anonreq/casb/`, `src/anonreq/breach/`
- Contains: `FirewallPipeline`, `DLPEngine`, `SINormalizer`, `MITREMapper`, `BreachDetector`
- Depends on: `detection/`, `cache/`, external SIEM sinks
- Used by: Pipeline, middleware, lifespan

**Admin Layer:**
- Purpose: Configuration hot-reload, policy management, compliance routes
- Location: `src/anonreq/admin/`, `src/anonreq/routes/`
- Contains: Admin API routes, policy routes, compliance routes, governance routes
- Depends on: `auth/`, `config/`, `policy/`
- Used by: Administrative HTTP clients

**Storage Layer:**
- Purpose: Data persistence abstractions
- Location: `src/anonreq/cache/`, `src/anonreq/storage/`, Alembic migrations
- Contains: `CacheManager` (Valkey/Redis), `MinioStorage` (MinIO), SQLAlchemy async engine
- Depends on: External Valkey, PostgreSQL, MinIO
- Used by: All layers via dependency injection

## Data Flow

### Primary Request Path (Non-Streaming)

1. **HTTP Ingress** — Request arrives at `POST /v1/chat/completions` (`src/anonreq/routing/chat.py:361`)
2. **Middleware chain** — MetricsMiddleware → ClassificationMiddleware → PolicyMiddleware (`src/anonreq/main.py:589-606`)
3. **Auth** — `auth_context` dependency validates Bearer token, creates `RequestContext` (`src/anonreq/dependencies.py:96`)
4. **ProcessingContext creation** — Route handler creates `ProcessingContext` with `TextExtractor.extract()` (`src/anonreq/routing/chat.py:195`)
5. **Pipeline execution** — `PipelineManager.run(ctx)` executes registered stages sequentially (`src/anonreq/pipeline/manager.py:60`):
   - `ClassificationStage` — determines action (PASS/ANONYMIZE/BLOCK)
   - `LocaleNegotiationStage` — resolves locale header, merges recognizers
   - `DetectionStage` — runs regex + Presidio NER + span arbitration + MNPI
   - `SensitivityClassificationStage` — entity-based sensitivity scoring
   - `PolicyEnforcementStage` — PDP/PEP evaluation
   - `TokenizationStage` — replaces PII spans with `[TYPE_N]` tokens, stores in Valkey
   - `ForwardingGuard` — blocks if `block_all_unintercepted_ai` is set
   - `ProviderStage` — translates to provider schema, calls LLM, translates response
   - `RestorationStage` — replaces `[TYPE_N]` tokens with original values from Valkey
   - `CleanupStage` — deletes token mappings from Valkey
6. **Error handling** — any error → `ctx.fail_secure()` → `_raise_for_pipeline_errors()` → HTTP 500/503/504 (`src/anonreq/routing/chat.py:175`)
7. **Response** — validated `ChatCompletionResponse` with audit headers returned (`src/anonreq/routing/chat.py:433`)

### Secondary Flow: Streaming

1. Same middleware + auth + pre-provider pipeline stages 1–7
2. `ProviderAdapter.stream_events()` yields SSE `StreamEvent`s (`src/anonreq/routing/chat.py:293`)
3. `TailBuffer` ingests chunks, splits on token boundaries (`src/anonreq/streaming/tail_buffer.py`)
4. `StreamingRestorationStage` restores tokens in-flight (`src/anonreq/streaming/restoration.py`)
5. `SSEEmitter` formats SSE frames (`src/anonreq/streaming/emitter.py`)
6. `SessionCleanup` deletes mappings on stream end (`src/anonreq/streaming/cleanup.py`)

### Proxy-Only Mode Flow

1. HTTP ingress → minimal middleware → auth → route handler
2. No detection/anonymization pipeline — `ProxyOnlyHandler.passthrough()` (`src/anonreq/gateway/passthrough.py:69`)
3. Target latency: P50 < 2ms / P95 < 5ms / P99 < 10ms

### Transparent Proxy Flow

1. MITM TLS interception intercepts outbound AI traffic (`src/anonreq/proxy/mitm_handler.py`)
2. `TLSInterceptor` terminates TLS, re-originates to destination (`src/anonreq/proxy/tls_interceptor.py`)
3. Content parsed, routed through full pipeline, then forwarded

**State Management:**
- **Request-scoped**: `ProcessingContext` dataclass created per request, flows through pipeline stages, discarded after response
- **Session-scoped**: Token mappings stored in Valkey with `anonreq:{Session_ID}` key, TTL 60–3600s, deleted post-response
- **Application-scoped**: `app.state` on FastAPI holds long-lived singletons (CacheManager, ProviderRegistry, PDP, etc.)
- **No disk writes**: All tokenization state is in-memory via Valkey with `save ""` (persistence disabled)

## Key Abstractions

**`PipelineStage` (Abstract Base):**
- Purpose: Interface for all pipeline processing stages
- Files: `src/anonreq/pipeline/base.py`
- Pattern: Abstract class with `execute(ctx: ProcessingContext) -> ProcessingContext` method
- Implementations: ClassificationStage, DetectionStage, TokenizationStage, ProviderStage, RestorationStage, CleanupStage, LocaleNegotiationStage, SensitivityClassificationStage, PolicyEnforcementStage, ForwardingGuard

**`ProcessingContext` (Dataclass):**
- Purpose: Shared state container flowing through all pipeline stages
- Files: `src/anonreq/models/processing_context.py`
- Pattern: Single mutable dataclass — each stage reads and writes its fields

**`ProxyMode` (Enum):**
- Purpose: Determines operating mode and active pipeline stages
- Files: `src/anonreq/proxy/modes.py`
- Values: `PROXY_ONLY`, `FULL`, `TRANSPARENT`

**`ProviderAdapter` (Abstract Base):**
- Purpose: Unified interface to different LLM providers
- Files: `src/anonreq/providers/adapter.py`
- Pattern: Strategy pattern — concrete implementations for each provider

**`CacheManager`:**
- Purpose: Valkey/Redis abstraction for token mapping storage
- Files: `src/anonreq/cache/manager.py`
- Pattern: Singleton per application lifetime, initialized in lifespan

**`Settings` (Pydantic BaseSettings):**
- Purpose: Central configuration from env vars
- Files: `src/anonreq/config/__init__.py`
- Pattern: Singleton at module level, validated at import time

**`AnonReqError` (Exception Hierarchy):**
- Purpose: Structured error types with safe messages
- Files: `src/anonreq/exceptions.py`
- Subclasses: `DependencyUnavailableError`, `PipelineAbortError`, `PipelineBlockedError`, `OutboundDLPError`, `AuthenticationError`

**`Tokenization` / `Restoration`:**
- Purpose: PII→token substitution and reversal
- Files: `src/anonreq/tokenization/tokenizer.py`, `src/anonreq/restore/engine.py`
- Token format: `[TYPE_N]` — case-insensitive + bracket-optional matching

## Entry Points

**FastAPI Application:**
- Location: `src/anonreq/main.py:152` (`create_app()`)
- Triggers: Uvicorn (`uvicorn anonreq.main:app --host 0.0.0.0 --port 8080`)
- Responsibilities: Creates FastAPI app, configures middleware, exception handlers, lifespan

**`POST /v1/chat/completions`:**
- Location: `src/anonreq/routing/chat.py:361`
- Triggers: HTTP POST from client
- Responsibilities: Core anonymization pipeline — extract, detect, tokenize, forward, restore

**`GET /v1/gateway/status`:**
- Location: `src/anonreq/main.py:647`
- Triggers: HTTP GET
- Responsibilities: Returns gateway operating mode + uptime + proxy config

**`GET /health`, `GET /health/ready`:**
- Location: `src/anonreq/health.py:83,108`
- Triggers: HTTP GET (load balancers, Docker HEALTHCHECK)
- Responsibilities: Component health status (Valkey + Presidio)

**`GET /metrics`:**
- Location: `src/anonreq/main.py:610`
- Triggers: HTTP GET (Prometheus scraping)
- Responsibilities: Prometheus metrics endpoint

**Admin Routes:**
- Location: `src/anonreq/admin/router.py`
- Routes: `/v1/admin/policy/*`, `/v1/admin/config/*`, `/v1/admin/providers/*`, `/v1/admin/usage/*`, `/v1/admin/compliance/*`, `/v1/admin/incidents/*`
- Responsibilities: Configuration hot-reload, policy management, provider config

## Architectural Constraints

- **Threading:** Single-threaded async event loop (Python asyncio, FastAPI with async route handlers). Presidio client uses `max_concurrency=10` for parallel NER requests. No background worker threads or process pools.
- **Global state:** Module-level `settings = Settings()` singleton in `src/anonreq/config/__init__.py:104`. Long-lived singletons stored on `app.state` (CacheManager, ProviderRegistry, AliasRegistry, PDP, etc.). Logging config is global via `structlog.configure()`.
- **Circular imports:** `config/__init__.py` imports `Settings` which depends on `exceptions.py`. `main.py` imports from nearly every subpackage. No circular chains detected — all imports are tree-structured with `config/` and `exceptions.py` as leaves.
- **Fail-secure invariant:** Every pipeline error → HTTP 5xx. No path forwards unsanitized data to providers. Enforced via `ctx.fail_secure()` + `ctx.has_errors()` check before each stage.
- **Ephemeral cache only:** Valkey with `save ""` and `appendonly no`. No persistence. TTL-based eviction.
- **No PII in logs:** `ALLOWLIST` field allowlist in `logging_config.py:34`. Only metadata fields permitted.

## Anti-Patterns

### Module-level Settings Singleton

**What happens:** `settings = Settings()` is instantiated at module import time in `src/anonreq/config/__init__.py:104`. This requires env vars to be set before any import.

**Why it's wrong:** Makes testing harder — requires `os.environ.setdefault()` in `conftest.py:23` before any test imports. Tests that need different env var values must use `monkeypatch` before re-importing.

**Do this instead:** Use FastAPI dependency injection or `lru_cache`-based factory. See `tests/conftest.py:25-26` for the current workaround pattern.

### Sequential Pipeline with Single ProcessingContext

**What happens:** All pipeline stages operate on a single mutable `ProcessingContext` dataclass, passed by reference. Stages mutate the same object.

**Why it's wrong:** Creates implicit coupling between stages — order matters, and stage A reading a field set by stage B creates hidden dependencies. Impossible to run stages in parallel.

**Do this instead:** Accept the tradeoff — this is a deliberate architectural choice for fail-secure simplicity (D-45 through D-49). Document stage ordering dependencies explicitly.

### Hardcoded `config/` Path References

**What happens:** Many files reference config paths as string literals (e.g., `"config/classification.yaml"` in `src/anonreq/routing/chat.py:78`, `"config/mnpi_recognizers.yaml"` in `src/anonreq/routing/chat.py:113`).

**Why it's wrong:** Brittle — moving config files requires hunting through source code. No single source of truth for config paths.

**Do this instead:** Centralize config file paths in `config/__init__.py` or a dedicated `ConfigPaths` class.

## Error Handling

**Strategy:** Fail-secure with OpenAI-compatible error envelopes. Every exception returns `{"error": {"message": str, "type": str, "code": str, "request_id": str}}`.

**Patterns:**
- `AnonReqError` hierarchy for structured errors with safe messages (`src/anonreq/exceptions.py:75`)
- `global_exception_handler` catches all unhandled exceptions (`src/anonreq/exceptions.py:220`)
- `http_exception_handler` formats FastAPI's HTTPException (`src/anonreq/exceptions.py:299`)
- Pipeline errors use `ctx.fail_secure()` → `PipelineAbortError` → HTTP error

## Cross-Cutting Concerns

**Logging:** Structured JSON via `structlog` with strict field allowlist (`src/anonreq/logging_config.py:34`). `request_id` propagated via `structlog.contextvars` for trace correlation. No raw PII ever logged.

**Validation:** Pydantic models for request/response validation (`src/anonreq/models/chat.py`). Settings validated via `pydantic-settings` with `field_validator` for API key length.

**Authentication:** Bearer token via `HTTPBearer(auto_error=True)` (`src/anonreq/dependencies.py:29`). Composite `auth_context` dependency on all protected routes. Admin API has separate key (`ADMIN_API_KEY`).

**Metrics:** Prometheus client with custom counters (`dlp_violations_total`, `exfiltration_total`, `actions_total`) defined in `src/anonreq/main.py:99-113` and middleware in `src/anonreq/monitoring/metrics.py`. Exposed at `GET /metrics`.

**Observability:** Health checks (`/health`, `/health/ready`) verify Valkey + Presidio connectivity (`src/anonreq/health.py`). Pre-flight startup checks prevent boot with unavailable dependencies (`src/anonreq/startup_checks.py`).

---

*Architecture analysis: 2026-07-06*
