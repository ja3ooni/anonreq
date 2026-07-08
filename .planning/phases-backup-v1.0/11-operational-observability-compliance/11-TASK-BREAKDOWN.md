# Phase 11 Task Breakdown: Operational Observability & Compliance

## Epics
1. PostgreSQL schema + Alembic migrations
2. Audit event ingestion with hash chain
3. Daily chain anchoring service
4. SLO computation engine (fixed + rolling windows)
5. Breach detection + webhook delivery
6. Compliance export (JSONL + Parquet) to object storage
7. SBOM generation in CI/CD
8. Prometheus + Grafana integration
9. Docker Compose updates

## Stories
- As a security officer, every config change produces an immutable hash-chained audit entry
- As a security officer, daily audit chain anchors prevent retroactive tampering
- As an SRE, SLO compliance is viewable at GET /v1/governance/status
- As an SRE, SLO breaches trigger alerts via configurable webhook
- As a compliance officer, monthly audit exports (JSONL + Parquet) are available in object storage
- As a security engineer, CycloneDX SBOMs are generated per release with cosign attestation

## Tasks
- Create PostgreSQL audit_event table with hash chain columns
- Implement Alembic migrations
- Implement audit event ingestion endpoint
- Implement SHA-384 hash chaining
- Implement daily chain anchoring (compute, sign, store)
- Implement SLO counter storage in Valkey
- Implement SLO computation engine (fixed + rolling)
- Implement GET /v1/governance/status
- Implement breach detection + webhook with DLQ
- Implement GET /v1/admin/audit/config-history (paginated + filterable)
- Implement GET /v1/admin/audit/config-history/export (JSONL)
- Implement monthly audit exporter (JSONL + Parquet → MinIO)
- Add SBOM generation steps to Dockerfile/release pipeline
- Add Prometheus/Grafana dashboards
- Update Docker Compose with postgres, minio, prometheus, grafana
- Add docs/operations/slo-runbook.md
- Add docs/security/incident-response.md
- Add SECURITY.md
