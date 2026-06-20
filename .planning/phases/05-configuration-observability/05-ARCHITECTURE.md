# Phase 5 Architecture: Configuration & Observability

## Metrics Pipeline

```
Request
    ↓
FastAPI Middleware (start timer, increment requests_total)
    ↓
Classification → Detection → Tokenization → ForwardingGuard
    ↓                                           ↓
[anonreq_detection_latency_ms]              [record pre-provider timestamp]
    ↓
ProviderAdapter → execute / stream_events
    ↓
RestorationStage (non-streaming) / TailBuffer → RestorationStage (streaming)
    ↓                                           ↓
[anonreq_unrestored_tokens_total]          [anonreq_unrestored_tokens_total]
    ↓
Response sent
    ↓
[anonreq_processing_overhead_ms] histogram recorded
[anonreq_requests_total] incremented with labels
```

## Post-Restoration Token Verification

```
Non-streaming:
RestorationStage completes
    ↓
ScanResponseBody for /\[[A-Z]+_\d+\]/
    ↓
If matches > 0:
    anonreq_unrestored_tokens_total += matches
    log.warning("Unrestored tokens detected", count=matches)
    ↓
Return response (unchanged)

Streaming:
Stream FINISH event received
    ↓
TailBuffer flush remaining
    ↓
RestorationStage restore final chunk
    ↓
Scan full assembled (pre-restoration) text for /\[[A-Z]+_\d+\]/
    ↓
If matches > 0:
    anonreq_unrestored_tokens_total += matches
    log.warning("Unrestored tokens detected", count=matches)
    ↓
Emit FINISH to client (unchanged)
```

## Custom Rules Hot-Reload

```
POST /v1/admin/config/rules
Authorization: Bearer <admin_api_key>
Body: YAML custom patterns + exclusions
    ↓
Validate YAML against RecognizerSchema
    ↓
Validate patterns compile as regex
    ↓
Test patterns against sample text (optional)
    ↓
(any failure) → HTTP 422 with structured errors
    ↓
(all pass) → Atomic swap: new_recognizer_registry = build(payload)
               old = current_registry
               current_registry = new_recognizer_registry
               anonreq_active_config_version += 1
               log audit entry
    ↓
HTTP 200 { status: "ok", version: N }
```

## Metrics Namespace

```python
# prometheus_client counters and histograms

requests_total = Counter(
    "anonreq_requests_total",
    "Total requests processed",
    labelnames=["endpoint", "status_code", "provider", "classification"]
)

detection_latency = Histogram(
    "anonreq_detection_latency_ms",
    "Detection engine latency in milliseconds",
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000]
)

entities_detected = Counter(
    "anonreq_entities_detected_total",
    "Entities detected by type and locale",
    labelnames=["entity_type", "locale"]
)

unrestored_tokens = Counter(
    "anonreq_unrestored_tokens_total",
    "Residual unrestored tokens found post-restoration",
    labelnames=["endpoint"]
)

fail_secure_events = Counter(
    "anonreq_fail_secure_events_total",
    "Fail-secure events by failure type",
    labelnames=["failure_type"]
)

audit_failures = Counter(
    "anonreq_audit_failures_total",
    "Audit log write failures"
)

processing_overhead = Histogram(
    "anonreq_processing_overhead_ms",
    "Gateway processing overhead in milliseconds (total minus provider time)",
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000]
)

active_config_version = Gauge(
    "anonreq_active_config_version",
    "Current active custom rules config version (incremented on hot-reload)"
)
```

## Admin API Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `GET /v1/config/rules` | GET | `ANONREQ_API_KEY` | Return active custom recognizers and exclusion list |
| `POST /v1/admin/config/rules` | POST | `ANONREQ_ADMIN_API_KEY` | Hot-reload custom rules |
| `GET /metrics` | GET | None | Prometheus scrape endpoint |

## Domain Model

```python
@dataclass
class CustomRecognizerRule:
    id: str
    entity_type: str
    patterns: list[str]           # regex patterns
    confidence: float = 0.7
    enabled: bool = True
    version: int = 1
    created_at: datetime | None = None

@dataclass
class ExclusionEntry:
    value: str                    # exact match or wildcard pattern
    match_type: str               # "exact" | "wildcard"
    entity_type: str | None = None  # None = applies to all entity types

@dataclass
class RulesConfig:
    custom_recognizers: list[CustomRecognizerRule]
    exclusion_list: list[ExclusionEntry]
    thresholds: dict[str, float]  # entity_type → confidence threshold

@dataclass
class ConfigVersion:
    version: int
    config: RulesConfig
    applied_at: datetime
    applied_by: str | None = None

class AtomicConfigRegistry:
    _current: RulesConfig         # pointer-swapped on successful validation
    _version: int
    _lock: Lock

    def get_active(self) -> RulesConfig: ...
    def validate_and_swap(self, new: RulesConfig) -> bool: ...
```
