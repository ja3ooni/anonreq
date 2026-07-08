# Phase 15: Financial Services Compliance - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 15 delivers financial-sector regulatory compliance: MNPI protection with SEC 17a-4 retention, Model Risk Management (SR 11-7), third-party provider oversight (DORA ICT), financial crime controls (context-word boosting, AML webhook), and DORA operational resilience with configurable incident escalation.

</domain>

<decisions>
## Implementation Decisions

### MNPI Protection
- **D-001:** New Presidio recognizer bundle for MNPI: ticker symbols, deal codenames, restricted names
- **D-002:** Tenant-configurable restricted-names list, hot-reloadable
- **D-003:** 4 MNPI policies: anonymize_and_forward, flag_and_forward, block, quarantine
- **D-004:** SEC 17a-4 retention via dedicated MinIO WORM bucket (separate from Phase 11 compliance bucket)

### Model Risk Management (SR 11-7)
- **D-005:** Hybrid: MRM concepts embedded in Phase 14 governance lifecycle
- **D-006:** Model inventory with fields: risk classification, approval status, review cycles
- **D-007:** Approval gating: unapproved models blocked at ForwardingGuard
- **D-008:** SR 11-7 alignment documentation

### Third-Party Provider Oversight (DORA ICT)
- **D-009:** Provider inventory in PostgreSQL + Phase 14 governance versioning
- **D-010:** DORA ICT concentration risk flagging per provider
- **D-011:** Provider suspension endpoint (POST /v1/admin/providers/{id}/suspend)
- **D-012:** Annual concentration risk justification for critical providers

### Financial Crime Controls
- **D-013:** Context-word boosting: Presidio context-aware enhancement. High-risk words within 50 chars of entity → confidence +0.15 (capped at 1.0)
- **D-014:** AML webhook: configurable threshold per tenant, metadata-only payload
- **D-015:** Financial crime entity types: IBAN, payment refs, customer IDs, AML case refs

### DORA Operational Resilience
- **D-016:** Incident auto-escalation with configurable rules per service criticality
- **D-017:** Criticality tiers: critical (slo_breach + auto_incident + notify), important (slo_breach only), standard (no escalation)
- **D-018:** Critical service classification triggers enhanced monitoring

### Compliance Reports
- **D-019:** Both: dynamic generation (GET /v1/admin/compliance/report?framework={id}) + exportable template
- **D-020:** Frameworks: DORA, NIS2, GDPR, ISO 27001/42001, EBA, FCA, SEC, FINRA
- **D-021:** Compliance mapping document docs/compliance/financial-services-mapping.md

### the agent's Discretion
- MNPI recognizer implementation details (ticker patterns, codename conventions)
- Restricted-names list hot-reload mechanism
- Model inventory schema details
- Provider suspension implementation
- AML webhook payload format
- DORA incident record schema
- Compliance report template format

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` §Phase 15 — Goal and 6 success criteria
- `.planning/REQUIREMENTS.md` §Req 37-40, 42-43
- `.planning/phases/14-ai-governance-oversight/14-CONTEXT.md` — Governance lifecycle, versioning
- `.planning/phases/11-operational-observability-compliance/11-CONTEXT.md` — PostgreSQL, MinIO WORM
- `.planning/phases/02-core-pipeline-classification-non-streaming/02-CONTEXT.md` — Presidio detection pipeline
- `.planning/phases/04-multi-locale-detection-compliance-presets/04-CONTEXT.md` — Locale for MNPI

</canonical_refs>

</domain>

*Phase: 15-financial-services-compliance*
*Context gathered: 2026-06-20*
