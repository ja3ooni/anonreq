# Phase 3: SSE Streaming + Multi-Provider - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Streaming responses with real-time token restoration via Tail_Buffer FSM. Multi-provider support for Anthropic, Gemini, and Ollama via Provider_Adapter translation layer. Client disconnect handling. Streaming correctness proven by Hypothesis.

Plan execution order: 03-02 (provider adapters) → 03-01 (SSE + Tail_Buffer) → 03-03 (model alias routing) → 03-04 (streaming property tests + disconnect load test).
</domain>

<decisions>
## Implementation Decisions

### Architectural Guardrails
- **AG-01:** ProviderAdapters are schema translators only — no policy, classification, detection, tokenization, restoration, or cache logic
- **AG-02:** Policies route to model aliases, never directly to providers
- **AG-03:** Session IDs are internal only — clients receive Request IDs (UUIDv7)
- **AG-04:** Fail-secure > availability. Detection failures return errors. Never bypass anonymization.
- **AG-05:** TailBuffer never emits partial token matches
- **AG-06:** RestorationStage is separate from TailBuffer
- **AG-07:** All provider streams normalize to StreamEvent canonical model
- **AG-08:** Reasoning streams are blocked in MVP (REASONING_DELTA dropped before emission)
- **AG-09:** Secrets never enter ProcessingContext — resolved only inside ProviderFactory/ProviderAdapter
- **AG-10:** All terminal states trigger cleanup_session() via `finally:`
- **AG-11:** TTL is safety net only — never primary cleanup mechanism
- **AG-12:** All routing occurs through aliases. Alias registry is the control plane.

### StreamEvent Canonical Model
- **D-54:** `StreamEvent(BaseModel)` with fields: event_type, provider, role, delta_text, tool_call, reasoning, finish_reason, metadata
- **D-55:** Event types: START, TEXT_DELTA, TOOL_CALL_DELTA, REASONING_DELTA, FINISH, ERROR, HEARTBEAT
- **D-56:** TailBuffer processes only TEXT_DELTA — all other event types bypass the FSM
- **D-57:** Finish reasons normalized to: STOP, LENGTH, TOOL_CALL, CONTENT_FILTER, ERROR, UNKNOWN
- **D-58:** REASONING_DELTA events are dropped before emission in MVP — not forwarded, not processed by TailBuffer, not persisted

### Tail_Buffer FSM
- **D-59:** FSM states: START → COLLECTING → MATCHING → FLUSHING → COLLECTING (loop) → TERMINATED
- **D-60:** In COLLECTING: append incoming chunk, transition to MATCHING
- **D-61:** In MATCHING: if full token match → FLUSHING; if partial match at buffer tail → COLLECTING (wait for more data); if no match → FLUSHING
- **D-62:** In FLUSHING: emit safe content before tail window, retain tail window (MAX_TOKEN_LENGTH × 2, default 128 chars)
- **D-63:** Buffer limits: TAIL_WINDOW_CHARS = 128, MAX_BUFFER_CHARS = 2048, MAX_BUFFER_AGE_MS = 1000
- **D-64:** Flush triggers: safe prefix exists before tail window; buffer exceeds MAX_BUFFER_CHARS; buffer age exceeds MAX_BUFFER_AGE_MS; provider emits finish event
- **D-65:** Never flush based on chunk count — chunk count is provider-dependent, has no semantic meaning

### ProviderAdapter Contract
- **D-66:** `class ProviderAdapter(ABC)` with: `provider_name`, `capabilities`, `translate_request(ctx)`, `execute(request)`, `stream_events(request)`, `translate_response(ctx, response)`
- **D-67:** Adapter returns `ProviderResult` envelope containing either `response: ProviderResponse` or `stream: AsyncIterator[StreamEvent]` plus streaming flag
- **D-68:** Pipeline branches exactly once after ProviderStage — non-streaming goes to RestorationStage, streaming goes to TailBuffer FSM → RestorationStage → SSEEmitter
- **D-69:** ProviderCapabilities: streaming, tool_calling, reasoning, vision, embeddings, json_mode, function_calling, max_context_window, max_output_tokens

