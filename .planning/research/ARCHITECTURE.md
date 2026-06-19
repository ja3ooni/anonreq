# Architecture Patterns

**Domain:** Self-hosted LLM Anonymization Gateway (FastAPI proxy)
**Researched:** 2026-06-19

## Recommended Architecture

### High-Level Component Diagram

```
┌──────────────┐     ┌─────────────────────────────────────────────────────┐
│   Client     │────▶│              AnonReq Gateway Process                │
│  (curl/SDK)  │     │                                                     │
└──────────────┘     │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
                     │  │ FastAPI  │  │ ASGI     │  │ Route Handlers   │  │
                     │  │ Server   │─▶│ Middle-  │─▶│ POST /v1/chat/   │  │
                     │  │ (uvicorn)│  │ ware     │  │ completions      │  │
                     │  └──────────┘  │ Stack    │  │ GET /health      │  │
                     │                └──────────┘  │ GET /v1/models   │  │
                     │                              └────────┬─────────┘  │
                     │                                       │            │
                     │                 ┌─────────────────────┼────────────┘
                     │                 │  In-Process Engine  │
                     │                 │  Pipeline            │
                     │                 │  ┌────────────────┐  │
                     │                 │  │ Text Extractor │  │  (1)
                     │                 │  │ (flatten msgs) │  │
                     │                 │  └───────┬────────┘  │
                     │                 │          ▼           │
                     │                 │  ┌────────────────┐  │
                     │                 │  │ Request        │  │  (2)
                     │                 │  │ Context Builder│  │
                     │                 │  └───────┬────────┘  │
                     │                 │          ▼           │
                     │                 │  ┌────────────────┐  │
                     │                 │  │ Detection      │  │  (3) ◀── Sidecar
                     │                 │  │ Engine Client  ├──┼──────── /analyze
                     │                 │  └───────┬────────┘  │
                     │                 │          ▼           │
                     │                 │  ┌────────────────┐  │
                     │                 │  │ Tokenization   │  │  (4)
                     │                 │  │ Engine         │  │
                     │                 │  └───────┬────────┘  │
                     │                 │          ▼           │
                     │                 │  ┌────────────────┐  │
                     │                 │  │ Cache Writer   │  │  (5) ───▶ Valkey
                     │                 │  └───────┬────────┘  │
                     │                 │          ▼           │
                     │                 │  ┌────────────────┐  │
                     │                 │  │ Provider       │  │  (6) ───▶ External LLM
                     │                 │  │ Adapter + HTTPX│  │
                     │                 │  └───────┬────────┘  │
                     │                 │          ▼           │
                     │                 │  ┌────────────────┐  │
                     │                 │  │ Restoration    │  │  (7)  (non-streaming)
                     │                 │  │ Engine         │  │
                     │                 │  └───────┬────────┘  │
                     │                 │          ▼           │
                     │                 │  ┌────────────────┐  │
                     │                 │  │ Post-Restore   │  │  (8)
                     │                 │  │ Verification   │  │
                     │                 │  └───────┬────────┘  │
                     │                 │          ▼           │
                     │                 │  ┌────────────────┐  │
                     │                 │  │ Cache Cleanup  │  │  (9)
                     │                 │  │ + Audit Logger │  │
                     │                 │  └────────────────┘  │
                     │                 └──────────────────────┘
                     │
┌──────────────┐     │  ┌──────────────────┐  ┌──────────────────┐
│  Presidio    │◀────┼──│  HTTPX Client   │  │  Valkey/Redis    │
│  Analyzer    │─────┼─▶│  (in Gateway)   │  │  (ephemeral)     │
│  Container   │     │  └──────────────────┘  └──────────────────┘
└──────────────┘     │
```

### Component Boundaries — In-Process vs Sidecar

