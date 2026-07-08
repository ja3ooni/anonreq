# Phase 20 Security Acceptance: AI SOC / SIEM Integration

## Controls

- No raw prompt content ever forwarded to SIEM — enforced at event normalizer with fail-secure drop
- SIEM sink auth credentials stored via environment variable or file references, never in config YAML
- TLS verification enabled by default for all HTTPS-based sinks
- Status endpoint requires `security_officer` or `administrator` RBAC role
- In-memory buffer enforces maxsize 10,000 — prevents OOM on downstream SIEM failure
- Buffer overflow drops oldest events first (LRU) — never blocks request processing
- Exponential backoff with jitter prevents thundering herd on SIEM recovery
- Per-sink enable/disable — disabled sinks consume no resources
- Audit events for all SOC failures: unreachable sink, buffer overflow, event dropped, content strip failure

## Required Audit Events

- `soc_event_forwarded` — event successfully delivered to SIEM sink
- `soc_sink_unreachable` — SIEM sink connection failed
- `soc_sink_reachable` — SIEM sink recovered
- `soc_buffer_overflow` — buffer at capacity, oldest events dropped
- `soc_event_dropped` — event dropped after max retries exhausted
- `soc_strip_failure` — raw content detected in event, event dropped
- `sink_config_loaded` — sink configuration loaded at startup

## Required Metrics

- `anonreq_soc_events_normalized_total` — events processed by normalizer
- `anonreq_soc_sink_splunk_hec_total` — events forwarded to Splunk HEC
- `anonreq_soc_sink_qradar_cef_total` — events forwarded to QRadar CEF
- `anonreq_soc_sink_sentinel_dcr_total` — events forwarded to Sentinel DCR
- `anonreq_soc_sink_elastic_bulk_total` — events forwarded to Elastic Bulk
- `anonreq_soc_sink_datadog_logs_total` — events forwarded to Datadog Logs
- `anonreq_soc_sink_webhook_total` — events forwarded to webhook
- `anonreq_soc_buffer_size` — current buffer size per sink label
- `anonreq_soc_buffer_overflow_total` — buffer overflow events count
- `anonreq_soc_sink_healthy` — sink health status gauge (0/1) per sink label

## Release Gate

- All 6 SIEM sinks produce correctly formatted events for known event types
- No raw content detected in any sink output format (verified by automated inspection)
- Buffer overflow behavior confirmed: maxsize enforced, LRU eviction correct
- Buffer overflow never blocks request processing (verified under load)
- Exponential backoff with jitter verified (time sequence correct)
- Status endpoint returns accurate per-sink health status
- RBAC enforced on status endpoint (403 for unauthorized, 200 for authorized roles)
- SIEM sink auth credentials absent from logs and error messages
- MITRE mapping covers all security event types from Phases 10, 13, 12, 8, 17, 18
- All 7 required audit events emitted on trigger conditions
