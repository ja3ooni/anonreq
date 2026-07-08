---
phase: 20-ai-soc-siem-integration
plan: 03
status: complete
subsystem: soc
tags:
  - siem-sinks
  - sentinel
  - elastic
  - datadog
  - tdd
requires:
  - 20-01
  - 20-02
provides:
  - sentinel_dcr_sink
  - elastic_bulk_sink
  - datadog_logs_sink
affects:
  - src/anonreq/soc/sinks/__init__.py
tech-stack:
  added:
    - httpx (async HTTP client for all three sinks)
    - respx (HTTP mocking for tests)
    - prometheus_client (counter metrics per sink)
  patterns:
    - SinkBase protocol from 20-02
    - OAuth2 client_credentials token acquisition with caching
    - NDJSON formatting with action_meta + event pairs
    - JSON array batching for log APIs
key-files:
  created:
    - src/anonreq/soc/sinks/sentinel_dcr.py
    - src/anonreq/soc/sinks/elastic_bulk.py
    - src/anonreq/soc/sinks/datadog_logs.py
    - tests/test_soc_sink_sentinel_dcr.py
    - tests/test_soc_sink_elastic_bulk.py
    - tests/test_soc_sink_datadog_logs.py
metrics:
  duration: ~20 min
  tasks: 3
  tests: 34
  passed: 34
  failed: 0
decisions: []
completed_date: 2026-07-05
---

# Phase 20 Plan 03: Cloud SIEM Sinks Summary

**One-liner:** Implemented Azure Sentinel (DCR API), Elastic Security (Bulk API), and Datadog (Logs API) SIEM sinks — all implementing the SinkBase protocol with OAuth2 token handling, NDJSON formatting, and JSON array batching — 34 tests passing.

## Key Results

| Sink | Source File | Auth | Wire Format | Endpoint |
|------|------------|------|-------------|----------|
| Sentinel DCR | `sentinel_dcr.py` | OAuth2 Bearer token | DCR stream records (JSON array) | Azure DCR API |
| Elastic Bulk | `elastic_bulk.py` | ApiKey header | NDJSON (action_meta + event) | `/_bulk` |
| Datadog Logs | `datadog_logs.py` | DD-API-KEY header | JSON array | `/api/v2/logs` |

## Task Results

### Task 1: Sentinel DCR Sink (11 tests)
- OAuth2 `client_credentials` grant to Azure AD
- Token caching with 5-minute refresh buffer before expiry
- DCR stream POST with `Bearer {token}` auth
- Health check validates token acquisition
- Prometheus counter: `anonreq_soc_sink_sentinel_dcr_total`

### Task 2: Elastic Bulk Sink (12 tests)
- NDJSON format: `{"create": {"_index": "...", "_id": "..."}}` + event body
- Configurable index pattern with `strftime` date substitution (default: `anonreq-ai-security-%Y.%m.%d`)
- API key auth with auto-base64 encoding of raw keys
- Batch send support
- Bulk response error detection (HTTP 200 + `errors: true` → False)
- Prometheus counter: `anonreq_soc_sink_elastic_bulk_total`

### Task 3: Datadog Logs Sink (11 tests)
- JSON log entry format: ddsource, ddtags, hostname, service, message
- DD-API-KEY auth header
- Configurable site (datadoghq.com, .eu, us3, ddog-gov)
- Configurable source tag (default: `anonreq`)
- Batch send support
- Health check sends test event
- Prometheus counter: `anonreq_soc_sink_datadog_logs_total`

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

All 34 tests pass. All 3 source files created. All 3 test files created.