| Component | Boundary | Rationale |
|-----------|----------|-----------|
| **FastAPI Server + ASGI Middleware** | In-process | Core routing; must be at application boundary |
| **Text Extractor** | In-process | Parses JSON, no state; pure function |
| **Detection Engine Client** | In-process HTTP client | Talks to Presidio Analyzer sidecar over HTTP. NOT the Presidio library directly — the sidecar architecture gives process isolation, independent scaling, and avoids loading spaCy models into the gateway process (which would double memory). |
| **Tokenization Engine** | In-process | Pure transformation: entity spans → `[TYPE_N]` tokens. No I/O after receiving detection results. |
| **Cache Writer/Reader** | In-process (driver) | redis-py / valkey async client. Valkey runs as separate container for fail-secure isolation. |
| **Provider Adapter** | In-process | Schema translation only (OpenAI → Anthropic/Gemini/Ollama). Pure transformations. |
| **Restoration Engine** | In-process | Token replacement + Tail_Buffer state machine for SSE. Must be in-process for zero-copy streaming. |
| **Audit Logger** | In-process | Writes structured JSON to stdout via Python logging. No external dependency. |
| **Health/Metrics** | In-process | Exposes from same FastAPI process. |

**Why Presidio Analyzer as a sidecar, not in-process:**

1. **Memory isolation**: Presidio loads spaCy/Transformers NER models (~500MB–2GB loaded). Running them in the gateway process would double the gateway's memory footprint and couple GC pressure.
2. **Independent scaling**: In high-throughput deployments, detection can be scaled horizontally (multiple Presidio containers) while the gateway remains stateless and lightweight.
3. **Fail-secure isolation**: If Presidio's NER model crashes or OOMs, it doesn't take down the gateway. The gateway detects the failure via health probe and returns HTTP 503.
4. **Language independence**: Presidio's HTTP server is Flask-based. Running it as a sidecar keeps the gateway's dependency tree lean.
5. **Hot-reload independence**: Custom recognizer config reloads happen in Presidio without restarting the gateway.

> **Key tradeoff**: Network round-trip to Presidio adds ~1-5ms per request. Acceptable given the 100ms P95 budget. If latency becomes critical, a future optimization tiers frequently-used regex recognizers into the gateway process and only sends text to Presidio for NER-based detection.

---

### Data Flow — Request Lifecycle

#### Non-Streaming Request

```
Step  Phase               What Happens                           Fail Point
────  ─────               ────────────                           ──────────
 1    REQUEST RECEIVE     Client → FastAPI route handler           HTTP 400 if invalid JSON
                          POST /v1/chat/completions                  
                          Body validated against Pydantic schema   

 2    TEXT EXTRACT        Flatten all message blocks into          HTTP 500 if extract fails
                          a list of (field_path, text) pairs       
                          Detect stream:true/false                  

 3    CONTEXT BUILD       Generate Session_ID (UUID4),             HTTP 500 if gen fails
                          parse X-AnonReq-Locale header            
                          select compliance preset                 

 4    DETECT              Send full text to Presidio Analyzer    ⚠ HTTP 500 if Presidio down
                          POST /analyze with language, entities    HTTP 504 if timeout
                          Receive list of RecognizerResult spans   
                          Apply confidence threshold filtering     

 5    TOKENIZE            Sort spans by position (reverse order)   HTTP 500 if conflict
                          Replace each span with [TYPE_N]          
                          Deduplicate identical values             
                          Build Mapping: {token → original_value}  
                          Randomize token indices per session      

 6    CACHE WRITE         Store Mapping in Valkey:               ⚠ HTTP 500 if Valkey down
                          HSET anonreq:{session_id} mapping        
                          EXPIRE with configured TTL                

 7    PROVIDER CALL       Translate to provider schema             HTTP 500 if translate fails
                          Forward via httpx.AsyncClient           HTTP 502/504 if provider down
                          Receive full JSON response              

 8    RESTORE             Pre-fetch Mapping from Valkey          ⚠ HTTP 500 if Valkey down
                          Scan response for [TYPE_N] patterns      
                          Replace each token with original value   
                          Case-insensitive + bracket-optional      

 9    VERIFY              Scan response body for residual         Log warning (never block)
                          token patterns \[[A-Z]+_\d+\]             

 10   AUDIT & CLEANUP     Emit structured audit log to stdout      Log discard on failure
                          DEL anonreq:{session_id} from Valkey     TTL fallback on DEL fail
                          Return response to client               
```

#### Streaming Request

