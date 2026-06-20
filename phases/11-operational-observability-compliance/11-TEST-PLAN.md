# Phase 11 Test Plan: Operational Observability & Compliance

## Unit Tests
- Hash chain: event hash computed correctly from fields
- Hash chain: prev_hash references correct previous event
- SLO computation: fixed windows (daily, monthly) calculate correct percentages
- SLO computation: rolling windows (24h, 30d) calculate correct percentages
- Audit event schema validation
- Export: JSONL format generates correctly
- Export: Parquet schema matches specification

## Integration Tests
- Audit event ingested → stored with correct hash chain
- Daily anchor computed → signed → stored
- SLO breach detection → webhook fired
- Webhook delivery failure → queued to dead letter
- GET /v1/governance/status returns per-SLO compliance
- GET /v1/admin/audit/config-history paginated + filtered
- GET /v1/admin/audit/config-history/export returns valid JSONL
- Monthly export written to MinIO WORM bucket

## Security Tests
- Hash chain tampering detected (modify an event → hash chain breaks)
- Daily anchor tampering detected (modify anchor → verification fails)
- Append-only enforced (no modify/delete API)
- Config audit trail cannot be bypassed
- No raw PII in audit events

## Property Tests
- Hash chain linear integrity: any modification detectable
- SLO counters monotonic: request count never decreases
- Export round-trip: JSONL events match PostgreSQL events
