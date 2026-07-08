# Phase 11: Operational Observability & Compliance Infrastructure - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 11 delivers enterprise observability and compliance infrastructure: SLO tracking with breach alerting, immutable tamper-evident audit trail with 7-year configurable retention, and supply chain SBOM generation. Adds PostgreSQL as persistent store, Prometheus+Grafana for metrics, and MinIO/S3 WORM for audit archive.

</domain>

<decisions>
## Implementation Decisions

### Storage Architecture
- **D-001:** PostgreSQL (separate container, Alembic migrations) for SLO counters and audit event storage
- **D-002:** Valkey remains for real-time counters only (ephemeral, fast reads)
- **D-003:** Object storage (MinIO/S3 WORM bucket) for monthly audit exports (gzipped JSONL + Parquet)
- **D-004:** Metrics backend: Prometheus + Grafana

### Audit Trail
- **D-005:** Every audit event has tamper-evident hash chain: event_id, prev_hash, hash (SHA-384, FIPS-compliant)
- **D-006:** Daily chain anchoring: compute daily_root_hash, sign, store in PostgreSQL + archive with exports
- **D-007:** Audit event schema: timestamp, tenant_id, request_id, policy_id, decision, provider, latency_ms, hash
- **D-008:** Append-only — no modify or delete API (except Legal Hold)
- **D-009:** Retention: tenant-configurable, default = 7 years

### Export Format
- **D-010:** Monthly exports: audit-YYYY-MM.jsonl.gz + audit-YYYY-MM.parquet
- **D-011:** Parquet for analytics tooling (Splunk, Snowflake, Databricks, BigQuery)

### SLO Tracking
- **D-012:** Both compliance windows (fixed calendar: daily/monthly) AND operational windows (rolling 24h/30d)
- **D-013:** SLO targets: success ≥ 99.9%, P95 ≤ 100ms, fail-secure ≤ 0.1%, audit write ≥ 99.99%
- **D-014:** GET /v1/governance/status with per-SLO compliance, last breach timestamps

### Breach Alerting
- **D-015:** Webhook with dead letter queue — POST to configured URL, retry 3x with exponential backoff, failed deliveries to DLQ
- **D-016:** GET /v1/governance/breaches endpoint for polling
- **D-017:** SLO breach log entry event_type: slo_breach_detected

### SBOM
- **D-018:** CI/CD: CycloneDX JSON SBOM (all Python deps) per release
- **D-019:** Container: Syft for OS packages + Python + model artifacts
- **D-020:** Supply chain: cosign OCI attestation, published as release artifact
- **D-021:** Dependabot weekly scans; CVSS ≥ 9.0 auto-issue within 24h
- **D-022:** Docs: docs/operations/slo-runbook.md, docs/security/incident-response.md, SECURITY.md

### Docker Compose Additions
- **D-023:** New postgres:16 service with persistent volume + Alembic migrations
- **D-024:** New minio service for object storage (WORM bucket)
- **D-025:** Prometheus + Grafana services

### Metrics from OBS-04
- **D-026:** anonreq_rate_limit_hits_total, anonreq_spend_limit_hits_total, anonreq_tenant_active_sessions, anonreq_config_reload_total — add to Prometheus

### the agent's Discretion
- Exact Grafana dashboard layout and panels
- PostgreSQL schema design details
- Alembic migration naming conventions
- Prometheus recording rules for SLO computation
- MinIO WORM bucket configuration
- Webhook format and delivery details
- Audit event signing key management
- Parquet schema definition

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` §Phase 11 — Goal and success criteria
- `.planning/REQUIREMENTS.md` §Req 24 — OBS-01 through OBS-05
- `.planning/REQUIREMENTS.md` §Req 25 — AUDT-CFG-01 through AUDT-CFG-06
- `.planning/REQUIREMENTS.md` §Req 26 — SBOM-01 through SBOM-06
- `.planning/phases/05-configuration-observability/05-CONTEXT.md` — Existing config system, metrics registry, audit logger
- `.planning/phases/08-Enterprise-Policy-Engine/08-CONTEXT.md` — Policy decisions as audit events
- Docker Compose from Phase 1 — New services: postgres, minio, prometheus, grafana

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 5 AuditLogger — structured JSON logging, extended for hash chain
- Phase 5 MetricsRegistry — Prometheus counters, extended for OBS-04 metrics
- Phase 5 Config hot-reload — config changes trigger audit events
- Phase 8 Policy decisions — audit events with policy decisions

### New Dependencies
- PostgreSQL 16 (new container)
- MinIO (new container, WORM bucket)
- Prometheus + Grafana (new containers)
- Alembic (Python migration framework)

### Integration Points
- Existing config system → emit AUDT-CFG events on change
- Policy engine → emit policy decision audit events
- Detection pipeline → emit SLO counters
- ForwardingGuard → emit success/failure for SLO computation

</code_context>

<specifics>
## Specific Ideas

- Hash chain anchors prevent retroactive chain rewriting even with DB access
- JSONL + Parquet dual export covers compliance reporting + analytics
- MinIO WORM bucket provides immutable, retention-compliant archive without enterprise storage vendor
- Tenant-configurable retention instead of hardcoded 7 years

</specifics>

<deferred>
## Deferred Ideas

- Advanced audit analytics dashboards (Phase 20 SOC/SIEM)
- Automated compliance report generation (Phase 14/15)
- Audit event streaming to external SIEM (Phase 20)

</deferred>

---

*Phase: 11-operational-observability-compliance*
*Context gathered: 2026-06-20*