```
Step  Phase               What Happens                           
────  ─────               ────────────                           
 1-6  (Same as non-streaming up to cache write)                  

 7    STREAM SETUP        Start httpx.AsyncClient streaming request
                          Pre-fetch Mapping via HGETALL (single call)
                          Return StreamingResponse(media_type="text/event-stream")
                          Set headers: Cache-Control: no-cache
                                       X-Accel-Buffering: no
                                       Connection: keep-alive

 8    STREAM LOOP         For each SSE chunk from provider:
      ┌──────────┐           Parse SSE event type (data:, event:, [DONE])
      │ Tail     │           Append to Tail_Buffer (max 512 chars)
      │ Buffer   │           Scan Tail_Buffer for complete [TYPE_N] tokens
      │ State    │           If token split across chunks:
      │ Machine  │             Buffer prefix, wait for suffix in next chunk
      │          │           If buffered >50 chunks or >500ms:
      │          │             Flush buffered content as-is, log warning
      └──────────┘           Replace found tokens using local Mapping
                             Yield modified SSE event to client
                             On [DONE] or connection close:
                               Flush Tail_Buffer remainder
                               Perform post-stream verification
                               Emit audit log
                               DEL mapping from Valkey

 9    POST-STREAM          Scan assembled stream for residual tokens
                           Log warning if found, increment counter
                           Close response stream
```

---

### SSE Streaming Architecture — Tail_Buffer Pattern

#### The Token-Split Problem

LLM streaming sends tokens character-by-character or subword-by-subword. A token like `[NAME_1]` can arrive split across two SSE chunks:

```
Chunk N:     data: {"content": "Hello [NAME_"}
Chunk N+1:   data: {"content": "1], how are you?"}
```

Naive per-chunk scanning would fail to match the partial `[NAME_` in chunk N.

#### Tail_Buffer State Machine

```
State Machine States:

  SCAN ──────────────► PENDING ──────────────► FLUSH
   │                      │                      │
   │ partial match         │ token complete       │ timeout/exceeded
   │ found                 │ found                │ chunks
   ▼                      ▼                      ▼
  (buffer text)         (replace +              (emit buffered
                         emit)                   content as-is)

Implementation:

class TailBuffer:
    buffer: str          # Rolling suffix of last 512 chars
    partial: str         # Current incomplete token prefix (e.g., "[NAME_")
    chunks_since_partial: int
    created_at: float

    def push(self, chunk_text: str) -> list[str]:
        """Return list of (restored) text events from this chunk."""
        self.buffer = (self.buffer + chunk_text)[-512:]
        results = []
        
        if self.partial:
            # Try to complete the partial token
            remainder = self._extract_token_after_prefix(chunk_text)
            if remainder is not None:
                full_token = self.partial + remainder
                restored = self.mapping.get(full_token, fallback=full_token)
                results.append(restored)
                self.partial = ""
                self.chunks_since_partial = 0
            else:
                self.chunks_since_partial += 1
                if self._should_flush():
                    results.append(self.partial)
                    self.partial = ""
                    self.chunks_since_partial = 0
        
        # Scan for new partial tokens
        for token in self._scan_tokens(chunk_text):
            if token.complete:
                results.append(token.restored)
            else:
                self.partial = token.prefix
                self.chunks_since_partial = 0
                self.created_at = time.monotonic()
        
        # Emit non-token text
        results.append(self._non_token_text(chunk_text))
        return results

    def _should_flush(self) -> bool:
        return (self.chunks_since_partial >= 50 or 
                time.monotonic() - self.created_at >= 0.5)
```

**Key design decisions:**

1. **Pre-fetch Mapping once**: One `HGETALL` at stream start avoids per-chunk round-trips to Valkey. The entire Mapping is held in memory for the stream's duration.
2. **Tail_Buffer size limit of 512 chars**: Large enough to hold any realistic token prefix (`[TYPE_` is at most 22 chars), small enough to not obscure memory pressure.
3. **50-chunk / 500ms flush heuristic**: Prevents indefinite buffering if the stream never completes the token. 50 chunks at typical LLM speeds (~20ms/chunk) ≈ 1 second. 500ms is the absolute cap.
4. **Case-insensitive + bracket-optional matching**: LLMs may mutate tokens to `[name_1]` or `NAME_1`. The Restoration Engine normalizes all tokens to `[TYPE_N]` before lookup.
5. **No back-pressure on the provider stream**: The gateway yields events to the client as they arrive; restoration is a transformation on the forward path, not a buffering step.

