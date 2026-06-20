# Phase 3 Domain Model: SSE Streaming + Multi-Provider

## StreamEvent

```python
class EventType(str, Enum):
    START = "START"
    TEXT_DELTA = "TEXT_DELTA"
    TOOL_CALL_DELTA = "TOOL_CALL_DELTA"
    REASONING_DELTA = "REASONING_DELTA"
    FINISH = "FINISH"
    ERROR = "ERROR"
    HEARTBEAT = "HEARTBEAT"

class FinishReason(str, Enum):
    STOP = "STOP"
    LENGTH = "LENGTH"
    TOOL_CALL = "TOOL_CALL"
    CONTENT_FILTER = "CONTENT_FILTER"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"

class ToolCallDelta(BaseModel):
    index: int
    id: str | None = None
    type: str | None = None  # "function"
    function_name: str | None = None
    function_arguments: str | None = None

class StreamEvent(BaseModel):
    event_type: EventType
    provider: str
    role: str | None = None
    delta_text: str | None = None
    tool_call: ToolCallDelta | None = None
    reasoning: str | None = None
    finish_reason: FinishReason | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

## TailBuffer FSM

```python
class BufferState(str, Enum):
    COLLECTING = "COLLECTING"
    MATCHING = "MATCHING"
    FLUSHING = "FLUSHING"
    TERMINATED = "TERMINATED"

@dataclass
class TailBuffer:
    active_buffer: str = ""
    tail_window: str = ""
    state: BufferState = BufferState.COLLECTING
    last_flush_at: float = 0.0

    # Config
    TAIL_WINDOW_CHARS: int = 128        # MAX_TOKEN_LENGTH × 2
    MAX_BUFFER_CHARS: int = 2048
    MAX_BUFFER_AGE_MS: int = 1000

    def ingest(self, chunk: str) -> AsyncIterator[str]: ...
    # emits assembled text chunks (safe content before tail window)
```

## ProviderAdapter

```python
class ProviderCapabilities(BaseModel):
    streaming: bool = False
    tool_calling: bool = False
    reasoning: bool = False
    vision: bool = False
    embeddings: bool = False
    json_mode: bool = False
    function_calling: bool = False
    max_context_window: int = 0
    max_output_tokens: int = 0

@dataclass
class ProviderRequest:
    method: str = "POST"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0

@dataclass
class ProviderResponse:
    status_code: int = 200
    body: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

@dataclass
class RestoredResponse:
    body: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)

@dataclass
class ProviderResult:
    streaming: bool
    response: ProviderResponse | None = None
    stream: AsyncIterator[StreamEvent] | None = None
```

## Model Alias

```python
class ModelAlias(BaseModel):
    provider: str
    model: str
    capabilities: ProviderCapabilities | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    fallback: dict[str, str] | None = None      # {provider, model} — future
    routes: list[dict] | None = None             # future

class AliasRegistry:
    def resolve(self, alias: str) -> ModelAlias: ...
    def list_aliases(self) -> dict[str, ModelAlias]: ...
```

## CapabilityResolver

```python
class CapabilityResolver:
    def get_effective_capabilities(
        self,
        provider: str,
        tenant_id: str = "default"
    ) -> ProviderCapabilities: ...
```

Startup-cached in MVP. Future: merge provider → platform → tenant overrides.

## Session Cleanup

```python
class SessionCleanup:
    _cleaned: bool = False

    async def cleanup(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        await self._delete_valkey_mapping()
        await self._release_buffers()
        await self._cancel_upstream()
        await self._emit_audit_log()
        await self._emit_metrics()
```

Idempotent. Called from `finally:` in stream handler. All terminal states converge here.

## ProcessingContext (extended for streaming)

```python
@dataclass
class ProcessingContext:
    request_id: str
    tenant_id: str
    context_id: str       # UUIDv7

    # Input
    original_request: dict
    text_nodes: list[TextNode]

    # Pipeline state
    classification_result: ClassificationResult | None = None
    detections: list[Detection] | None = None
    token_mappings: dict[str, str] | None = None    # token → original_value
    transformed_request: dict | None = None

    # Provider
    provider: str | None = None
    model: str | None = None

    # Output
    provider_response: ProviderResponse | None = None
    restored_response: RestoredResponse | None = None

    # Streaming state
    stream_events: AsyncIterator[StreamEvent] | None = None
    stream_finished: bool = False
    terminal_state: str | None = None

    # Audit
    audit_metadata: dict[str, Any] = field(default_factory=dict)
```
