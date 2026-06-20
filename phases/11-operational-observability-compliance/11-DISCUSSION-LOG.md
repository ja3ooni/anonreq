# Phase 11: Operational Observability & Compliance - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-20
**Phase:** 11-operational-observability-compliance
**Areas discussed:** SLO Storage, Audit Storage, Breach Alerting, SBOM Approach, SLO Windows, Hash Algorithm, PostgreSQL Deploy, Audit Anchoring, Metrics Backend, Retention, Audit Schema, Export Format

---

## SLO Storage
| Option | Selected |
|--------|----------|
| In-memory + Valkey | |
| SQLite | |
| PostgreSQL (separate container) | ✓ |

**User's choice:** PostgreSQL (separate container).

## Audit Trail Storage
**User's choice:** PostgreSQL + Object Storage (MinIO/S3 WORM) + Hash Chain. Monthly exports: audit-YYYY-MM.jsonl.gz + .parquet.

## Breach Alerting
| Option | Selected |
|--------|----------|
| Simple POST + retry | |
| Webhook + dedicated endpoint | |
| Webhook with dead letter queue | ✓ |

**User's choice:** Webhook with DLQ.

## SBOM Approach
| Option | Selected |
|--------|----------|
| CI/CD only | |
| CI/CD + container | |
| Full: CI + container + attestation | ✓ |

**User's choice:** Full pipeline: CycloneDX + Syft + cosign.

## SLO Windows
**User's choice:** Both — fixed calendar (daily/monthly) for compliance + rolling (24h/30d) for ops.

## Hash Algorithm
**User's choice:** SHA-384 (FIPS).

## Audit Integrity Anchoring
**User's choice:** Daily chain anchoring. Daily_root_hash signed and stored. Prevents full-chain rewrite by attacker with DB access.

## Metrics Backend
**User's choice:** Prometheus + Grafana.

## Retention
**User's choice:** Tenant-configurable, default = 7 years.

## Audit Event Schema
**User's choice:** Standard schema: timestamp, tenant_id, request_id, policy_id, decision, provider, latency_ms, hash.

## Export Format
**User's choice:** JSONL + Parquet. Parquet for analytics (Splunk, Snowflake, Databricks, BigQuery).

## Deferred Ideas
- Advanced audit analytics (Phase 20)
- Automated compliance report generation (Phase 14/15)
- Event streaming to external SIEM (Phase 20)