#### Streaming Proxy Core Pattern (FastAPI)

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from fastapi.sse import EventSourceResponse
import httpx
import json

router = APIRouter()

@router.post("/v1/chat/completions")
async def chat_completions(request: Request, body: ChatRequest):
    session_id = generate_session_id()
    
    # --- Request Pipeline (steps 2-6) ---
    text_blocks = extract_text(body.messages)
    context = build_context(body, session_id)
    detections = await detect_pii(text_blocks, context)
    tokenized, mapping = tokenize(body, detections)
    await cache_write(session_id, mapping)
    
    # --- Provider Call ---
    provider = select_provider(body.model)
    adapted_request = provider.translate(tokenized)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        if not body.stream:
            # Non-streaming
            response = await client.post(
                provider.url,
                json=adapted_request,
                headers=provider.headers
            )
            restored = restore_non_stream(response.json(), mapping)
            verify(restored)
            await cache_delete(session_id)
            return restored
        else:
            # Streaming
            local_mapping = mapping  # already in memory
            async def stream_restorer():
                tail = TailBuffer(local_mapping)
                async with client.stream(
                    "POST", provider.url,
                    json=adapted_request,
                    headers=provider.headers
                ) as stream:
                    async for chunk in stream.aiter_bytes():
                        events = tail.push(chunk.decode("utf-8"))
                        for event in events:
                            yield f"data: {json.dumps(event)}\n\n"
                    # Flush any remaining partial tokens
                    flush = tail.flush()
                    if flush:
                        yield flush
                    # Post-stream verification
                    verify(tail.assembled_text)
                    await cache_delete(session_id)
            
            return EventSourceResponse(stream_restorer())
```

---

### FastAPI Middleware Pattern for Request Interception

#### Recommended: ASGI Middleware Class

Abstract `BaseHTTPMiddleware` is deprecated in newer FastAPI versions. The recommended pattern is raw ASGI middleware (function-based or class-based). However, for AnonReq's use case, we actually do NOT want a middleware-based interception — we want a **route handler** pattern. Here's why:

**The "Route Handler" over "Middleware" argument:**

| Concern | Middleware | Route Handler |
|---------|-----------|---------------|
| Request body modification | Requires hacking ASGI `receive` to replay body | Natural — FastAPI/Pydantic parses body, you modify and pass it |
| Response modification (non-stream) | Works via `StreamingResponse` wrapper | Works via normal return |
| Response modification (SSE stream) | Very complex — need to wrap generator | Natural — generator yields modified events |
| Error handling + fail-secure | Must wrap `call_next` in try/except | Natural — standard Python exception handler |
| Testing | Requires TestClient with full middleware stack | Test route function directly |
| Pydantic schema access | Must re-parse body | Schema already validated |

**Therefore: The `/v1/chat/completions` route handler IS the pipeline orchestrator.** The handler function:

1. Receives validated `ChatRequest` Pydantic model
2. Calls Detection Engine
3. Calls Tokenization Engine
4. Caches mapping
5. Routes to provider
6. Restores response
7. Returns

**The middleware stack is reserved for cross-cutting concerns:**

| Middleware | Purpose | Order (outermost first) |
|-----------|---------|------------------------|
| `ProcessTimeMiddleware` | Add `X-Process-Time` header | 1 (first to see request) |
| `RequestIDMiddleware` | Inject `X-Request-ID` | 2 |
| `FailSecureMiddleware` | Catch unhandled exceptions → HTTP 500 (NEVER forward) | 3 |
| `AuthMiddleware` | Validate API keys / JWT / mTLS | 4 |
| `SSEMiddleware` | Set streaming response headers | Built into route |
| (Route Handler) | Core pipeline logic | Last |

**Fail-Secure Middleware:**

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class FailSecureMiddleware(BaseHTTPMiddleware):
    """
    Catches any unhandled exception in the pipeline and returns HTTP 500.
    Ensures no content is forwarded to provider during exception handling.
    """
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception:
            # Log metadata only (no PII)
            logger.error("fail_secure_event", 
                         session_id=getattr(request.state, "session_id", None))
            return Response(
                status_code=500,
                content=ERROR_RESPONSE_500
            )
```

