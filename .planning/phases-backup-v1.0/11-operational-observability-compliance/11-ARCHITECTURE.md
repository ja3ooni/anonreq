# Phase 11 Architecture: Operational Observability & Compliance

## Architecture

```
Gateway
   ↓
Events
   ↓
 ┌─────────────────────────────────────┐
 │ PostgreSQL (Compliance DB)          │
 │  - SLO counters                     │
 │  - Audit trail (hash-chained)       │
 │  - Daily chain anchors              │
 │  - Tenant configurable retention    │
 └─────────────────────────────────────┘
   ↓
Valkey (real-time counters)
   ↓
Prometheus (metrics)
   ↓
Grafana (dashboards)
   ↓
Audit Exporter
   ├── JSONL (monthly archive)
   └── Parquet (analytics)
   ↓
Object Storage (MinIO/S3 WORM)
   ↓
7-Year Retention
```

## Data Flow

### Audit Event Flow
1. Event generated (policy decision, config change, SLO breach)
2. Event_id + prev_hash computed
3. SHA-384 hash computed over event fields
4. Event stored in PostgreSQL
5. At end of day: daily_root_hash computed, signed, stored in PostgreSQL + archive
6. Monthly: events exported to JSONL.gz + Parquet, pushed to MinIO WORM

### SLO Computation
1. Per-request counters in Valkey (real-time)
2. Scheduled job computes SLO from PostgreSQL event store
3. Compliance windows (fixed daily/monthly) + operational windows (rolling 24h/30d)
4. Breach detection fires webhook on SLO threshold exceeded

## Hash Chain Structure
```json
{
  "event_id": "evt_abc123",
  "prev_hash": "sha384-...",
  "hash": "sha384-...",
  "timestamp": "...",
  "tenant_id": "...",
  "request_id": "...",
  "policy_id": "...",
  "decision": "...",
  "provider": "...",
  "latency_ms": 42
}
```

## Docker Compose Additions
- postgres:16 (persistent volume)
- minio (WORM bucket)
- prometheus
- grafana