### ProviderAdapter Registry & Capability Resolution
- **D-70:** Adapters resolved through `ProviderRegistry.get_adapter(provider_name)` — YAML-configured mapping
- **D-71:** Adapter responsibilities: translate request/response schemas, normalize streaming events/finish reasons/tool calls/errors
- **D-72:** Adapter prohibitions: no classification, detection, tokenization, restoration, Valkey access, policy/routing/governance decisions
- **D-73:** `CapabilityResolver` abstraction with tenant_id API — startup-cached implementation in MVP
- **D-74:** Capability resolution order: YAML config (authoritative) → optional provider discovery (validate/enrich only, never override)
- **D-75:** Future capability pipeline: ProviderCapabilities → Platform Policy Override → Tenant Policy Override → EffectiveCapabilities

### Streaming Pipeline Architecture
- **D-76:** Streaming path: Classification → Detection → Tokenization → ForwardingGuard → ProviderAdapter → StreamEvent normalization → TailBuffer FSM → RestorationStage → SSEEmitter
- **D-77:** Non-streaming path: shared stages up to ProviderStage → ProviderAdapter → RestorationStage (full-response) → Response
- **D-78:** RESTORATION STAGE is a dedicated, independently testable component — receives assembled text from TailBuffer, resolves tokens via Valkey mappings, emits restored text
- **D-79:** TailBuffer never knows about Valkey, mappings, token formats, or restoration rules
- **D-80:** RestorationStage never knows about buffer windows, FSM states, partial matches, or chunk boundaries

### Client Disconnect Handling
- **D-81:** ASGI disconnect signal is source of truth for disconnect detection
- **D-82:** On disconnect: cancel upstream HTTPX stream → stop TailBuffer → stop RestorationStage → emit disconnect metrics → cleanup_session()
- **D-83:** First terminal state wins — if FINISH and DISCONNECT race, FINISH wins if the event already entered pipeline
- **D-84:** No StreamEvent processed after disconnect detected (STREAM-03 invariant)
- **D-85:** Disconnect with provider timeout later → terminal state remains CLIENT_DISCONNECT
- **D-86:** Terminal states: FINISH, CLIENT_DISCONNECT, PROVIDER_ERROR, PROVIDER_TIMEOUT, INTERNAL_ERROR, TASK_CANCELLED
- **D-87:** `cleanup_session()` is idempotent — `SessionCleanup._cleaned` flag ensures exactly-once execution. Delete Valkey mapping, release buffers, cancel upstream tasks, structured audit log, metrics emission

### API Key Management
- **D-88:** Hybrid env var naming: `ANONREQ_{PROVIDER}_API_KEY` preferred, `{PROVIDER}_API_KEY` fallback. Resolution order: ANONREQ_* → standard → startup validation error
- **D-89:** Supported: openai, anthropic, gemini, mistral, groq, openrouter (API keys); ollama (base URL)
- **D-90:** Secrets resolved only inside ProviderFactory/ProviderAdapter — never stored in ProcessingContext

### Model Alias Routing
- **D-91:** Richer alias schema with future fields reserved: `capabilities`, `metadata`, `fallback`, `routes`. MVP activation: alias → provider → model only
- **D-92:** Rich schema (reserved for future — not active in MVP):
  ```yaml
  model_aliases:
    smart:
      provider: anthropic
      model: claude-sonnet-4
      capabilities:
        streaming: true
        tools: true
      metadata:
        owner: default
        description: Enterprise default model
      fallback:
        provider: openai
        model: gpt-4o
  ```
- **D-93:** Simple MVP schema (active):
  ```yaml
  model_aliases:
    fast:
      provider: openai
      model: gpt-4o-mini
    smart:
      provider: anthropic
      model: claude-sonnet-4
    local:
      provider: ollama
      model: llama3.3:70b
  ```
- **D-94:** Client sends alias as `model` field. Gateway resolves alias → provider + model. Client never sees provider details
- **D-95:** Classification rules route to model aliases, not provider names
- **D-96:** `GET /v1/models` returns configured aliases with metadata