---

### Configuration Management Approach

#### Layered Configuration Model

```
Layer 1: Defaults (hardcoded in code)
  ├── Confidence_Threshold: 0.7
  ├── TTL: 300s
  ├── Presidio URL: http://presidio:3000
  ├── Valkey URL: redis://valkey:6379
  └── ...

Layer 2: Environment variables (override defaults)
  ├── ANONREQ_CONFIDENCE_THRESHOLD
  ├── ANONREQ_TTL_SECONDS
  ├── ANONREQ_PRESIDIO_URL
  ├── ANONREQ_VALKEY_URL
  ├── ANONREQ_OPENAI_API_KEY
  ├── ANONREQ_ANTHROPIC_API_KEY
  ├── ANONREQ_GEMINI_API_KEY
  ├── ANONREQ_LOG_LEVEL
  └── ...

Layer 3: Config file (YAML, hot-reloadable)
  ├── custom_recognizers.yaml
  │   └── List of name, entity_type, patterns, context_words, score
  ├── exclusion_list.txt
  │   └── One term per line, supports wildcard (*)
  ├── compliance_presets.yaml
  │   └── gdpr, lgpd, pdpa, popia, etc.
  ├── provider_routes.yaml
  │   └── model aliases → provider mapping
  └── ...

Layer 4: Request headers (per-request override)
  ├── X-AnonReq-Locale: de-DE
  ├── X-AnonReq-Classification: Restricted
  └── X-AnonReq-Tenant-ID: acme-corp
```

