# Phase 20 Test Plan: AI SOC / SIEM Integration

## Unit Tests

### Event Normalizer
- Normalized event contains all required fields (severity, event_type, tenant_id, session_id, timestamp, gateway_version, appliance_instance_id, mitre_technique_id)
- Raw content fields stripped from forwarded events
- Event with content field detected: event dropped, `soc_strip_failure` audit event emitted
- MITRE mapping applied correctly per event_type
- Unmapped event_type gets `TEMP:UNMAPPED` fallback
- Gateway version and appliance instance ID populated correctly

### Splunk HEC Sink
- HEC event envelope formatted correctly with sourcetype `anonreq:ai_security`
- Authorization header set to `Splunk {token}`
- Batch send retries on HTTP 4xx/5xx
- Invalid token causes unreachable status

### QRadar CEF Sink
- CEF header format: `CEF:0|AnonReq|Appliance|1.0|{mitre_id}|{event_type}|{severity}|`
- CEF extension fields mapped correctly
- Syslog message length within limits
- TCP connection retry on failure

### Sentinel DCR Sink
- OAuth2 token acquisition from Azure
- DCR stream request body matches stream schema
- Bearer token included in Authorization header
- Token refresh on expiry

### Elastic Bulk Sink
- NDJSON formatting correct: action_meta line + event line
- Index name pattern with date substitution correct
- API key auth header set correctly
- Bulk response error handling

### Datadog Logs Sink
- JSON array format correct
- DD-API-KEY header set correctly
- Batch size within Datadog limits

### Webhook Sink
- Payload template rendering correct (Jinja2 subset)
- Configured HTTP method, content-type, and headers applied
- Timeout handling

### MITRE Mapping
- All default event types mapped to known MITRE technique IDs
- Invalid mapping YAML raises validation error
- Fallback `TEMP:UNMAPPED` for unknown event_type
- MITRE ATLAS IDs supported alongside ATT&CK IDs

### Buffer & Retry Manager
- Buffer enforces maxsize 10,000
- LRU eviction drops oldest events when full
- Buffer overflow emits `soc_buffer_overflow` audit event
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s (capped at 60s)
- Jitter applied within ±10%
- Max retries exhausted: event dropped, `soc_event_dropped` audit event emitted
- Request processing never blocked by buffer operations

### Health Monitoring
- Status endpoint returns expected JSON structure
- Reachable sink status correct
- Unreachable sink includes last_error and last_successful_delivery_ts
- Buffer size reported accurately
- RBAC: 403 for unauthorized roles, 200 for security_officer/administrator

### Sink Configuration
- `soc-sinks.yaml` valid/invalid: loaded or rejected with clear error
- Environment variable secrets resolved correctly (`$env:VAR_NAME`)
- File-based secrets resolved correctly (`$file:/path/to/secret`)
- Missing secret raises config validation error
- Disabled sinks not started and not probed

## Integration Tests

### Event Pipeline
- Full pipeline: Detection Engine event → Event Bus → Normalizer → Sink Router → Buffer → SIEM format
- All sink types format events correctly from the same normalized event
- Event published before sink configuration changes discarded (graceful shutdown)

### Sink Connectivity
- Splunk HEC reachable/unreachable status updates correctly
- QRadar syslog TCP connection established
- Sentinel DCR HTTP 200 vs 4xx handling
- Elastic Bulk API success/error response parsing
- Datadog Logs API error handling
- Webhook HTTP timeout handling

### Buffer Overflow Behavior
- Publish 10,001+ events → oldest event dropped
- Buffer overflow audit event emitted exactly once
- Subsequent events continue to flow after overflow
- Never blocks request processing (verified with concurrent request count)

## Property-Based Tests (Hypothesis)

- **No-raw-content invariant**: For all normalized events, no field named `content`, `prompt`, `response`, or `raw_text` exists at any nesting level.
- **Sink format completeness**: For all formatted sink outputs (HEC, CEF, DCR, Bulk, Datadog, Webhook), all required fields from the normalized event are present.
- **Buffer FIFO-LRU**: For any sequence of events with buffer at capacity, the oldest events are always dropped first (verified by event_id ordering).
- **MITRE mapping total**: Every event_type that appears in the source detection engines has exactly one MITRE mapping entry.
- **Severity ordering monotonic**: Severity levels are strictly ordered: informational < low < medium < high < critical.

## Security Tests

- No raw prompt content in any sink output format
- SIEM sink auth credentials never appear in logs or audit events
- Secrets referenced via `$env:` or `$file:` never resolved in error messages or logs
- TLS verification enabled by default for HTTPS sinks
- Status endpoint RBAC enforced
- Buffer overflow never causes OOM (maxsize enforced)
- Sink connection failures never cause unhandled exceptions in main pipeline

## Load Tests

- 1,000 events/second throughput through normalizer and all 6 sinks
- Buffer at 10,000 capacity with continuous event flow
- Sink unreachable for 60 seconds → buffer fills → LRU eviction → recovery
- Concurrent event publication from 10 detection engine threads