### Streaming Property Tests (Phase 3)
- **D-97:** TEST-07A: Same text split into N arbitrary chunks must restore identically
- **D-98:** TEST-07B: Token split at every possible boundary must restore identically
- **D-99:** TEST-07C: Very long streams never exceed MAX_BUFFER_CHARS
- **D-100:** TEST-07D: Flush timing variations never change output
- **D-101:** TEST-07E: If provider emits reasoning events, no reasoning content appears in final client stream
- **D-102:** STREAM-07A: Disconnect at arbitrary chunk boundary → cleanup_session(), zero orphaned mappings
- **D-103:** STREAM-07B: Disconnect during partial token match → cleanup_session(), no partial token emission
- **D-104:** STREAM-07C: Disconnect during restoration → cleanup_session()
- **D-105:** STREAM-07D: Disconnect/FINISH race → exactly one terminal state, cleanup_session()
- **D-106:** ADAPT-01: Canonical request → provider request translation
- **D-107:** ADAPT-02: Provider response → canonical response translation
- **D-108:** ADAPT-03: Provider stream → StreamEvent normalization
- **D-109:** ADAPT-04: Error normalization across providers

### From Prior Phases (carried forward)
- D-01 to D-53 from Phases 1 and 2 apply fully — error model, logging, config, tenant isolation, Valkey HASH, pipeline orchestration, ForwardingGuard, detection/classification strategies
</decisions>

<canonical_refs>
## Canonical References

### Requirements
- `.planning/REQUIREMENTS.md` — SSE-01 to SSE-08, PROV-02 to PROV-08, CACH-05, TEST-07
- `.planning/ROADMAP.md` § Phase 3 — Success criteria, 4 plans (03-02 → 03-01 → 03-03 → 03-04)

### Phase 1 & 2 Decisions
- `.planning/phases/01-foundation-fail-secure-auth/01-CONTEXT.md` — D-01 to D-21
- `.planning/phases/02-core-pipeline-classification-non-streaming/02-CONTEXT.md` — D-22 to D-53

### Project Decisions
- `.planning/PROJECT.md` — Python 3.12 + FastAPI, Presidio sidecar, Valkey, Docker Compose, Apache 2.0, fail-secure mandate

### Architectural Guardrails
- `.planning/phases/03-sse-streaming-multi-provider/03-ARCHITECTURE.md` — Detailed architecture document
- `.planning/phases/03-sse-streaming-multi-provider/03-DOMAIN-MODEL.md` — Data model definitions
- `.planning/phases/03-sse-streaming-multi-provider/03-IMPLEMENTATION-PLAN.md` — Implementation phasing
- `.planning/phases/03-sse-streaming-multi-provider/03-TEST-STRATEGY.md` — Testing approach
- `.planning/phases/03-sse-streaming-multi-provider/03-TASK-BREAKDOWN.md` — Task-level breakdown
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 1: Config, logging, error handling, auth, Docker scaffold
- Phase 2: Pipeline orchestration (ProcessingContext), TextExtractor, detection/classification stages, ForwardingGuard, Valkey cache manager, non-streaming restoration

### Established Patterns
- ProcessingContext-based stage pipeline (D-45 to D-49)
- Stage registry + sequential execution with internal concurrency
- DetectionProvider interface

### Integration Points
- ProviderAdapter interface for Anthropic/Gemini/Ollama schema translation
- ASGI lifespan events for disconnect detection
- SSE response streaming via FastAPI StreamingResponse
- Provider alias registry → `GET /v1/models`
</code_context>

<specifics>
## Specific Ideas

- Model alias = control plane for routing, sovereignty, and provider abstraction
- All routing through aliases — classification rules target aliases, not provider names
- `ProviderResult` envelope avoids both fake-streams-for-non-streaming and union-type-leakage
- Reasoning blocked in MVP; future `reasoning_mode: BLOCK | ALLOW | ANONYMIZE`
- `cleanup_session()` called from `finally:` in stream handler — idempotent via `_cleaned` flag
- Secrets never enter ProcessingContext — resolved at network boundary in ProviderAdapter
</specifics>

<deferred>
## Deferred Ideas

- Weighted failover/routes across providers — future enterprise phase
- Dynamic provider capability discovery — future phase
- Reasoning stream anonymization — Phase 7+
- Tenant-specific capability overrides — Phase 8+
- Client-controlled session IDs — post-MVP
- Per-model capability resolution — Phase 15+
</deferred>

---

*Phase: 3-SSE Streaming + Multi-Provider*
*Context gathered: 2026-06-20*