#### Implementation Pattern

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Pydantic-based settings with env var support."""
    model_config = SettingsConfigDict(env_prefix="ANONREQ_")
    
    # Core
    confidence_threshold: float = 0.7
    ttl_seconds: int = 300
    
    # Dependencies
    presidio_url: str = "http://presidio:3000"
    valkey_url: str = "redis://valkey:6379"
    
    # Providers
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    
    # Observability
    log_level: str = "INFO"
    metrics_enabled: bool = True
    
    # Startup
    startup_timeout_seconds: int = 60

settings = Settings()

@app.on_event("startup")
async def validate_settings():
    """Reject startup if required config is missing."""
    if not settings.openai_api_key:
        raise ValueError("ANONREQ_OPENAI_API_KEY is required")
```

#### Hot-Reload Mechanism

```python
import yaml
from pathlib import Path
from watchfiles import awatch

class ConfigWatcher:
    """
    Watches config files for changes and swaps them atomically.
    Uses a read-copy-update (RCU) pattern: new config is built
    in full, then swapped via a single pointer assignment.
    """
    
    def __init__(self, config_dir: Path):
        self._recognizers: list[dict] = []
        self._exclusion_list: set[str] = set()
        self._lock = asyncio.Lock()
        self._config_dir = config_dir
    
    async def start_watching(self):
        async for changes in awatch(self._config_dir):
            async with self._lock:
                new_recognizers = self._load_recognizers()
                new_exclusions = self._load_exclusions()
                # Atomic swap
                self._recognizers = new_recognizers
                self._exclusion_list = new_exclusions
```

---

### Build Order — Component Dependencies

```
Phase 1: Foundation
  ├── Project scaffold (pyproject.toml, Dockerfile, docker-compose.yml)
  ├── Settings / Configuration module
  ├── Logging setup (structured JSON to stdout)
  └── Health endpoint + startup validation
  
Phase 2: Core Pipeline (Non-Streaming)
  ├── Text Extractor (pure function, no deps)
  ├── Pydantic request/response schemas
  ├── Detection Engine Client (HTTPX → Presidio)
  ├── Tokenization Engine (spans → tokens, reverse-order replacement)
  ├── Cache Manager (Valkey async client)
  ├── Restoration Engine (token → value replacement)
  ├── Provider Adapter: OpenAI passthrough (native format, simplest path)
  └── Orchestrator: POST /v1/chat/completions handler
  
Phase 3: Fail-Secure (must follow Phase 2)
  ├── Error boundary middleware
  ├── Health probe integration (detection + cache checks)
  ├── Pre-flight startup probes
  └── Timeout handling on detection

Phase 4: Multi-Provider
  ├── Provider Adapter: Anthropic (OpenAI → Anthropic Messages API)
  ├── Provider Adapter: Gemini (OpenAI → contents[])
  ├── Provider Adapter: Ollama (OpenAI passthrough with custom base_url)
  ├── Model routing logic (model name → provider)
  └── GET /v1/models endpoint

Phase 5: SSE Streaming
  ├── Tail_Buffer implementation
  ├── State machine (SCAN → PENDING → FLUSH)
  ├── Streaming route path (separate from non-streaming)
  ├── Pre-fetch Mapping at stream start
  ├── TTL extension during long streams
  └── Post-stream verification

Phase 6: Multi-Locale Detection
  ├── Locale-specific recognizer bundles (8 locales)
  ├── Checksum validation per locale
  ├── X-AnonReq-Locale header parsing
  ├── Multi-locale merging logic
  └── Presidio recognizer config injection

Phase 7: Configuration & Observability
  ├── Hot-reload config watcher
  ├── Custom recognizer/exclusion list support
  ├── Prometheus /metrics endpoint
  ├── Compliance presets
  ├── Response-side token verification
  └── Append-only audit trail
```

**Dependency graph:**

```
Phase 1 (no deps)
    │
    ▼
Phase 2 (needs Phase 1)
    │
    ├──────────────┐
    ▼              ▼
Phase 3        Phase 4
(needs Ph2)    (needs Ph2)
    │              │
    └──────┬───────┘
           ▼
       Phase 5
    (needs Ph3 + Ph4)
           │
           ▼
       Phase 6
    (needs Ph2)
           │
           ▼
       Phase 7
    (needs all)
```

---

### Testing Architecture

#### Test Pyramid for AnonReq

```
                ┌──────────┐
                │Property- │  8 tests (Req 16) — Hypothesis
                │Based     │  round-trip correctness
                │Tests     │  token uniqueness/dedup
                │          │  fail-secure invariants
                │          │  locale checksum
                │          │  no-PII-in-logs
                └────┬─────┘  streaming round-trip
                     │         cross-request randomization
                ┌────┴─────┐
                │Integration│  20-30 tests
                │Tests     │  Full pipeline: request→detect→tokenize→cache→restore
                │          │  Valkey container via testcontainers
                │          │  Fake Presidio (responses mock)
                │          │  SSE streaming end-to-end
                └────┬─────┘
                     │
                ┌────┴─────┐
                │Unit Tests│  50-80 tests
                │          │  Tokenization engine (pure logic)
                │          │  Restoration engine (pure logic)
                │          │  Tail_Buffer (state machine)
                │          │  Text extractor (flattening logic)
                │          │  Provider adapters (schema translation)
                │          │  Configuration validation
                │          │  Case-insensitive/bracket-optional matching
                └──────────┘
```

#### Test Configuration

```python
# conftest.py
import pytest
from hypothesis import strategies as st

# Hypothesis strategies for property tests
text_with_pii = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
    min_size=10, max_size=1000
)

@pytest.fixture
def fake_presidio():
    """Mock Presidio Analyzer via responses / respx."""
    ...

@pytest.fixture
async def valkey_container():
    """Testcontainers Redis for integration tests."""
    ...

@pytest.fixture
def test_client():
    """FastAPI TestClient."""
    ...
```

#### Property-Based Tests (Hypothesis)

```python
# tests/property/test_roundtrip.py
from hypothesis import given, assume
from hypothesis.strategies import ...

@given(text_with_pii)
def test_roundtrip_correctness(text: str):
    """Round-trip: anonymize → restore → byte-for-byte match."""
    mapping = {}
    tokenized = tokenize(text, detect(text), mapping)
    restored = restore(tokenized, mapping)
    assert restored == text

@given(text_with_pii)
def test_token_uniqueness(text: str):
    """N distinct values → N distinct tokens."""
    mapping = {}
    tokenized = tokenize(text, detect(text), mapping)
    entity_values = extract_entity_values(detect(text))
    tokens_used = re.findall(r'\[([A-Z]+_\d+)\]', tokenized)
    assert len(set(tokens_used)) == len(set(entity_values))

@given(text_with_pii, text_with_pii)
def test_cross_request_randomization(t1: str, t2: str):
    """Same entity in two sessions → different tokens (P > 1 - 2^-32)."""
    ...
```

#### Testing Rules

| Test Type | Dependencies | Speed | Fail on | When to Run |
|-----------|-------------|-------|---------|-------------|
| Unit | None | <1ms | Logic errors | Every commit |
| Integration | Mock Presidio + testcontainers Valkey | <5s | Pipeline errors | Every commit |
| Property-based | None (pure functions) | <60s | Invariant violations | Every commit |
| E2E | Full Docker Compose stack | <30s | Deployment errors | CI only |
| Bias/Fairness | Test datasets | <120s | Recall disparity >5% | CI only (weekly) |

---

### Patterns to Follow

#### Pattern 1: Pipeline as Composable Steps

```python
# Each step is a standalone async function with clear input/output types.
# Steps are composed by the route handler; no step calls another step directly.

class PipelineStep(Protocol):
    async def __call__(self, ctx: RequestContext) -> RequestContext: ...

class RequestContext:
    session_id: str
    original_body: ChatRequest
    text_blocks: list[tuple[str, str]]  # (field_path, text)
    detections: list[RecognizerResult]
    tokenized_body: dict
    mapping: dict[str, str]
    provider_response: dict
    restored_body: dict
    errors: list[Exception]

async def pipeline(request: Request, body: ChatRequest) -> Response:
    ctx = RequestContext(session_id=uuid4(), original_body=body)
    steps = [
        extract_text_step,
        detect_pii_step,
        tokenize_step,
        cache_write_step,
        provider_call_step,
        restore_step,
        verify_step,
        audit_step,
    ]
    for step in steps:
        ctx = await step(ctx)
        if ctx.errors:
            return fail_secure(ctx)  # HTTP 500
    return JSONResponse(ctx.restored_body)
```

#### Pattern 2: Provider Adapter Strategy

```python
# Provider adapters implement a common protocol.
# Registration-based provider selection — no if/elif chain.

class ProviderAdapter(ABC):
    @abstractmethod
    def translate_request(self, openai_body: dict) -> dict: ...
    @abstractmethod
    def parse_response(self, raw: dict) -> dict: ...
    @abstractmethod
    def parse_stream_event(self, sse_line: str) -> dict: ...

class OpenAIAdapter(ProviderAdapter): ...
class AnthropicAdapter(ProviderAdapter): ...
class GeminiAdapter(ProviderAdapter): ...
class OllamaAdapter(ProviderAdapter): ...

ADAPTER_REGISTRY: dict[str, type[ProviderAdapter]] = {
    "gpt-4": OpenAIAdapter,
    "gpt-4o": OpenAIAdapter,
    "claude-3-opus": AnthropicAdapter,
    "claude-3-sonnet": AnthropicAdapter,
    "gemini-1.5-pro": GeminiAdapter,
    "ollama/*": OllamaAdapter,  # wildcard match
}

def get_adapter(model: str) -> ProviderAdapter:
    for key, adapter_cls in ADAPTER_REGISTRY.items():
        if key.endswith("/*"):
            prefix = key[:-2]
            if model.startswith(prefix):
                return adapter_cls()
        elif model == key:
            return adapter_cls()
    raise UnsupportedModelError(model)
```

#### Pattern 3: Async HTTP Client Lifecycle (HTTPX)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared HTTPX clients at app startup."""
    async with httpx.AsyncClient(timeout=5.0) as presidio_client:
        async with httpx.AsyncClient(timeout=60.0) as llm_client:
            app.state.presidio_client = presidio_client
            app.state.llm_client = llm_client
            yield

