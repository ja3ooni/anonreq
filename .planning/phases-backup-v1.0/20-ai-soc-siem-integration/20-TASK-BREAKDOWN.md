# Phase 20 Task Breakdown: AI SOC / SIEM Integration

## Epics

1. Event Normalizer Service — core event bus subscriber, content stripper, MITRE mapper
2. Splunk HEC Sink — HTTP Event Collector output
3. QRadar CEF Sink — syslog CEF format output
4. Sentinel DCR Sink — Azure Monitor Data Collection Rule API output
5. Elastic Bulk Sink — Elasticsearch Bulk API output
6. Datadog Logs Sink — Datadog Logs API output
7. Generic Webhook Sink — user-configurable custom SIEM output
8. MITRE Technique ID Mapping — mapping config file and loader
9. Buffer & Retry Manager — per-sink in-memory buffer with exponential backoff
10. Health Monitoring — status endpoint and periodic probes
11. Sink Configuration — soc-sinks.yaml loader and validation
12. Integration Testing — end-to-end tests with each SIEM

## Stories

- As a SOC analyst, I want AI security events from all detection engines forwarded to Splunk so that AI threats are correlated with enterprise security telemetry.
- As a SOC analyst, I want events forwarded to QRadar in CEF format so that existing QRadar correlation rules can process AI events.
- As a SOC analyst, I want events forwarded to Microsoft Sentinel so that AI security events are visible in the Azure security portal.
- As a SOC analyst, I want events forwarded to Elastic Security so that AI events are searchable alongside log data.
- As a SOC analyst, I want events forwarded to Datadog Logs so that AI security appears in the Datadog observability platform.
- As a security officer, each forwarded event includes a MITRE ATT&CK / ATLAS technique ID so that SIEM detection rules can use standard technique-based alerting.
- As a SOC analyst, I want the appliance to buffer and retry events when a SIEM sink is unreachable so that no events are lost during network outages.
- As a security officer, I want a health endpoint showing per-sink status so that integration failures are visible.
- As a security officer, no raw prompt content is ever forwarded to SIEM so that PII exposure surface is minimized.
- As a platform operator, I want a generic webhook so that any custom SIEM can receive events.

## Tasks

### Event Normalizer Service
- T-001: Implement SOC Integration Service class with event bus subscription
- T-002: Implement content field stripping (enforce no-raw-content invariant)
- T-003: Implement MITRE mapping application to normalized events
- T-004: Implement event metadata enrichment (gateway_version, appliance_instance_id)
- T-005: Add Prometheus counter `anonreq_soc_events_normalized_total`
- T-006: Add audit event `soc_event_stripped` when content field detected and dropped

### Splunk HEC Sink
- T-007: Implement Splunk HEC HTTP client with auth header
- T-008: Implement Splunk HEC event envelope formatting (sourcetype: anonreq:ai_security)
- T-009: Implement Splunk HEC batch send (multiple events per request)
- T-010: Add Prometheus counter `anonreq_soc_sink_splunk_hec_total`

### QRadar CEF Sink
- T-011: Implement CEF message formatter (CEF:0|AnonReq|Appliance|...)
- T-012: Implement syslog TCP/UDP client for QRadar
- T-013: Implement field mapping from normalized event to CEF extension fields
- T-014: Add Prometheus counter `anonreq_soc_sink_qradar_cef_total`

### Sentinel DCR Sink
- T-015: Implement Azure DCR API HTTP client with managed identity / client secret auth
- T-016: Implement DCR stream JSON formatting matching stream schema
- T-017: Implement OAuth2 token acquisition for Azure API
- T-018: Add Prometheus counter `anonreq_soc_sink_sentinel_dcr_total`

### Elastic Bulk Sink
- T-019: Implement Elasticsearch Bulk API HTTP client with API key auth
- T-020: Implement NDJSON bulk formatting (action_meta + event pairs)
- T-021: Implement configurable index name pattern (default: `anonreq-ai-security-%Y.%m.%d`)
- T-022: Add Prometheus counter `anonreq_soc_sink_elastic_bulk_total`

### Datadog Logs Sink
- T-023: Implement Datadog Logs API HTTP client with DD-API-KEY auth
- T-024: Implement batch JSON array formatting
- T-025: Implement configurable log source tag (default: anonreq)
- T-026: Add Prometheus counter `anonreq_soc_sink_datadog_logs_total`

### Webhook Sink
- T-027: Implement generic webhook HTTP client with configurable auth header
- T-028: Implement user-configurable JSON payload template (Jinja2 subset)
- T-029: Implement configurable HTTP method (POST/PUT), content type, and timeout
- T-030: Add Prometheus counter `anonreq_soc_sink_webhook_total`

### MITRE Technique ID Mapping
- T-031: Create `config/mitre-mapping.yaml` with default mappings
- T-032: Implement MITRE mapping config loader with validation
- T-033: Implement fallback to `TEMP:UNMAPPED` for unmapped event types

### Buffer & Retry Manager
- T-034: Implement per-sink asyncio.Queue(maxsize=10000) with LRU eviction
- T-035: Implement exponential backoff retry loop with jitter
- T-036: Implement buffer overflow handling — emit `soc_buffer_overflow` audit event, drop oldest
- T-037: Add Prometheus gauge `anonreq_soc_buffer_size` per sink label
- T-038: Add Prometheus counter `anonreq_soc_buffer_overflow_total`

### Health Monitoring
- T-039: Implement periodic sink health probes (configurable interval, default 60s)
- T-040: Implement `GET /v1/admin/soc/integration/status` endpoint with RBAC
- T-041: Return per-sink status: reachable, unreachable, last_successful_delivery_ts, buffer_size, last_error
- T-042: Add Prometheus gauge `anonreq_soc_sink_healthy` (0/1) per sink label

### Sink Configuration
- T-043: Create `config/soc-sinks.yaml` schema and loader
- T-044: Implement environment variable / file-based secret references (`$env:`, `$file:`)
- T-045: Implement per-sink enable/disable at startup
- T-046: Implement config validation at load time with clear error messages
