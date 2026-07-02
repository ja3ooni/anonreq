# Phase 16: Compliance, Audit & Fairness - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 16 delivers enterprise compliance, audit, and fairness capabilities: fairness testing (CI/CD + monitoring), third-party AI supplier governance, post-deployment monitoring, immutable data lineage, Legal Hold, data subject rights, and breach notification automation.

</domain>

<decisions>
## Implementation Decisions

### Fairness Testing
- **D-001:** CI/CD bias assessment on every release: recall disparity across demographic groups ≤ 0.05
- **D-002:** + Runtime fairness monitoring: alert if production drift exceeds threshold
- **D-003:** Fairness datasets stored in MinIO bucket by content hash
- **D-004:** Dataset metadata: id, sha256, owner, approved_by, approval_date, framework, version
- **D-005:** Per locale, 200+ examples per demographic group

### Post-Deployment Monitoring
- **D-006:** Extends Phase 11 SLO framework
- **D-007:** Metrics: detection quality drift, fail-secure frequency, SLO compliance
- **D-008:** Incident classification: Critical (notify immediate), High (24h), Medium (72h), Low (next review cycle)

### Data Lineage
- **D-009:** Per-session immutable lineage: session_id, timestamps, provider, model, entities, policies
- **D-010:** Storage: PostgreSQL (queryable) + MinIO archive (per-session JSONL)
- **D-011:** No API to modify or delete lineage records

### Third-Party AI Supplier Governance
- **D-012:** Provider inventory with contract/risk/review status
- **D-013:** Provider review cycle: default 365 days
- **D-014:** Uses Phase 14 lifecycle stages
- **D-015:** Risk re-evaluation triggers: model changes, ToS changes, data residency changes, new AI Act classification, security incident
- **D-016:** Overdue reviews surfaced in governance status (GET /v1/governance/status)

### Retention
- **D-017:** Tiered retention: PostgreSQL 90 days (operational queries), MinIO WORM 7 years (compliance archive), Valkey TTL (token mappings), Legal Hold infinite until release

### Legal Hold
- **D-018:** Tenant-level hold + record-level tagging
- **D-019:** Hold suspension blocks deletion across all storage tiers
- **D-020:** Release of hold triggers normal retention policy

### Data Subject Rights
- **D-021:** DSAR workflow: intake → retention check → execute
- **D-022:** No hold → delete mapping (Valkey token→entity mappings)
- **D-023:** Hold exists → restrict processing (mark subject as restricted, block future requests)
- **D-024:** Result: subject_status { deleted, processing_restricted, legal_hold }
- **D-025:** Supports erasure, rectification, portability, and restriction

### Breach Notification
- **D-026:** Configurable templates per framework/region
- **D-027:** Regulator notification queue
- **D-028:** Affected-tenant notification workflow
- **D-029:** Notification contacts in governance records + escalation path

### eDiscovery Export
- **D-030:** Formats: JSONL + PDF summary + EDRM XML

### the agent's Discretion
- Fairness metric implementation details (recall disparity calculation)
- Incident record schema
- DSAR workflow API design
- Breach notification template format
- Legal Hold record schema
- Provider risk re-evaluation scoring

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` §Phase 16 — Goal and 7 success criteria
- `.planning/REQUIREMENTS.md` §Req 32-34, 44-47
- `.planning/phases/11-operational-observability-compliance/11-CONTEXT.md` — SLO framework, PostgreSQL, MinIO WORM
- `.planning/phases/14-ai-governance-oversight/14-CONTEXT.md` — Governance lifecycle, versioning
- `.planning/phases/04-multi-locale-detection-compliance-presets/04-CONTEXT.md` — Locale data for fairness
- `.planning/phases/15-financial-services-compliance/15-CONTEXT.md` — DORA resilience, SEC 17a-4

</canonical_refs>

---

*Phase: 16-compliance-audit-fairness*
*Context gathered: 2026-06-20*