app = FastAPI(lifespan=lifespan)
```

---

### Anti-Patterns to Avoid

#### Anti-Pattern 1: Middleware-Based Request Body Modification

**What:** Modifying the request body in `@app.middleware("http")` by hacking `request._receive`.
**Why bad:** Fragile, breaks if FastAPI/Starlette internals change, impossible to handle SSE streaming bodies, dual-read issues.
**Instead:** Use a route handler that receives the parsed Pydantic model and passes it through the pipeline.

#### Anti-Pattern 2: Loading spaCy/Presidio In-Process

**What:** `from presidio_analyzer import AnalyzerEngine` inside the gateway process.
**Why bad:** ~1-2GB memory per worker, NER model loading on startup (30-60s), model crash takes down gateway.
**Instead:** Run Presidio as a sidecar container. Gateway calls it via HTTP.

#### Anti-Pattern 3: Per-Chunk Cache Lookups During SSE Streaming

**What:** Calling `HGET anonreq:{session_id}` for every SSE chunk.
**Why bad:** ~1ms per round-trip × 500 chunks = 500ms overhead added to stream. Under memory pressure, Valkey eviction could delete mapping mid-stream.
**Instead:** `HGETALL` once at stream start, hold entire mapping in memory.

#### Anti-Pattern 4: Using `BaseHTTPMiddleware` for SSE Streaming Responses

**What:** Trying to wrap a `StreamingResponse` in `BaseHTTPMiddleware.dispatch`.
**Why bad:** `BaseHTTPMiddleware` buffers the entire response body before running post-processing — defeats streaming. This is a known Starlette limitation (issue #1070).
**Instead:** Handle streaming entirely within the route handler/async generator.

#### Anti-Pattern 5: Thread Pool for Presidio Calls

**What:** Using `run_in_threadpool` or `ThreadPoolExecutor` to call Presidio synchronously.
**Why bad:** Thread pool context switching overhead, GIL contention, harder to timeout properly.
**Instead:** Use `httpx.AsyncClient` for fully asynchronous communication with Presidio's HTTP endpoint.

---

### Scalability Considerations

| Concern | Single Gateway | Multi-Replica | Notes |
|---------|---------------|---------------|-------|
| **Session state** | In-memory + Valkey | Valkey shared across replicas | Session mapping must be in Valkey so any replica can restore any session |
| **Presidio scaling** | Single sidecar | Multiple Presidio replicas behind round-robin | Presidio is stateless; scale horizontally for throughput |
| **Valkey scaling** | Single instance | Valkey Cluster or Redis Sentinel | `allkeys-lru` eviction handles memory pressure |
| **Streaming affinity** | Not required | Not required | Because mapping is in Valkey, any replica can handle any stream |
| **Connection limit** | OS file descriptors | Per-replica limits | SSE streams hold long-lived connections; plan connection limits per instance |

At 10K users: 1 gateway replica, 2 Presidio replicas, 1 Valkey. At 1M users: 10+ gateway replicas, 20+ Presidio replicas, Valkey Cluster (3 shards, 3 replicas).

---

### Sources

- **FastAPI Server-Sent Events documentation** (fastapi.tiangolo.com/tutorial/server-sent-events) — SSE streaming with EventSourceResponse, high confidence
- **Microsoft Presidio Analyzer documentation** (microsoft.github.io/presidio/analyzer/) — AnalyzerEngine API, Docker deployment, sidecar pattern, high confidence
- **FastAPI SSE + StreamingResponse lifecycle analysis** (readoss.com/en/fastapi/fastapi/sse-jsonl-streaming-fastapi-response-lifecycles) — ASGI streaming internals, producer/consumer architecture, high confidence
- **Hypothesis property-based testing documentation** (hypothesis.readthedocs.io) — strategies, stateful testing, shrinking, high confidence
- **Starlette middleware / BaseHTTPMiddleware limitations** — GitHub issues #1070, community knowledge, medium confidence
- **HTTPX AsyncClient best practices** (python-httpx.org) — async HTTP for FastAPI, connection pooling, lifespan management, high confidence
