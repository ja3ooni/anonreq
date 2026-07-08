# Phase 3 Implementation Plan

## Plan Execution Order

Per ROADMAP.md: `03-02 → 03-01 → 03-03 → 03-04`

Provider wire formats must be understood before Tail_Buffer FSM is built.

---

## Plan 03-02: Provider Adapters

### Purpose
Implement ProviderAdapter interface + Anthropic, Gemini, Ollama adapters.

### Tasks
1. Define `ProviderRequest`, `ProviderResponse`, `ProviderResult` types
2. Define `ProviderCapabilities` model
3. Implement `ProviderAdapter` ABC
4. Implement `ProviderRegistry` with YAML config
5. Implement `CapabilityResolver` (startup-cached)
6. Implement `AnthropicAdapter`:
   - translate_request: OpenAI messages → Anthropic messages format
   - execute: HTTP POST to Anthropic API
   - stream_events: Anthropic SSE → StreamEvent normalization
   - translate_response: Anthropic response → canonical format
   - Handle: text deltas, tool calls, finish reasons, errors
7. Implement `GeminiAdapter`:
   - translate_request: OpenAI → Gemini contents[] format
   - execute: HTTP POST to Gemini API
   - stream_events: Gemini SSE → StreamEvent normalization
   - Handle: candidates, parts, finish reasons
8. Implement `OllamaAdapter`:
   - translate_request: OpenAI → Ollama chat format (nearly passthrough)
   - execute + stream_events: HTTP to configurable base URL
   - Ollama uses OpenAI-compatible schema — adapter is thin
9. Provider error normalization (PROV-08)
10. ADAPT-01 to ADAPT-04 unit tests

### Files modified
- `src/gateway/providers/adapter.py` — ABC + types
- `src/gateway/providers/anthropic.py`
- `src/gateway/providers/gemini.py`
- `src/gateway/providers/ollama.py`
- `src/gateway/providers/registry.py`
- `src/gateway/providers/capabilities.py`
- `config/providers.yaml` — adapter mapping
- `config/capabilities.yaml` — per-provider capabilities

---

## Plan 03-01: SSE Streaming Route + TailBuffer FSM

### Purpose
Implement streaming request handling: SSE response, Tail_Buffer FSM, RestorationStage for streaming, client disconnect handling, cleanup.

### Tasks
1. Implement `StreamEvent` model (all event types, normalized finish reasons)
2. Implement `TailBuffer` FSM:
   - COLLECTING/MATCHING/FLUSHING/TERMINATED states
   - Active buffer + tail window management
   - Partial token detection at buffer boundary
   - Flush heuristics (safe prefix, size, age, finish)
   - Never flush on chunk count
3. Implement streaming `RestorationStage`:
   - HGETALL pre-fetch at stream start (SSE-02)
   - Token replacement on assembled text from TailBuffer
   - Case-insensitive + bracket-optional matching (SSE-04, SSE-05)
4. Implement `SSEEmitter`:
   - text/event-stream format with delta encoding
   - Anti-buffering headers (SSE-07): Cache-Control, X-Accel-Buffering
   - Flush Tail_Buffer on terminal event (SSE-08)
5. Implement streaming route handler:
   - Detect `stream: true` flag
   - Run shared stages (Classification → Detection → Tokenization → ForwardingGuard)
   - Call ProviderAdapter.stream_events()
   - Wire through TailBuffer → RestorationStage → SSEEmitter
   - Wrap in `try/finally` with `cleanup_session()`
6. Implement client disconnect handling:
   - ASGI disconnect signal detection
   - Upstream HTTPX stream cancellation
   - Idempotent `cleanup_session()` via `SessionCleanup._cleaned`
   - Disconnect metrics and audit log
7. Implement TTL extension for long streams (CACH-05)
8. Anti-buffering + proper SSE formatting

### Files modified
- `src/gateway/streaming/stream_event.py` — StreamEvent model
- `src/gateway/streaming/tail_buffer.py` — FSM
- `src/gateway/streaming/restoration.py` — streaming restoration
- `src/gateway/streaming/emitter.py` — SSE formatting
- `src/gateway/streaming/cleanup.py` — SessionCleanup
- `src/gateway/routes/chat.py` — streaming vs non-streaming branch
- `src/gateway/pipeline/stages.py` — ProviderStage + streaming branch

---

## Plan 03-03: Model Alias Routing

### Purpose
Implement alias registry, `GET /v1/models`, and routing through aliases.

### Tasks
1. Define `ModelAlias` model with schema for future fields
2. Implement `AliasRegistry`:
   - Load from YAML config at startup
   - `resolve(alias: str) → ModelAlias`
   - Startup validation: all aliases reference valid providers
3. Implement alias → provider+model resolution in pipeline
4. Implement `GET /v1/models` endpoint
5. Update ProviderStage to accept resolved provider/model from alias registry
6. Wire alias lookup into request processing path

### Files modified
- `src/gateway/routing/alias_registry.py`
- `src/gateway/routing/model_alias.py`
- `src/gateway/routes/models.py` — GET /v1/models
- `config/model_aliases.yaml`
- `src/gateway/pipeline/stages.py` — ProviderStage alias integration

---

## Plan 03-04: Streaming Property Tests + Disconnect Load Test

### Purpose
Prove streaming correctness under Hypothesis. Prove disconnect resilience under load.

### Tasks
1. TEST-07A: Arbitrary chunk split — same text split into N chunks restores identically
2. TEST-07B: Every token split boundary — token at every possible split index restores identically
3. TEST-07C: Buffer overflow — very long streams never exceed MAX_BUFFER_CHARS
4. TEST-07D: Flush timing invariance — timing variations produce identical final output
5. TEST-07E: Reasoning blocked — no reasoning content in final client stream
6. STREAM-07A: Disconnect at arbitrary chunk boundary → cleanup
7. STREAM-07B: Disconnect during partial token match → cleanup
8. STREAM-07C: Disconnect during restoration → cleanup
9. STREAM-07D: Disconnect/FINISH race → exactly one terminal state
10. Disconnect load test: 100 concurrent disconnects, zero orphaned connections (ROADMAP SC #4)
11. ADAPT-01 to ADAPT-04 unit tests for each adapter

### Files modified
- `tests/property/test_streaming.py`
- `tests/property/test_disconnect.py`
- `tests/unit/providers/test_adapters.py`
- `tests/load/test_disconnect.py`
