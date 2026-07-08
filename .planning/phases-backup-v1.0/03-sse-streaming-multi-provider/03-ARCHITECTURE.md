# Phase 3 Architecture: SSE Streaming + Multi-Provider

## Non-Streaming Pipeline (Phase 2)

```
Ingress
  → Classification
  → Detection
       ├── Regex (deterministic identifiers)
       └── Presidio NER (fuzzy entities, concurrent per-TextNode)
  → Tokenization
  → ForwardingGuard
  → ProviderAdapter
       └── translate_request()
       └── execute()
       └── translate_response()
  → RestorationStage
  → Response
```

## Streaming Pipeline (Phase 3)

```
Ingress
  → Classification
  → Detection
  → Tokenization
  → ForwardingGuard
  → ProviderAdapter
       └── translate_request()
       └── stream_events()  → AsyncIterator[StreamEvent]
  → StreamEvent Normalization
  → TailBuffer FSM
       └── COLLECTING → MATCHING → FLUSHING loop
       └── TEXT_DELTA only; tool_calls/reasoning/finish bypass
  → RestorationStage
       └── Token replacement via Valkey HGGETALL
  → SSEEmitter
       └── text/event-stream, anti-buffering headers
       └── cleanup_session() in finally:
```

## Shared Stages (both pipelines)

| Stage | Input | Output | Responsibility |
|-------|-------|--------|----------------|
| Classification | ProcessingContext | ProcessingContext.classification_result | 4-tier BLOCK/ROUTE_LOCAL/ANONYMIZE/PASS |
| Detection | ProcessingContext | ProcessingContext.detections | Regex + Presidio NER, span arbitration |
| Tokenization | ProcessingContext | ProcessingContext.token_mappings | `[TYPE_N]` replacement, dedup, HASH commit |
| ForwardingGuard | ProcessingContext | pass/fail (503) | Verify all prerequisites complete |

## Streaming-Specific Stages

| Stage | Input | Output | Responsibility |
|-------|-------|--------|----------------|
| ProviderAdapter.stream_events | ProviderRequest | AsyncIterator[StreamEvent] | Provider wire → canonical events |
| TailBuffer FSM | StreamEvent (TEXT_DELTA) | Assembled text chunks | Reassemble chunks, never emit partial tokens |
| RestorationStage | Assembled text | Restored text | Replace tokens with Valkey mappings |
| SSEEmitter | Restored text | SSE response stream | Format and stream to client, handle disconnect |

## ProviderResult Envelope

```python
@dataclass
class ProviderResult:
    streaming: bool
    response: ProviderResponse | None = None        # non-streaming
    stream: AsyncIterator[StreamEvent] | None = None  # streaming
```

Pipeline branches exactly once after ProviderStage reads this envelope.

## ProviderAdapter Contract

```python
class ProviderAdapter(ABC):

    @property
    def provider_name(self) -> str: ...

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def translate_request(self, ctx: ProcessingContext) -> ProviderRequest: ...

    async def execute(self, request: ProviderRequest) -> ProviderResponse: ...

    async def stream_events(self, request: ProviderRequest) -> AsyncIterator[StreamEvent]: ...

    def translate_response(self, ctx: ProcessingContext, response: ProviderResponse) -> RestoredResponse: ...
```

Adapters are pure schema translators. Zero policy logic (AG-01).

## Provider Capability Resolution

```
ProviderCapability (YAML config — authoritative)
    ↓
Platform Policy Override (optional discovery — validate/enrich only)
    ↓
Tenant Policy Override (future — Phase 8+)
    ↓
EffectiveCapability (startup-cached in MVP)
```

## Model Alias Resolution

```
Client sends: model: "smart"
    ↓
AliasRegistry.resolve("smart")
    ↓
Returns: (provider="anthropic", model="claude-sonnet-4")
    ↓
ProviderRegistry.get_adapter("anthropic")
    ↓
ProviderAdapter translates request/stream/response
```

## Client Disconnect Handling

```
ASGI disconnect signal
    ↓
cancel upstream HTTPX stream
    ↓
stop TailBuffer processing
    ↓
stop RestorationStage
    ↓
emit disconnect metrics
    ↓
cleanup_session()  (idempotent)
```

First terminal state wins. `cleanup_session()` executes exactly once via `_cleaned` flag.

## Architectural Guardrails (AG-01 through AG-12)

See `03-CONTEXT.md` for the complete list.
