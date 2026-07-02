# AnonReq — Low Level Design (LLD)

**Version:** 1.0  
**Status:** Draft  
**Source Requirements:** `req/requirements.md`, `req/requirements_v2.md`  
**Phase Plans:** `.planning/phases/01-21`  

---

## Table of Contents

1. [Package Structure](#1-package-structure)
2. [Data Models](#2-data-models)
3. [Component Interfaces](#3-component-interfaces)
4. [Key Algorithms](#4-key-algorithms)
5. [Pipeline Stage Definitions](#5-pipeline-stage-definitions)
6. [Database Schemas](#6-database-schemas)
7. [API Contracts](#7-api-contracts)
8. [Error Handling Strategy](#8-error-handling-strategy)
9. [Configuration Schema](#9-configuration-schema)
10. [Test Architecture](#10-test-architecture)

---

## 1. Package Structure

```
src/anonreq/
├── __init__.py                  # Package docstring
├── __about__.py                 # __version__ = "0.1.0"
├── main.py                      # FastAPI app factory, lifespan, router registration
├── config.py                    # Pydantic Settings, YAML provider registry loader
│
├── models/
│   ├── __init__.py
│   ├── chat.py                  # ChatRequest, ChatMessage, ToolCall — Pydantic request models
│   ├── processing_context.py    # ProcessingContext — per-request pipeline state
│   ├── detection.py             # DetectionResult, TextNode
│   ├── tokenization.py          # TokenMapping, TokenizationResult, TOKEN_PATTERN
│   ├── classification.py        # ClassificationLevel, ClassificationResult, ENTITY_CLASSIFICATION_MAP
│   └── audit.py                 # AuditEvent dataclass, compute_event_hash()
│
├── api/
│   └── v1/
│       ├── __init__.py
│       ├── chat.py              # POST /v1/chat/completions — non-streaming + streaming branch
│       ├── health.py            # GET /health
│       ├── models.py            # GET /v1/models
│       └── governance.py        # Phase 14: GET/POST /v1/governance/*
│
├── pipeline/
│   ├── __init__.py
│   ├── manager.py               # PipelineManager — orchestrates stage execution
│   ├── extraction.py            # TextExtractor — recursive JSON message walker
│   ├── stages.py                # Stage definitions: ClassificationStage, DetectionStage, etc.
│   └── provider.py              # ForwardingGuard — pre-forward validation
│
├── classification/
│   ├── __init__.py
│   ├── engine.py                # ClassificationEngine — YAML rule evaluator, 4-tier action
│   └── loader.py                # ClassificationRuleLoader — YAML → Rule objects
│
├── detection/
│   ├── __init__.py
│   ├── regex_patterns.py        # PATTERNS dict, luhn_checksum(), ENTITY_SPECIFICITY, TIER_1/2
│   ├── regex_detector.py        # RegexDetector — pattern matching on text
│   ├── presidio_client.py       # PresidioClient — async HTTP to Presidio Analyzer sidecar
│   ├── span_arbiter.py          # SpanArbiter — regex+NER merge with specificity ranking
│   └── exclusion_list.py        # ExclusionList — exact + wildcard suppression
│
├── tokenization/
│   ├── __init__.py              # Exports Tokenizer, TOKEN_PATTERN
│   ├── tokenizer.py             # Tokenizer — dedup, reverse-offset, random seed
│   └── restorer.py              # Restorer — non-streaming restoration (text replacement)
│
├── cache/
│   ├── __init__.py
│   └── manager.py               # CacheManager — Valkey/Redis abstraction, TTL, HGETALL
│
├── streaming/
│   ├── __init__.py
│   ├── stream_event.py          # StreamEvent, EventType, FinishReason, ToolCallDelta
│   ├── tail_buffer.py           # TailBuffer FSM — COLLECTING/MATCHING/FLUSHING/TERMINATED
│   ├── restoration.py           # StreamingRestorationStage — case-insensitive + bracket-optional
│   ├── emitter.py               # SSEEmitter — SSE frame formatting, anti-buffering headers
│   └── cleanup.py               # SessionCleanup — idempotent cleanup with _cleaned flag
│
├── providers/
│   ├── __init__.py
│   ├── registry.py              # ProviderRegistry — adapter lookup by provider name, aliases
│   ├── adapter.py               # ProviderAdapter ABC — translate_request, execute, stream_events
│   ├── openai.py                # OpenAIAdapter
│   ├── anthropic.py             # AnthropicAdapter
│   ├── gemini.py                # GeminiAdapter
│   └── ollama.py                # OllamaAdapter
│
├── middleware/
│   ├── __init__.py
│   ├── auth.py                  # API key authentication middleware
│   ├── content_type.py          # ContentTypeMiddleware — routes by Content-Type header
│   └── context.py               # RequestContext middleware — request_id, tenant_id
│
├── multimodal/
│   ├── __init__.py
│   ├── models.py                # ContentType, UnifiedDetectionResult, AnalyzerResult
│   ├── dispatcher.py            # ContentTypeDispatcher — routes by MIME type
│   ├── json_analyzer.py         # JsonAnalyzer — recursive tree walk, key-pattern detection
│   ├── multipart_analyzer.py    # MultipartAnalyzer — per-part content-type routing
│   └── limits.py                # PayloadLimits, validate_payload_limits()
│
├── services/
│   ├── audit_chain.py           # AuditChainService — SHA-384 hash chaining, event ingestion
│   ├── chain_anchor.py          # ChainAnchorService — daily anchoring, HMAC-SHA384 signing
│   └── classification_engine.py # ClassificationEngine (Phase 12) — 5-level deterministic max
│
├── audit/
│   ├── __init__.py
│   └── logger.py                # Structured JSON audit logger, field allowlist
│
├── metrics/
│   ├── __init__.py
│   └── exporter.py              # Prometheus counters, histograms, gauges
│
├── locale/
│   ├── __init__.py
│   ├── registry.py              # LocaleRegistry — locale code → LocaleBundle
│   ├── negotiator.py            # LocaleNegotiator — X-AnonReq-Locale header → merged recognizers
│   └── checksum.py              # ChecksumValidatorRegistry — ISO 7064, Luhn, Verhoeff validators
│
├── compliance/
│   ├── __init__.py
│   └── presets.py               # CompliancePresetEngine — startup validation, merge, hard fail
│
├── policy/                      # Phase 8 Enterprise Policy Engine
│   ├── __init__.py
│   ├── engine.py                # PolicyEngine — PDP #1 and PDP #2
│   ├── models.py                # PolicyRule, PolicyDecision, TenantPolicy
│   └── loader.py                # PolicyLoader — YAML tenant policies
│
├── ai_firewall/                 # Phase 10 AI Security Firewall
│   ├── __init__.py
│   ├── injector.py              # PromptInjectorDetector
│   ├── jailbreak.py             # JailbreakDetector
│   └── models.py                # FirewallResult, ThreatScore
│
├── dataloss/                    # Phase 13 DLP
│   ├── __init__.py
│   ├── scanner.py               # DLPContentScanner
│   └── rules.py                 # DLPRule, DLPClassification
│
├── governance/                  # Phase 14 AI Governance
│   ├── __init__.py
│   └── oversight.py             # GovernanceOversight — policy attestation, audit trails
│
└── siem/                        # Phase 20 SIEM Integration
    ├── __init__.py
    ├── forwarder.py             # SIEMEventForwarder
    └── formats.py               # CEF, LEEF, JSON format producers
```

### Package Dependency Rules

| Module | Depends On | Never Imports |
|--------|-----------|---------------|
| `models/` | stdlib, pydantic | Any service/engine module |
| `pipeline/` | `models/`, `classification/`, `detection/`, `tokenization/`, `providers/` | `services/audit_chain.py` |
| `detection/` | `models/detection.py`, `config.py`, `httpx` | `tokenization/`, `providers/` |
| `tokenization/` | stdlib (`re`, `secrets`) only | `detection/`, `providers/` |
| `streaming/` | `models/`, `cache/` | `detection/`, `classification/` |
| `providers/` | `models/`, `config.py`, `httpx` | `detection/`, `pipeline/` |
| `multimodal/` | `detection/`, `models/` | `providers/` |
| `services/` | `models/audit.py`, SQLAlchemy, `minio` | `pipeline/`, `detection/` |

---

## 2. Data Models

### 2.1 ProcessingContext

The single per-request context object propagated through every pipeline stage.

```python
@dataclass
class ProcessingContext:
    request_id: str
    tenant_id: str
    context_id: str                    # UUIDv7

    # Input
    original_request: dict
    text_nodes: list[dict]             # [{"path": str, "role": str, "value": str}]
    content_type: ContentType          # For multimodal routing

    # Pipeline state
    classification_result: dict | None = None     # {"action": str, "matched_rule_ids": [...]}
    detections: list[dict] | None = None           # [{"entity_type", "start", "end", "score", "source"}]
    token_mappings: dict[str, str] | None = None   # {"[EMAIL_1]": "user@example.com"}
    transformed_request: dict | None = None        # Sanitized request body sent to provider

    # Provider
    provider: str | None = None
    model: str | None = None
    provider_request: ProviderRequest | None = None

    # Output (non-streaming)
    provider_response: ProviderResponse | None = None
    restored_response: RestoredResponse | None = None

    # Output (streaming)
    stream_events: AsyncIterator[StreamEvent] | None = None
    stream_finished: bool = False
    terminal_state: str | None = None

    # Classification (Phase 12)
    classification_result_v2: ClassificationResult | None = None

    # Audit
    audit_metadata: dict = field(default_factory=dict)
```

### 2.2 Detection Models

```python
@dataclass
class TextNode:
    path: str                  # e.g. "messages[0].content"
    role: str                  # "user", "assistant", "system", "tool"
    value: str                 # The extracted text

@dataclass
class DetectionResult:
    entity_type: str           # "EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", etc.
    start: int                 # Character offset in original text
    end: int                   # Character offset in original text
    score: float               # 1.0 for regex, 0.0-1.0 for NER
    source: str                # "regex" or "ner"
    locale_id: str | None = None     # For multi-locale detection
    classification_level: str | None = None  # Set by Phase 12 ClassificationEngine
```

### 2.3 Tokenization Models

```python
TOKEN_PATTERN = re.compile(r'\[([A-Z][A-Z_]{0,19})_(\d+)\]')

@dataclass
class TokenMapping:
    token: str                 # "[EMAIL_1]"
    original_value: str        # "user@example.com"
    entity_type: str           # "EMAIL_ADDRESS"
    session_id: str

@dataclass
class TokenizationResult:
    tokenized_text: str
    mappings: dict[str, str]   # token → original_value
    per_type_counts: dict[str, int]
```

### 2.4 Classification Models

```python
# Phase 2 — Action-based classification
@dataclass
class ClassificationRule:
    id: str
    enabled: bool
    version: int
    name: str
    action: str                    # "BLOCK" | "ROUTE_LOCAL" | "ANONYMIZE" | "PASS"
    metadata: dict
    conditions: dict               # roles: list[str], regex: list[str], keywords: list[str]

@dataclass
class ClassResult:
    action: str
    matched_rule_ids: list[str]
    matched_rule_versions: list[int]

# Phase 12 — Sensitivity-level classification
class ClassificationLevel(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3
    HIGHLY_RESTRICTED = 4

@dataclass
class ClassificationResult:
    highest: ClassificationLevel
    labels: list[str]
    detected_levels: list[ClassificationLevel]
    client_override: bool = False
    client_asserted_level: ClassificationLevel | None = None
```

### 2.5 Streaming Models

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
    type: str | None = None
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
    model_config = {"extra": "ignore"}
```

### 2.6 Provider Models

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

### 2.7 Multimodal Models

```python
class ContentType(str, Enum):
    TEXT_PLAIN = "text/plain"
    APPLICATION_JSON = "application/json"
    MULTIPART_FORM_DATA = "multipart/form-data"
    UNKNOWN = "unknown"

class UnifiedDetectionResult(BaseModel):
    content_type: ContentType
    entities: list[dict] = []        # Phase 2 DetectionResult dicts
    risk_score: float = 0.0
    classification: str = "Internal"
    analyzer_metadata: dict = {}

class AnalyzerResult(BaseModel):
    source_analyzer: str
    content_type: ContentType
    detection_result: UnifiedDetectionResult
    should_process: bool = True
    action: str = "ANONYMIZE"       # "ANONYMIZE" | "ROUTE_LOCAL" | "BLOCK"
```

### 2.8 Audit Models

```python
@dataclass
class AuditEvent:
    event_id: str
    prev_hash: str | None
    hash: str
    timestamp: datetime
    tenant_id: str
    request_id: str | None
    policy_id: str | None
    decision: str | None
    provider: str | None
    latency_ms: int | None
    event_type: str                  # "request", "config_change", "policy_decision"
    operator_id: str | None
    change_type: str | None
    prev_value_hash: str | None
    new_value_hash: str | None
    metadata_json: str | None
    retention_days: int = 2557       # 7 years default
```

### 2.9 Chat Request (OpenAI-Compatible Input)

```python
class ChatMessage(BaseModel):
    role: str                                # "system" | "user" | "assistant" | "tool"
    content: str | list | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None

class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[dict] | None = None
    tool_choice: str | dict | None = None
    stop: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Non-standard extensions
    user: str | None = None               # tenant_id via header usually

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: dict | None = None

class Choice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str | None = None
```

---

## 3. Component Interfaces

### 3.1 PipelineManager

```python
class PipelineManager:
    """Orchestrates the execution of all pipeline stages."""

    def __init__(
        self,
        text_extractor: TextExtractor,
        classification_engine: ClassificationEngine,
        detection_provider: DetectionProvider,
        tokenizer: Tokenizer,
        forwarding_guard: ForwardingGuard,
        provider_registry: ProviderRegistry,
        cache_manager: CacheManager,
        restorer: Restorer,
        audit_logger: AuditLogger,
        metrics: MetricsExporter,
    ): ...

    async def execute(self, request: ChatRequest, tenant_id: str) -> Response:
        """Execute the full non-streaming pipeline."""
        # 1. Extract text nodes from request
        # 2. Run ClassificationStage
        # 3. Run DetectionStage
        # 4. Run TokenizationStage
        # 5. Run ForwardingGuard
        # 6. Run ProviderStage (translate, execute, translate response)
        # 7. Run RestorationStage
        # 8. Emit audit log & metrics
        # 9. Return RestoredResponse
        ...

    async def execute_streaming(self, request: ChatRequest, tenant_id: str) -> StreamingResponse:
        """Execute the streaming pipeline by branching on stream=True."""
        # 1-5: Same as non-streaming
        # 6. ProviderStage.stream_events()
        # 7. Wire TailBuffer → StreamingRestorationStage → SSEEmitter
        # 8. Emit audit log & metrics in cleanup()
        ...
```

### 3.2 ClassificationEngine (Phase 2 — Action-based)

```python
class ClassificationEngine:
    """YAML-rule-based 4-tier classification evaluator."""

    def __init__(self, rules: list[ClassificationRule], default_action: str = "PASS"): ...

    def classify(self, text_nodes: list[dict]) -> ClassResult:
        """Evaluate rules in action-priority order: BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS.
        First matching rule wins. Returns action, matched_rule_ids, matched_rule_versions."""
        # Algorithm: iterate action order, for each action iterate rules,
        # first match returns, else default_action
        ...
```

### 3.3 RegexDetector

```python
class RegexDetector:
    """Deterministic PII detection via pre-compiled regex patterns."""

    def __init__(self, patterns: dict[str, re.Pattern] | None = None): ...

    def detect(self, text: str) -> list[dict]:
        """Run all patterns on text, return [{"entity_type", "start", "end", "score": 1.0, "source": "regex"}]."""
        # CREDIT_CARD patterns require Luhn checksum pass
        # Score always 1.0 (deterministic)
        ...
```

### 3.4 PresidioClient

```python
class PresidioClient:
    """Async HTTP client to Presidio Analyzer sidecar with concurrency control."""

    def __init__(self, base_url: str, timeout: float = 2.0, max_concurrency: int = 10): ...

    async def analyze(self, text: str, language: str = "en",
                      entities: list[str] | None = None,
                      score_threshold: float = 0.7) -> list[dict]: ...

    async def analyze_text_nodes(self, text_nodes: list[dict], language: str = "en",
                                  score_threshold: float = 0.7) -> list[list[dict]]:
        """Analyze multiple text nodes concurrently via asyncio.gather with semaphore.
        Skips nodes < 20 chars (regex only per D-34)."""
        ...

    async def health_check(self) -> dict: ...
    async def close(self) -> None: ...
```

### 3.5 SpanArbiter

```python
class SpanArbiter:
    """Merges regex and NER detection results with specificity-based arbitration."""

    @staticmethod
    def merge(regex_results: list[dict], ner_results: list[dict]) -> list[dict]:
        """Merge with overlap resolution rules:
        - Exact overlap: regex wins
        - Nested: most specific entity type wins
        - Partial: most specific entity type wins
        - Non-overlapping: both kept
        """
        ...

    @staticmethod
    def _overlap_type(a: dict, b: dict) -> str | None:
        """Returns 'exact', 'nested', 'partial', or None."""
        ...
```

### 3.6 Tokenizer

```python
class Tokenizer:
    """Per-session tokenizer with deduplication and reverse-offset replacement."""

    def __init__(self): ...

    def initialize_session(self) -> None:
        """Reset state, generate new random seed via secrets.randbits(32)."""
        ...

    def tokenize(self, text: str, detections: list[dict]) -> tuple[str, dict[str, str]]:
        """Replace detected PII spans with [TYPE_N] tokens.
        Returns (tokenized_text, {token: original_value}).
        - Sort detections descending by start (reverse-offset)
        - Dedup: same value → same token
        - Per-type atomic counters
        - Token index = (seed & 0x3FFFFFFF) + counter
        - No detections → (text, {}) fast path
        """
        ...

    def get_mapping(self) -> dict[str, str]: ...
```

### 3.7 ProviderAdapter (ABC)

```python
class ProviderAdapter(ABC):
    """Abstract base for provider-specific schema translators."""

    @property
    def provider_name(self) -> str: ...

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def translate_request(self, ctx: ProcessingContext) -> ProviderRequest:
        """Convert canonical request to provider-specific format."""
        ...

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        """Non-streaming HTTP call to provider API."""
        ...

    async def stream_events(self, request: ProviderRequest) -> AsyncIterator[StreamEvent]:
        """Streaming HTTP call, normalize chunks to StreamEvent."""
        ...

    def translate_response(self, ctx: ProcessingContext, response: ProviderResponse) -> RestoredResponse:
        """Convert provider-specific response back to canonical format."""
        ...
```

### 3.8 TailBuffer FSM

```python
class BufferState(str, Enum):
    COLLECTING = "COLLECTING"
    MATCHING = "MATCHING"
    FLUSHING = "FLUSHING"
    TERMINATED = "TERMINATED"

class TailBuffer:
    """Finite state machine that reassembles text chunks, never emitting partial tokens."""

    TAIL_WINDOW_CHARS: int = 128       # MAX_TOKEN_LENGTH * 2
    MAX_BUFFER_CHARS: int = 2048
    MAX_BUFFER_AGE_MS: int = 1000

    def __init__(self): ...

    async def ingest(self, event: StreamEvent) -> AsyncIterator[str]:
        """Process TEXT_DELTA through state machine.
        Non-TEXT_DELTA events bypass FSM and yield as-is."""
        ...

    def terminate(self) -> None: ...
    def flush_remaining(self) -> str: ...
```

### 3.9 CacheManager

```python
class CacheManager:
    """Valkey/Redis abstraction for ephemeral token mapping storage."""

    def __init__(self, redis_url: str, ttl: int = 600): ...

    async def store_mapping(self, tenant_id: str, session_id: str, mapping: dict[str, str]) -> None:
        """Store token→value mapping in a HSET key 'anonreq:{tenant_id}:{session_id}'."""

    async def get_mapping(self, tenant_id: str, session_id: str) -> dict[str, str]:
        """HGETALL → dict. Used by RestorationStage at stream start."""

    async def delete_mapping(self, tenant_id: str, session_id: str) -> None:
        """DEL the key. Called by SessionCleanup post-response."""

    async def extend_ttl(self, tenant_id: str, session_id: str) -> None:
        """EXPIRE to reset TTL. Called at 80% elapsed stream time."""
```

### 3.10 LocaleNegotiator

```python
class LocaleNegotiator:
    """Resolves X-AnonReq-Locale header to merged recognizer set."""

    def __init__(self, registry: LocaleRegistry): ...

    async def negotiate(self, header: str | None) -> RecognizerSet:
        """Parse header, resolve locale codes to bundles, merge recognizers.
        Falls back to ['en'] if header missing."""
        ...

class LocaleRegistry:
    """Startup-loaded locale bundles from config/locales/*.yaml."""

    def register(self, code: str, bundle: LocaleBundle) -> None: ...
    def resolve(self, codes: list[str]) -> list[LocaleBundle]: ...

class LocaleBundle:
    code: str
    entity_types: list[EntityTypeConfig]
    checksum: ChecksumConfig | None = None
```

### 3.11 ClassificationEngine (Phase 12 — Sensitivity)

```python
class ClassificationEngineV2:
    """Deterministic max-algorithm classification engine (Phase 12)."""

    def __init__(self, entity_map: dict[str, ClassificationLevel] | None = None): ...

    async def classify(self, entity_types: list[str]) -> ClassificationResult:
        """Given detected entity types, return highest sensitivity level.
        - Unknown types → INTERNAL (with log warning)
        - Empty input → INTERNAL
        - Deterministic: same input → same output always
        """
        levels = [self._entity_map.get(et.upper(), ClassificationLevel.INTERNAL) for et in entity_types]
        highest = max(levels)
        return ClassificationResult(highest=highest, labels=entity_types, detected_levels=levels)

    async def classify_with_client_override(
        self, entity_types: list[str], client_level: ClassificationLevel | None = None
    ) -> ClassificationResult:
        """Client-asserted override: increase only. Higher of detected vs client wins."""
```
```

### 3.12 AuditChainService

```python
class AuditChainService:
    """Immutable audit event ingestion with SHA-384 hash chaining."""

    def __init__(self, db_session_factory, config: AuditConfig): ...

    async def store_event(self, event: AuditEvent) -> AuditEvent:
        """Compute hash, link to latest event (SELECT...FOR UPDATE), insert."""

    async def verify_chain(self, tenant_id: str, from_id: int | None = None) -> ChainVerificationResult:
        """Walk chain, verify each hash link."""

    async def get_latest_event(self, tenant_id: str) -> AuditEvent | None: ...
    async def get_events(self, tenant_id: str, limit: int = 100, offset: int = 0,
                         event_type: str | None = None) -> list[AuditEvent]: ...
```

### 3.13 ContentTypeDispatcher

```python
class ContentTypeDispatcher:
    """Routes requests to the correct content analyzer based on Content-Type."""

    def __init__(self, json_analyzer: JsonAnalyzer, multipart_analyzer: MultipartAnalyzer,
                 text_analyzer=None): ...

    async def dispatch(self, content_type: str, body: bytes, ctx) -> AnalyzerResult:
        """Parse Content-Type, strip charset, route to analyzer.
        Unknown types return AnalyzerResult(action="ROUTE_LOCAL")."""
        ...

    def _parse_content_type(self, header: str) -> tuple[ContentType, str]: ...
```

---

## 4. Key Algorithms

### 4.1 Classification Action Precedence (Phase 2)

The classification engine evaluates rules in strict action-priority order. The first matching rule determines the entire request's disposition.

```
Algorithm: classify(text_nodes)
  Input:  text_nodes — list of {path, role, value}
  Output: {action, matched_rule_ids, matched_rule_versions}

  for action in [BLOCK, ROUTE_LOCAL, ANONYMIZE, PASS]:
    for rule in rules where rule.action == action and rule.enabled:
      if rule.matches(text_nodes):
        return {action: action, matched_rule_ids: [rule.id], matched_rule_versions: [rule.version]}
  return {action: "PASS", matched_rule_ids: [], matched_rule_versions: []}
```

Rule matching logic per `ClassificationRule.matches(text_nodes)`:
```
  for node in text_nodes:
    if rule.conditions.roles is non-empty AND node.role not in rule.conditions.roles:
      continue                          # Role filter not satisfied
    if any(regex matches node.value) OR any(keyword in node.value.lower()):
      return True                       # Content condition satisfied
  return False
```

### 4.2 Span Arbitration

Merges regex (deterministic, score=1.0) and NER (fuzzy, score=0.0–1.0) results.

```
Algorithm: merge(regex_results, ner_results)
  Input:  regex_results — list of {entity_type, start, end, score, source:"regex"}
          ner_results   — list of {entity_type, start, end, score, source:"ner"}
  Output: merged list sorted by start position

  1. Tag both input lists with _source field
  2. Combine into single list
  3. Sort by start ASC, then score DESC
  4. Initialize accepted = []
  5. For each span in combined:
     overlap = find_overlap(span, accepted)
     if overlap is None:
       accepted.append(span)
     elif overlap == "exact":
       regex_wins(span, accepted)      # Replace accepted if span is regex
     elif overlap == "nested":
       more_specific_wins(span, accepted)  # Higher ENTITY_SPECIFICITY wins
     elif overlap == "partial":
       more_specific_wins(span, accepted)
  6. Strip _source tags
  7. Return accepted sorted by start ASC
```

ENTITY_SPECIFICITY ranking (higher = more specific):
```
  API_KEY=100, EMAIL_ADDRESS=90, PHONE_NUMBER=80, CREDIT_CARD=75,
  IBAN_CODE=70, US_SSN=65, PASSPORT=62, BANK_ACCOUNT=60,
  URL=55, IP_ADDRESS=50, PERSON=40, DATE_TIME=35, LOCATION=30, ORGANIZATION=25
```

### 4.3 Tokenization with Reverse-Offset

Prevents position drift when replacing spans with tokens of different lengths.

```
Algorithm: tokenize(text, detections)
  Input:  text        — string to anonymize
          detections  — list of {entity_type, start, end, score, source}
  Output: (tokenized_text, {token: original_value})

  1. if detections is empty: return (text, {})           # TOKN-06/07 fast path
  2. Sort detections by start DESC                        # Right-to-left replacement
  3. Initialize tokenized = text, mapping = {}
  4. For each detection in sorted detections:
     original_value = text[detection.start:detection.end]
     if original_value in value_to_token:                 # Dedup
       token = value_to_token[original_value]
     else:
       type_short = detection.entity_type[:20]            # Truncate to 20 chars
       counter = per_type_counters.get(type_short, 0)
       token_index = (seed & 0x3FFFFFFF) + counter        # Random offset
       token = f"[{type_short}_{token_index}]"
       value_to_token[original_value] = token
       per_type_counters[type_short] = counter + 1
       mapping[token] = original_value
     tokenized = tokenized[:start] + token + tokenized[end:]   # Safe: right-to-left
  5. Return (tokenized, mapping)
```

### 4.4 TailBuffer FSM

Reassembles streaming chunks and prevents emitting partial token boundaries.

```
State Machine:

                        ┌──────────┐
                        │COLLECTING│◄────────────────────┐
                        └────┬─────┘                      │
                             │ ingest(chunk)              │
                             v                            │
                        ┌──────────┐                      │
                        │ MATCHING │                      │
                        └────┬─────┘                      │
                             │                             │
              ┌──────────────┼──────────────┐              │
              v              v              v              │
        ┌──────────┐ ┌──────────┐ ┌──────────┐            │
        │Full match│ │Partial   │ │No match  │            │
        │at frontier│ │match at  │ │          │            │
        └────┬─────┘ │tail      │ └────┬─────┘            │
             │       └────┬─────┘      │                   │
             v            v            v                   │
        ┌─────────────────────────────────────┐            │
        │              FLUSHING                │───────────┘
        │  emit safe_prefix (all but tail)     │
        │  retain tail_window = last N chars   │
        └─────────────────────────────────────┘

  On FINISH event: FLUSH entire buffer, transition to TERMINATED
  On non-TEXT_DELTA events: bypass FSM entirely
```

Flush triggers:
- **Full token match at frontier**: Token pattern `[TYPE_N]` fully matched within tail window
- **No match at frontier**: Emit safe prefix (all but `TAIL_WINDOW_CHARS`)
- **MAX_BUFFER_CHARS (2048) exceeded**: Emit safe prefix
- **MAX_BUFFER_AGE_MS (1000) exceeded**: Emit safe prefix
- **FINISH event**: Emit entire buffer including tail window, terminate
- **Partial token at tail**: Retain buffer, wait for more data (no emission)

### 4.5 Token Restoration (Streaming)

```
Algorithm: StreamingRestorationStage.restore_text(text)
  Input:  text — assembled text chunk from TailBuffer
  Output: restored text with tokens replaced by original values

  1. Pre-fetch all mappings via HGETALL at stream start (start_session)
  2. Build case-insensitive lookup: {token.upper(): original_value for each mapping}
  3. For each match of pattern r'\[?([A-Z][A-Z_]{0,19}_\d+)\]?' in text:
     key = match.upper().lstrip('[').rstrip(']')
     if key in lookup: replace match with lookup[key]
     else: leave match as-is
  4. Return replaced text
```

### 4.6 Luhn Checksum Validation

```
Algorithm: luhn_checksum(card_number)
  Input:  card_number — string of digits
  Output: True if valid Luhn checksum, False otherwise

  1. Strip non-digits from input
  2. If len < 13 or len > 19: return False
  3. Sum = 0, parity = len % 2
  4. For i, digit in enumerate(reversed(digits)):
     if i % 2 == parity:
       digit *= 2
       if digit > 9: digit -= 9
     sum += digit
  5. Return sum % 10 == 0
```

### 4.7 SHA-384 Audit Hash Chain

```
Algorithm: compute_event_hash(event)
  Input:  event — AuditEvent (without hash field)
  Output: SHA-384 hex digest (96 chars)

  1. Build canonical dict from event fields (exclude hash itself):
     {event_id, prev_hash, timestamp.isoformat(), tenant_id, request_id,
      policy_id, decision, provider, latency_ms, event_type}
  2. Serialize: json.dumps(data, sort_keys=True, separators=(",", ":"))
  3. Return hashlib.sha384(canonical.encode()).hexdigest()
```

Chain integrity verification walks from most recent to oldest, recomputes each hash, and compares against stored `hash` column. Any mismatch indicates tampering.

### 4.8 Classification Max-Algorithm (Phase 12)

```
Algorithm: classify_v2(entity_types)
  Input:  entity_types — list of detected entity type strings
  Output: ClassificationResult {highest, labels, detected_levels}

  1. If no entity_types: return INTERNAL       # Undetected default
  2. For each type:
     level = ENTITY_CLASSIFICATION_MAP.get(type.upper(), INTERNAL)
     # Unknown types log warning, default to INTERNAL
  3. highest = max(levels)                     # IntEnum comparison
  4. Return ClassificationResult
```

Default entity-to-level mapping (excerpt):
| Entity Type | Classification Level |
|-------------|---------------------|
| PERSON, LOCATION, DATE_TIME, DOMAIN_NAME, ORGANIZATION, AGE, ZIP_CODE, IP_ADDRESS | INTERNAL |
| EMAIL, PHONE, URL, CRYPTO | CONFIDENTIAL |
| CREDIT_CARD, IBAN, SWIFT, SSN, PASSPORT, BANK_ACCOUNT, MEDICAL_LICENSE, DRIVERS_LICENSE, TAX_ID, HEALTH_INFO | RESTRICTED |
| API_KEY, PASSWORD, AUTH_TOKEN, SOURCE_CODE | HIGHLY_RESTRICTED |

### 4.9 JSON Analyzer Recursive Walk

```
Algorithm: JsonAnalyzer.analyze(json_data)
  Input:  json_data — raw JSON string/bytes or parsed dict
  Output: UnifiedDetectionResult with all detected entities

  1. Parse JSON if string/bytes → dict
  2. Walk tree recursively:
     _walk_node(node, path="$", depth=0):
       if depth > max_depth(50): return
       if node is dict:
         for key, value in node.items():
           _walk_node(value, f"{path}.{key}", depth + 1)
       if node is list:
         for i, value in enumerate(node):
           _walk_node(value, f"{path}[{i}]", depth + 1)
       if node is string:
         is_sensitive = _is_sensitive_key(last_key)
         result = detection_engine.analyze(node)
         if is_sensitive: boost confidence += 0.15 (cap 1.0)
         collect results with path metadata
       if node is number/bool/null: skip
  3. Return UnifiedDetectionResult
```

Sensitive key patterns (compiled regex):
```
ssn|social\.security|password|secret|token|api\.key|credit\.card|
bank\.account|pin|cvv|passport|license\.number|medical\.record|dob
```

---

## 5. Pipeline Stage Definitions

### 5.1 Non-Streaming Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NON-STREAMING PIPELINE                              │
│                                                                             │
│  POST /v1/chat/completions                                                  │
│       │                                                                     │
│       v                                                                     │
│  ┌─────────────┐                                                            │
│  │ Auth MW     │ ← Bearer token validation                                  │
│  └──────┬──────┘                                                            │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ ContentType │ ← Content-Type Dispatcher (Phase 9)                        │
│  │ Middleware   │    text/plain → proceed                                   │
│  └──────┬──────┘    application/json → JsonAnalyzer                         │
│         v           multipart/form-data → MultipartAnalyzer                 │
│  ┌─────────────┐    unknown → HTTP 415                                      │
│  │ PDP #1      │ ← Policy Decision Point (Phase 8)                         │
│  └──────┬──────┘                                                            │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ TextExtract │ ← Walk messages[], extract TextNodes                       │
│  └──────┬──────┘                                                            │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ Classify    │ ← Evaluate classification rules (BLOCK/ROUTE_LOCAL/        │
│  └──────┬──────┘    ANONYMIZE/PASS)                                         │
│         │                                                                    │
│  ┌──────v───────┐                                                           │
│  │ BLOCK/       │ ← If BLOCK → HTTP 403, audit, return                     │
│  │ ROUTE_LOCAL  │ ← If ROUTE_LOCAL → HTTP 302 or local processing           │
│  └──────┬───────┘                                                           │
│         v  ANONYMIZE                                                        │
│  ┌─────────────┐                                                            │
│  │ Detection   │ ← RegexDetector + PresidioClient → SpanArbiter             │
│  │ (hybrid)    │    locale-aware RecognizerSet (Phase 4)                    │
│  └──────┬──────┘    ExclusionList applied after merge                       │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ Tokenize    │ ← Replace spans with [TYPE_N] tokens                       │
│  └──────┬──────┘    Store mapping → Valkey (HSET)                           │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ Forwarding  │ ← Pre-forward guard: verify all stages completed           │
│  │ Guard       │    Any failure → HTTP 503                                  │
│  └──────┬──────┘                                                            │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ Provider    │ ← Translate → Execute → Translate Response                │
│  │ Adapter     │    OpenAI/Anthropic/Gemini/Ollama                          │
│  └──────┬──────┘                                                            │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ Restore     │ ← Replace tokens in response body with originals           │
│  └──────┬──────┘    Case-insensitive + bracket-optional matching            │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ PDP #2      │ ← Post-processing policy decision (Phase 8)               │
│  └──────┬──────┘                                                            │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ Emit Audit  │ ← Structured JSON audit log (metadata only)               │
│  │ & Metrics   │    Prometheus counters + histograms                        │
│  └──────┬──────┘                                                            │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ Se ssion    │ ← Delete Valkey mapping (optional), free resources         │
│  │ Cleanup     │                                                            │
│  └─────────────┘                                                            │
│                                                                             │
│  Cleanup: → DELETE Valkey key 'anonreq:{tenant_id}:{session_id}'            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Streaming Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          STREAMING PIPELINE                                 │
│                                                                             │
│  Same as non-streaming through ForwardingGuard, then:                       │
│                                                                             │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ Provider    │ ← adapter.stream_events() → AsyncIterator[StreamEvent]    │
│  │ Adapter     │    Normalize provider wire format to StreamEvent           │
│  └──────┬──────┘                                                            │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ TailBuffer  │ ← COLLECTING/MATCHING/FLUSHING FSM                        │
│  │ FSM         │    Only TEXT_DELTA events enter FSM                        │
│  └──────┬──────┘    TOOL_CALL_DELTA/REASONING_DELTA/FINISH bypass           │
│         v           Never emits partial tokens                              │
│  ┌─────────────┐                                                            │
│  │ Streaming   │ ← Case-insensitive + bracket-optional token replacement   │
│  │ Restoration │    Pre-fetches mappings via HGETALL at stream start        │
│  └──────┬──────┘                                                            │
│         v                                                                   │
│  ┌─────────────┐                                                            │
│  │ SSE Emitter │ ← Format as text/event-stream                             │
│  └──────┬──────┘    Anti-buffering headers:                                 │
│         v           Cache-Control: no-cache                                 │
│  ┌─────────────┐    X-Accel-Buffering: no                                   │
│  │ Client SSE  │    Content-Type: text/event-stream                         │
│  └─────────────┘                                                            │
│                                                                             │
│  On FINISH: → FLUSH remaining buffer → restore → emit FINISH frame          │
│              → emit [DONE] frame → cleanup_session()                        │
│                                                                             │
│  On CLIENT_DISCONNECT: → cancel HTTPX → cleanup_session()                   │
│                                                                             │
│  TTL Extension: at 80% elapsed time, EXPIRE cache key to reset TTL          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Stage Interface Contract

Every pipeline stage conforms to:

```python
@dataclass
class StageResult:
    success: bool
    error: str | None = None
    error_code: str | None = None      # e.g. "PRESIDIO_TIMEOUT", "CLASSIFICATION_BLOCK"

class PipelineStage(ABC):
    async def execute(self, ctx: ProcessingContext) -> StageResult: ...
```

Stage ordering in `PipelineManager.execute()`:
1. `TextExtractionStage` — walk messages, produce TextNodes
2. `LocaleNegotiationStage` — resolve locale header to RecognizerSet
3. `ClassificationStage` — 4-tier action-based evaluation
4. `DetectionStage` — regex + NER → SpanArbiter → ExclusionList
5. `ClassificationV2Stage` — Phase 12 sensitivity classification (optional)
6. `TokenizationStage` — [TYPE_N] replacement, Valkey storage
7. `ForwardingGuard` — verify prerequisites, fail-secure check
8. `ProviderStage` — translate → execute/stream → translate back
9. `RestorationStage` — token → original value replacement
10. `AuditStage` — emit audit log (metadata only)
11. `MetricsStage` — emit Prometheus metrics
12. `CleanupStage` — delete Valkey mapping, release resources

---

## 6. Database Schemas

### 6.1 Valkey (Ephemeral Token Mapping Store)

No persistence. `save ""`, no AOF, no RDB.

```
Key format:         anonreq:{tenant_id}:{session_id}
Type:               HASH
TTL:                600s (configurable: 60–3600s)
Persistence:        disabled (save "", appendonly no)

Fields:
  {token}           → {original_value}
  e.g. "[EMAIL_1]"  → "user@example.com"

Operations:
  HSET key token value           # Store mapping (PipelineManager after tokenization)
  HGETALL key                    # Fetch all mappings (RestorationStage at stream start)
  DEL key                        # Delete after response (SessionCleanup)
  EXPIRE key ttl                 # Extend TTL for long streams
  KEYS anonreq:*                 # Admin operations only — not used at runtime
```

### 6.2 PostgreSQL (Audit Chain — Phase 11)

Table: `audit_event`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGINT` | PK, AUTOINCREMENT | Monotonic row ID |
| `event_id` | `VARCHAR(64)` | UNIQUE, NOT NULL | UUID or structured identifier |
| `prev_hash` | `VARCHAR(96)` | NULLABLE | SHA-384 hex of previous event (NULL for genesis) |
| `hash` | `VARCHAR(96)` | NOT NULL | SHA-384 hex of this event (excluding hash field) |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL | Event timestamp |
| `tenant_id` | `VARCHAR(64)` | NOT NULL, INDEXED | Tenant scope |
| `request_id` | `VARCHAR(64)` | NULLABLE | Correlates to gateway request |
| `policy_id` | `VARCHAR(64)` | NULLABLE | Policy rule identifier |
| `decision` | `VARCHAR(32)` | NULLABLE | BLOCK/ANONYMIZE/PASS/ROUTE_LOCAL |
| `provider` | `VARCHAR(64)` | NULLABLE | LLM provider name |
| `latency_ms` | `INTEGER` | NULLABLE | Request latency |
| `event_type` | `VARCHAR(64)` | NOT NULL, INDEXED | "request", "config_change", "policy_decision" |
| `operator_id` | `VARCHAR(64)` | NULLABLE | Admin who made config change |
| `change_type` | `VARCHAR(64)` | NULLABLE | Type of configuration change |
| `prev_value_hash` | `VARCHAR(96)` | NULLABLE | SHA-384 of previous config value |
| `new_value_hash` | `VARCHAR(96)` | NULLABLE | SHA-384 of new config value |
| `metadata_json` | `TEXT` | NULLABLE | Additional structured metadata |
| `retention_days` | `INTEGER` | DEFAULT 2557 | Retention period (7 years default) |

**Indexes:**
- `idx_audit_event_tenant_id` on `(tenant_id)`
- `idx_audit_event_timestamp` on `(timestamp)`
- `idx_audit_event_event_type` on `(event_type)`

**Migration:** Alembic managed, async via asyncpg.

**Chain anchoring:** Daily SHA-384 root hash computed from concatenation of all ordered event hashes, signed with HMAC-SHA384, stored in `audit_anchor` table + archived to MinIO WORM bucket.

### 6.3 MinIO Archive (Chain Anchors — Phase 11)

```
Bucket: anonreq-audit-archives (WORM, object-lock enabled)
Path:   anchors/{date.isoformat()}/anchor.json
Content:
{
  "date": "2026-06-26",
  "daily_root_hash": "abc...384",
  "signature": "hmac-sha384-hex",
  "event_count": 1234,
  "created_at": "2026-06-26T23:59:59Z",
  "verified_at": "2026-06-27T00:00:01Z"
}
```

---

## 7. API Contracts

### 7.1 POST /v1/chat/completions

Primary endpoint. OpenAI-compatible input schema. Supports both streaming and non-streaming.

**Request Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer {ANONREQ_API_KEY}` |
| `Content-Type` | Yes | `application/json` (or multipart/form-data for Phase 9) |
| `X-AnonReq-Locale` | No | Locale codes for detection (e.g., `de-DE, fr-FR`) |
| `X-AnonReq-Tenant-ID` | No | Tenant identifier for multi-tenant (default: `default`) |

**Request Body (OpenAI-compatible):**
```json
{
  "model": "gpt-4o",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "My email is john@example.com and phone is +1-555-1234"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**Non-Streaming Response (200):**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1719000000,
  "model": "gpt-4o",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "I can see your email is [EMAIL_1] and phone is [PHONE_1]."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 15,
    "total_tokens": 35
  }
}
```

**Streaming Response (200):**
```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no

data: {"choices":[{"delta":{"content":"I can see"},"index":0}]}

data: {"choices":[{"delta":{"content":" your email is [EMAIL_1]"},"index":0}]}

data: {"choices":[{"delta":{},"finish_reason":"stop","index":0}]}

data: [DONE]
```

**Error Responses:**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | Invalid request schema | `{"error": {"message": "...", "type": "invalid_request_error"}}` |
| 401 | Missing/invalid API key | `{"error": {"message": "Unauthorized", "type": "auth_error"}}` |
| 403 | BLOCK classification triggered | `{"error": {"message": "Request blocked by policy", "type": "policy_block", "rule_id": "CLS-001"}}` |
| 415 | Unsupported Content-Type | `{"error": {"message": "Unsupported Content-Type", "type": "unsupported_media_type"}}` |
| 451 | HIGHLY_RESTRICTED content (Phase 12) | `{"error": {"message": "Content blocked per data policy", "type": "policy_block"}}` |
| 500 | Internal error / fail-secure | `{"error": {"message": "Internal server error", "type": "internal_error"}}` |
| 502 | Upstream provider error | `{"error": {"message": "Provider error: ...", "type": "provider_error"}}` |
| 503 | ForwardingGuard triggered | `{"error": {"message": "Service temporarily unavailable", "type": "service_unavailable"}}` |

### 7.2 GET /health

```
Response 200:
{
  "status": "healthy",
  "version": "0.1.0",
  "uptime_seconds": 3600,
  "services": {
    "valkey": "connected",
    "presidio": "connected"
  }
}
```

### 7.3 GET /v1/models

```
Response 200:
{
  "object": "list",
  "data": [
    {"id": "gpt-4o", "object": "model", "provider": "openai"},
    {"id": "claude-sonnet-4", "object": "model", "provider": "anthropic"},
    {"id": "gemini-2.0-flash", "object": "model", "provider": "gemini"}
  ]
}
```

### 7.4 GET /v1/compliance/presets

```
Response 200:
{
  "presets": [
    {
      "id": "gdpr",
      "name": "GDPR",
      "mandatory_entity_types": ["PERSON", "EMAIL", "PHONE", "CREDIT_CARD"],
      "thresholds": {"PERSON": 0.8, "EMAIL": 0.9}
    }
  ],
  "active": ["gdpr"]
}
```

### 7.5 GET /v1/config/rules

```
Response 200:
{
  "version": 1,
  "custom_recognizers": [...],
  "exclusion_list": [...],
  "thresholds": {"EMAIL": 0.7, "PHONE": 0.8}
}
```

### 7.6 POST /v1/admin/config/rules (Phase 5)

```
Request Body: YAML custom patterns + exclusion list
Response 200: {"status": "ok", "version": 2}  # Atomic swap, version incremented
Response 422: {"detail": [{"msg": "Invalid regex pattern", "loc": ["patterns", 0]}]}
```

### 7.7 GET /metrics

Prometheus metrics endpoint. No authentication (scraped by Prometheus).

---

## 8. Error Handling Strategy

### 8.1 Fail-Secure Principle

Any error in any pipeline stage MUST result in HTTP 5xx — never forward unsanitized data.

```python
assert error_always_produces_5xx, "All errors → 500/503, never forward unsanitized data"
```

### 8.2 Error Classification

| Error Category | HTTP Status | Recovery | Action |
|---------------|-------------|----------|--------|
| Detection failure | 500 | None | Block request, audit, return 500 |
| Cache timeout | 503 | Retry | Return 503, no provider call |
| Presidio timeout | 500 | Retry | Block, audit, return 500 |
| Presidio error | 500 | None | Block, audit, return 500 |
| Provider timeout | 502 | Retry | Return 502 to client |
| Provider error | 502 | None | Return 502 with provider error |
| Classification BLOCK | 403 | None | Return 403 with rule_id |
| Tokenization failure | 500 | None | Block, never forward |
| Pipeline stage failure | 500 | None | Block, emit fail_secure metric |

### 8.3 Error Handling by Component

**PresidioClient:**
```python
# Timeout: 2.0s per D-50
# Semaphore: max 10 concurrent requests
# On httpx.TimeoutException → raise PresidioTimeoutError
# On httpx.HTTPStatusError → raise PresidioError
# Circuit breaker: after N consecutive failures, skip Presidio for M seconds
```

**CacheManager:**
```python
# On redis.ConnectionError → raise CacheUnavailableError
# PipelineManager catches this → HTTP 503, never forward
# TTL extension failures are logged but non-fatal (mapping still valid)
```

**DetectionStage:**
```python
# If PresidioClient raises any exception:
#   log error
#   block request: return HTTP 500
#   increment fail_secure_events_total{failure_type="presidio"}
#   Never fall through to forward without detection
```

**ForwardingGuard:**
```python
# Verify: classification done AND detection done AND tokenization done
# Any missing stage: HTTP 503
# Verify: token_mappings exist if entities detected
# Verify: request body modified (transformed_request != original_request)
# All checks pass → allow provider call
# Any check fails → 503, audit
```

**Streaming Disconnect:**
```python
# ASGI disconnect signal → cancel upstream HTTPX
# Cleanup via SessionCleanup.cleanup() in finally:
# _cleaned flag ensures exactly-once execution
# First terminal state wins (FINISH vs DISCONNECT race)
```

### 8.4 Audit Logging of Errors

```python
# Every error produces structured audit log entry:
{
    "event_type": "error",
    "error_type": "presidio_timeout",
    "request_id": "req_abc",
    "tenant_id": "default",
    "fail_secure": true,
    "timestamp": "..."
}
# No raw PII in audit logs per field allowlist (AUDT-CFG-02)
```

### 8.5 Error Codes

| Code | Meaning |
|------|---------|
| `PRESIDIO_TIMEOUT` | Presidio Analyzer request timed out (>2s) |
| `PRESIDIO_ERROR` | Presidio returned non-200 |
| `PRESIDIO_CIRCUIT_OPEN` | Presidio circuit breaker engaged |
| `CACHE_UNAVAILABLE` | Valkey connection failed |
| `CACHE_TIMEOUT` | Valkey operation timed out |
| `CLASSIFICATION_BLOCK` | Classification rule matched BLOCK |
| `CLASSIFICATION_ERROR` | Classification engine failed |
| `DETECTION_FAILED` | Detection stage produced no results unexpectedly |
| `TOKENIZATION_ERROR` | Token replacement failed |
| `FORWARDING_GUARD` | Forwarding preconditions not met |
| `PROVIDER_ERROR` | Upstream LLM provider returned error |
| `PROVIDER_TIMEOUT` | Upstream LLM provider timed out |
| `RESTORATION_FAILED` | Token restoration produced unexpected output |
| `INTERNAL_ERROR` | Unknown/unexpected error |

---

## 9. Configuration Schema

### 9.1 Environment Variables (Pydantic Settings)

All configuration passes through environment variables with `ANONREQ_` prefix. No hardcoded values.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ANONREQ_",
        yaml_file="config/providers.yaml",
        extra="ignore",
    )

    # Required
    API_KEY: str = Field(min_length=32, validation_alias="ANONREQ_API_KEY")
    VALKEY_URL: str = Field(validation_alias="ANONREQ_VALKEY_URL")
    PRESIDIO_URL: str = Field(validation_alias="ANONREQ_PRESIDIO_URL")

    # Optional with defaults
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    LOG_LEVEL: str = "INFO"
    REQUEST_TIMEOUT_SECONDS: int = 30
    CACHE_TTL_SECONDS: int = 600            # 60–3600 range
    ADMIN_API_KEY: str | None = None
    DATABASE_URL: str | None = None         # Phase 11: PostgreSQL
    ANCHOR_SIGNING_KEY: str | None = None   # Phase 11: HMAC key

    @field_validator("API_KEY")
    @classmethod
    def validate_api_key_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("ANONREQ_API_KEY must be at least 32 characters")
        return v

settings = Settings()  # Module-level singleton, raises on import if required vars missing
```

### 9.2 YAML Configuration Files

```
config/
├── classification.yaml          # Phase 2: Classification rules with 4-tier actions
├── providers.yaml               # Phase 3: Provider capability registry
├── multimodal.yaml              # Phase 9: Content-type limits, enabled flags
├── audit.yaml                   # Phase 11: Audit retention, anchor schedule
├── classification_v2.yaml      # Phase 12: Entity-to-level mapping
├── compliance/
│   └── presets.yaml             # Phase 4: Compliance preset definitions
├── locales/
│   ├── en.yaml                  # Phase 4: English locale recognizers
│   ├── de-DE.yaml               # Phase 4: German locale recognizers
│   ├── fr-FR.yaml
│   ├── es-ES.yaml
│   ├── it-IT.yaml
│   ├── pt-BR.yaml
│   ├── ja-JP.yaml
│   └── zh-CN.yaml
├── policies/
│   └── default.yaml             # Phase 8: Tenant policies (rate limits, classification overrides)
└── firewall.yaml                # Phase 10: AI firewall threshold config
```

**config/classification.yaml:**
```yaml
rules:
  - id: CLS-001
    enabled: true
    version: 1
    name: block_credentials
    action: BLOCK
    metadata:
      owner: security-team
      category: credentials
      severity: critical
    conditions:
      roles: [user]
      regex: ['(?i)(?:password|secret|api.?key|token)\s*[:=]\s*\S+']
      keywords: []

  - id: CLS-002
    enabled: true
    version: 1
    name: anonymize_pii_requests
    action: ANONYMIZE
    conditions:
      roles: [user, assistant, tool]
      regex: []
      keywords: ["email", "phone", "ssn", "credit card"]
```

**config/providers.yaml:**
```yaml
providers:
  openai:
    base_url: "https://api.openai.com/v1"
    capabilities:
      streaming: true
      tool_calling: true
      max_context_window: 128000
      max_output_tokens: 4096
  anthropic:
    base_url: "https://api.anthropic.com/v1"
    capabilities:
      streaming: true
      tool_calling: true
      reasoning: true
      max_context_window: 200000
  gemini:
    base_url: "https://generativelanguage.googleapis.com/v1beta"
    capabilities:
      streaming: true
      vision: true
      max_context_window: 1048576
  ollama:
    base_url: "http://host.docker.internal:11434"
    capabilities:
      streaming: true
      tool_calling: false
      max_context_window: 4096
```

**config/multimodal.yaml:**
```yaml
version: "1.0"
content_types:
  text_plain:
    enabled: true
    max_size_mb: 10
  application_json:
    enabled: true
    max_size_mb: 5
    max_depth: 50
  multipart_form_data:
    enabled: true
    max_size_mb: 50
unknown_type_action: ROUTE_LOCAL
```

**config/audit.yaml:**
```yaml
audit:
  retention_days: 2557
  chain_anchor_enabled: true
  chain_anchor_time: "23:59:59 UTC"
```

### 9.3 Configuration Validation

- **Startup validation:** Pydantic Settings validates env vars on import. Missing `ANONREQ_API_KEY` with `< 32` chars raises `ValidationError` before any code runs.
- **YAML safe_load:** All YAML files use `yaml.safe_load()` — no arbitrary code execution.
- **Compliance preset validation:** At startup, compliance presets are merged with customer overrides and validated. Violations cause `sys.exit(1)` — the gateway refuses to start with invalid compliance configuration.
- **Regex validation:** Custom recognizer patterns are validated at load time via `re.compile()`. Invalid patterns produce structured error responses.
- **Hot-reload atomic swap:** `AtomicConfigRegistry.validate_and_swap()` validates the entire payload before pointer-swapping the active config. On validation failure, the old config remains active.

---

## 10. Test Architecture

### 10.1 Test Framework

| Tool | Purpose |
|------|---------|
| `pytest` 9.x | Test runner, fixtures, parametrization |
| `pytest-asyncio` | Async test support (`asyncio_mode = "auto"`) |
| `hypothesis` 6.x | Property-based testing for invariants |
| `respx` | HTTPX request mocking (Presidio, provider APIs) |
| `fakeredis` | In-memory Redis mock for CacheManager tests |
| `coverage` / `pytest-cov` | Coverage measurement (threshold: 80%) |

### 10.2 Test Directory Structure

```
tests/
├── __init__.py
├── conftest.py                         # Shared fixtures (test client, settings override, fakeredis)
├── test_config.py                      # Phase 1: Config loading and validation
│
├── unit/
│   ├── test_text_extractor.py          # Phase 2: Text extraction from messages
│   ├── test_classification.py          # Phase 2: Classification rule evaluation
│   ├── test_detection.py               # Phase 2: Regex patterns, Luhn, exclusion list
│   ├── test_presidio_client.py         # Phase 2: Presidio HTTP client (respx mocked)
│   ├── test_span_arbiter.py            # Phase 2: Span merge algorithm
│   ├── test_tokenization.py            # Phase 2: Tokenizer, dedup, reverse-offset
│   ├── test_restoration.py             # Phase 2: Non-streaming token restoration
│   ├── test_cache_manager.py           # Phase 2: Valkey abstraction (fakeredis)
│   │
│   ├── streaming/
│   │   ├── test_tail_buffer.py         # Phase 3: FSM state transitions
│   │   ├── test_restoration.py         # Phase 3: Streaming restoration
│   │   └── test_cleanup.py             # Phase 3: Session cleanup idempotency
│   │
│   ├── test_locale_negotiation.py      # Phase 4: Locale header resolution
│   ├── test_compliance_presets.py      # Phase 4: Preset merge and validation
│   ├── test_checksum.py                # Phase 4: ISO 7064, Luhn, Verhoeff validators
│   │
│   ├── test_metrics.py                 # Phase 5: Prometheus metrics recording
│   │
│   ├── test_classification_v2.py       # Phase 12: Sensitivity-level classification
│   │
│   └── multimodal/
│       ├── test_dispatcher.py          # Phase 9: Content-Type routing
│       ├── test_json_analyzer.py       # Phase 9: JSON recursive walk
│       ├── test_multipart_analyzer.py  # Phase 9: Multipart form-data parsing
│       └── test_limits.py              # Phase 9: Payload size/depth validation
│
├── integration/
│   ├── test_pipeline_non_streaming.py  # Full non-streaming pipeline end-to-end
│   ├── test_pipeline_streaming.py      # Full streaming pipeline end-to-end
│   ├── test_multi_provider.py          # Provider adapter integration
│   └── test_fail_secure.py             # Fail-secure invariants
│
├── property/
│   ├── test_round_trip.py              # Round-trip correctness (Hypothesis)
│   ├── test_token_uniqueness.py        # Token dedup invariants
│   ├── test_fail_secure_invariants.py  # Never-forward verification
│   ├── test_locale_checksums.py        # Locale checksum validation
│   ├── test_no_pii_in_logs.py          # Audit log field allowlist
│   ├── test_streaming_round_trip.py    # Streaming split-token restoration
│   └── test_cross_session_random.py    # Cross-request token randomization
│
└── conftest.py                         # Root-level fixtures
```

### 10.3 Shared Fixtures (tests/conftest.py)

```python
@pytest.fixture
def settings_override(monkeypatch):
    """Set valid env vars before Settings import."""
    monkeypatch.setenv("ANONREQ_API_KEY", "testkey1234567890123456789012345678")
    monkeypatch.setenv("ANONREQ_VALKEY_URL", "redis://localhost:6379")
    monkeypatch.setenv("ANONREQ_PRESIDIO_URL", "http://localhost:5001")
    yield

@pytest.fixture
async def cache_manager():
    """Fakeredis-backed CacheManager for tests."""
    redis = await fakeredis.FakeAsyncRedis()
    cm = CacheManager(redis=redis, ttl=600)
    yield cm
    await redis.close()

@pytest.fixture
def sample_chat_request() -> dict:
    return {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "My email is john@example.com and phone is +1-555-1234"}
        ],
        "stream": False,
    }

@pytest.fixture
def mock_presidio(respx_mock):
    """Mock Presidio /analyze endpoint with configurable responses."""
    respx_mock.post("http://localhost:5001/analyze").respond(
        json=[
            {"entity_type": "EMAIL_ADDRESS", "start": 11, "end": 26, "score": 0.99},
            {"entity_type": "PHONE_NUMBER", "start": 40, "end": 51, "score": 0.95},
        ]
    )
    yield respx_mock

@pytest.fixture
async def test_client(settings_override):
    """FastAPI TestClient with settings override."""
    from anonreq.main import app
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

### 10.4 Property-Based Tests (Hypothesis)

**Round-trip correctness (test_round_trip.py):**
```python
@given(
    text=text(min_size=1, max_size=500),
    entity_types=lists(sampled_from(["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "PERSON"]), min_size=1, max_size=5),
    session_seed=integers(min_value=0, max_value=2**32 - 1),
)
def test_anonymize_restore_round_trip(text, entity_types, session_seed):
    """anonymize(tokenize) → restore → original text byte-for-byte match."""
    detections = generate_detections(text, entity_types)
    tokenizer = Tokenizer(seed=session_seed)
    tokenized, mapping = tokenizer.tokenize(text, detections)
    restored = restore_text(tokenized, mapping)
    assert restored == text, f"Round-trip failed: {restored} != {text}"
```

**Fail-secure invariants (test_fail_secure_invariants.py):**
```python
@given(
    failure_scenario=sampled_from(["presidio_timeout", "presidio_error", "cache_unavailable", "detection_empty"]),
    request_body=dictionaries(keys=text(max_size=10), values=text(max_size=50)),
)
@genspec
async def test_fail_secure_never_forwards(failure_scenario, request_body):
    """Any detection/cache/timeout error → HTTP 500, 0 requests forwarded to provider."""
    # Mock all downstream components, inject failure at specified point
    # Assert: HTTP status is 5xx, provider mock called 0 times
    ...
```

**Streaming round-trip (test_streaming_round_trip.py):**
```python
@given(
    original_text=text(min_size=1, max_size=200),
    split_positions=...  # Generate split at every possible token index
)
@genspec
async def test_streaming_restoration_at_every_split(original_text, split_positions):
    """Split text at every possible position, restore each chunk, verify final = original."""
    ...
```

**Cross-session token randomization (test_cross_session_random.py):**
```python
@given(
    pairs=lists(
        tuples(
            text(min_size=1, max_size=100),
            lists(sampled_from(ENTITY_TYPES), min_size=1, max_size=3),
        ),
        min_size=1000, max_size=1000,
    ),
)
@pytest.mark.slow
def test_cross_session_token_collision_probability(pairs):
    """Across 1000+ session pairs, probability of same token for different values ≤ 2⁻³²."""
    ...
```

### 10.5 Test Verification Gates

| Gate | Threshold | Required For |
|------|-----------|--------------|
| Unit tests | 100% pass | Every commit |
| Integration tests | 100% pass | Every commit |
| Property-based tests | 100% pass | Release |
| Code coverage | ≥80% | Release |
| Shellcheck (scripts) | No errors | Every commit |
| Docker Compose validation | `docker compose config` passes | Every commit |

### 10.6 Pytest Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.coverage.run]
source = ["anonreq"]
```

---

## Appendix A: Entity Type Registry (Phase 2 + 4)

Complete list of entity types that the Detection Engine can identify:

| Entity Type | Tier | Detection Method | Validation | Default Classification |
|-------------|------|-----------------|------------|----------------------|
| `EMAIL_ADDRESS` | 1 | Regex | Domain pattern | CONFIDENTIAL |
| `PHONE_NUMBER` | 1 | Regex | Pattern + length | CONFIDENTIAL |
| `CREDIT_CARD` | 1 | Regex | Luhn checksum | RESTRICTED |
| `IBAN_CODE` | 1 | Regex | Pattern + mod-97 | RESTRICTED |
| `IP_ADDRESS` | 1 | Regex | Quad-dotted decimal | INTERNAL |
| `URL` | 1 | Regex | http/https pattern | CONFIDENTIAL |
| `US_SSN` | 2 | Regex | Invalid area exclusion | RESTRICTED |
| `SWIFT_CODE` | 2 | Regex | Pattern | RESTRICTED |
| `CRYPTO` | 2 | Regex | Wallet address pattern | CONFIDENTIAL |
| `PERSON` | NER | Presidio | — | INTERNAL |
| `LOCATION` | NER | Presidio | — | INTERNAL |
| `DATE_TIME` | NER | Presidio | — | INTERNAL |
| `ORGANIZATION` | NER | Presidio | — | INTERNAL |
| `AGE` | NER | Presidio | — | INTERNAL |
| `PASSPORT` | NER+Regex | Both | Country-specific | RESTRICTED |
| `BANK_ACCOUNT` | NER+Regex | Both | Pattern | RESTRICTED |
| `MEDICAL_LICENSE` | NER+Regex | Both | Pattern | RESTRICTED |
| `DRIVERS_LICENSE` | NER+Regex | Both | Country-specific | RESTRICTED |
| `TAX_ID` | NER+Regex | Both | Country-specific | RESTRICTED |
| `HEALTH_INFO` | NER | Presidio | — | RESTRICTED |
| `API_KEY` | Regex | Pattern | Entropy check | HIGHLY_RESTRICTED |
| `PASSWORD` | Regex | Pattern | Context detection | HIGHLY_RESTRICTED |
| `AUTH_TOKEN` | Regex | Pattern | Context detection | HIGHLY_RESTRICTED |
| `SOURCE_CODE` | NER | Presidio | — | HIGHLY_RESTRICTED |
| `NRP` | NER | Presidio | — | INTERNAL |
| `ZIP_CODE` | NER | Presidio | — | INTERNAL |
| `DOMAIN_NAME` | Regex | Pattern | DNS pattern | INTERNAL |

## Appendix B: Docker Compose Service Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Docker Compose (anonreq-net)                    │
│                                                                      │
│  ┌──────────────────────┐   ┌──────────────────┐   ┌──────────────┐ │
│  │    anonreq-gateway    │   │ anonreq-presidio  │   │ anonreq-     │ │
│  │    (build: .)         │   │ (mcr.microsoft.com│   │ valkey       │ │
│  │    Port: 8080         │   │  /presidio-       │   │ (valkey/     │ │
│  │    Health: /health    │   │  analyzer:latest) │   │  valkey:8)   │ │
│  │    Restart: unless-   │   │  Port: internal   │   │  Port:       │ │
│  │    stopped            │   │  Health: /health  │   │  internal    │ │
│  └──────────┬───────────┘   └────────┬─────────┘   │  Persist:    │ │
│             │                        │             │  disabled    │ │
│             │                        │             └──────┬───────┘ │
│             │                        │                     │         │
│             └────────────────────────┴─────────────────────┘         │
│                        Internal network (bridge)                     │
└─────────────────────────────────────────────────────────────────────┘
```

Service dependencies:
- `valkey` and `presidio-analyzer`: No dependencies
- `anonreq-gateway`: `depends_on` both with `condition: service_healthy`
- Gateway starts only after Valkey and Presidio pass healthchecks

## Appendix C: Token Format Specification

**Format:** `[TYPE_N]`

| Component | Rule | Example |
|-----------|------|---------|
| `[` | Literal opening bracket | `[` |
| `TYPE` | Entity type, 1–20 uppercase chars + underscores | `EMAIL_ADDRESS` |
| `_` | Literal underscore separator | `_` |
| `N` | Positive integer, per-type counter + random seed offset | `42` |
| `]` | Literal closing bracket | `]` |

Full regex: `\[([A-Z][A-Z_]{0,19})_(\d+)\]`

Properties:
- Entity type truncated to 20 chars maximum
- Counter starts at 0 per entity type within a session
- Final index = `(cryptographic_seed & 0x3FFFFFFF) + counter`
- Different sessions have different seeds (`secrets.randbits(32)`)
- Same value in same session → same token (deduplication)
- Different values of same type → different tokens
- Per-type independent counters (`EMAIL_0` and `PHONE_0` are parallel, not sequential)

Token restoration matching:
- Case-insensitive: `[email_42]`, `[EMAIL_42]`, `[Email_42]` all match
- Bracket-optional: `EMAIL_42` at word boundary resolves to same mapping as `[EMAIL_42]`
- Unknown/unresolvable tokens left as-is (never replaced with wrong value)
