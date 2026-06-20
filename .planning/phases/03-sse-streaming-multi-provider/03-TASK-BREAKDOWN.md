# Phase 3 Task Breakdown

## Wave 1: Provider Adapters (03-02)

### Task 1.1 — Core types
- `ProviderRequest`, `ProviderResponse`, `ProviderResult`, `RestoredResponse`
- `ProviderCapabilities` model
- `ProviderAdapter` ABC
- Files: `src/gateway/providers/`

### Task 1.2 — Provider registry
- `ProviderRegistry` with YAML config loading
- `CapabilityResolver` (startup-cached, tenant_id API)
- Files: `src/gateway/providers/registry.py`, `src/gateway/providers/capabilities.py`

### Task 1.3 — AnthropicAdapter
- Schema translation: OpenAI → Anthropic messages
- Non-streaming execute
- Streaming: SSE → `StreamEvent` normalization
- Error normalization

### Task 1.4 — GeminiAdapter
- Schema translation: OpenAI → Gemini contents[]
- Non-streaming execute
- Streaming: SSE → `StreamEvent` normalization

### Task 1.5 — OllamaAdapter
- Thin adapter (OpenAI-compatible)
- Configurable base URL
- Streaming passthrough

### Task 1.6 — Adapter tests
- ADAPT-01 through ADAPT-04 for all adapters

---

## Wave 2: SSE Streaming + TailBuffer (03-01)

### Task 2.1 — StreamEvent model
- `EventType`, `FinishReason`, `ToolCallDelta`, `StreamEvent`
- Files: `src/gateway/streaming/stream_event.py`

### Task 2.2 — TailBuffer FSM
- `BufferState` enum
- `TailBuffer` class with COLLECTING/MATCHING/FLUSHING/TERMINATED
- Partial token detection, tail window management
- Flush heuristics (safe prefix, size, age, finish)
- Unit tests for all state transitions

### Task 2.3 — Streaming RestorationStage
- HGETALL pre-fetch at stream start
- Token replacement on assembled text
- Case-insensitive + bracket-optional matching
- Unit tests for restoration edge cases

### Task 2.4 — SSEEmitter
- `text/event-stream` delta formatting
- Anti-buffering headers
- Flush on terminal event

### Task 2.5 — Streaming route handler
- `stream: true` detection
- Shared stages → ProviderAdapter.stream_events → TailBuffer → RestorationStage → SSEEmitter
- `try/finally` with `cleanup_session()`

### Task 2.6 — Client disconnect
- ASGI disconnect signal detection
- Upstream HTTPX cancellation
- `SessionCleanup` (idempotent, `_cleaned` flag)

### Task 2.7 — TTL extension for long streams (CACH-05)
- Extend Valkey TTL at 80% elapsed time

---

## Wave 3: Model Alias Routing (03-03)

### Task 3.1 — ModelAlias model
- Richer schema with future fields (capabilities, metadata, fallback, routes)
- `AliasRegistry` with YAML loading
- `resolve(alias) → ModelAlias`

### Task 3.2 — GET /v1/models
- List configured aliases with metadata
- Files: `src/gateway/routes/models.py`

### Task 3.3 — Alias integration in pipeline
- ProviderStage accepts resolved provider/model from alias
- Wire alias lookup into request path

---

## Wave 4: Property Tests + Load Tests (03-04)

### Task 4.1 — Streaming property tests
- TEST-07A through TEST-07E

### Task 4.2 — Disconnect property tests
- STREAM-07A through STREAM-07D

### Task 4.3 — Disconnect load test
- 100 concurrent disconnects
- Zero orphaned connections verification

---

## Dependency Graph

```
Task 1.1 (Core types)
    ↓
Task 1.2 (Registry) ──────────────┐
    ↓                               ↓
Task 1.3-1.5 (Adapters)      Task 3.1-3.3 (Alias)
    ↓                               │
Task 1.6 (Adapter tests)            │
    ↓                               │
Task 2.1 (StreamEvent model)       │
    ↓                               │
Task 2.2 (TailBuffer FSM)         │
    ↓                               │
Task 2.3 (RestorationStage)       │
    ↓                               │
Task 2.4 (SSEEmitter)             │
    ↓                               │
Task 2.5 (Route handler) ←────────┘
    ↓
Task 2.6 (Disconnect)
    ↓
Task 2.7 (TTL extension)
    ↓
Task 4.1-4.3 (Tests)
```

## File Manifest

```
src/gateway/
├── providers/
│   ├── __init__.py
│   ├── adapter.py          # ABC + types
│   ├── anthropic.py
│   ├── gemini.py
│   ├── ollama.py
│   ├── registry.py
│   └── capabilities.py
├── streaming/
│   ├── __init__.py
│   ├── stream_event.py
│   ├── tail_buffer.py
│   ├── restoration.py
│   ├── emitter.py
│   └── cleanup.py
├── routing/
│   ├── __init__.py
│   ├── alias_registry.py
│   └── model_alias.py
├── routes/
│   ├── __init__.py
│   ├── chat.py             # streaming + non-streaming
│   └── models.py
└── pipeline/
    └── stages.py            # ProviderStage streaming branch

config/
├── providers.yaml
├── capabilities.yaml
└── model_aliases.yaml

tests/
├── unit/providers/
│   └── test_adapters.py
├── unit/streaming/
│   ├── test_tail_buffer.py
│   ├── test_restoration.py
│   └── test_cleanup.py
├── unit/routing/
│   └── test_alias_registry.py
├── property/
│   ├── test_streaming.py
│   └── test_disconnect.py
└── load/
    └── test_disconnect.py
```
