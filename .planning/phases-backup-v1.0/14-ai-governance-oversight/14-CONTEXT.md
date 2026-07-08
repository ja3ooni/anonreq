# Phase 14: AI Governance & Oversight - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 14 delivers a structured AI governance framework aligned with ISO/IEC 42001:2023 and EU AI Act. Governance records, risk assessments (6 dimensions), human oversight (approval queue, kill-switch), transparency (headers + periodic reports + status endpoint), lifecycle management (6 stages), and conformity assessment packages. All governance objects are versioned forever with approval and diff history.

</domain>

<decisions>
## Implementation Decisions

### Governance Records
- **D-001:** Per-tenant governance records with named owners (governance, risk, compliance, security)
- **D-002:** Governance review cycle: default 90 days, configurable per tenant
- **D-003:** Overdue reviews surfaced in GET /v1/governance/status + notifications
- **D-004:** Governance data stored in PostgreSQL (Phase 11 infrastructure)
- **D-005:** Review notifications: webhook + admin API + optional SMTP email

### Risk Assessments
- **D-006:** 6 risk dimensions: hybrid — fixed ISO/IEC 42001 core + tenant extensions
- **D-007:** Risk dimensions include privacy, security, bias, explainability, fairness, safety (core)
- **D-008:** Scoring: severity + likelihood per dimension, with treatment plans
- **D-009:** Config changes affecting entity types trigger reassessment flag

### Human Oversight
- **D-010:** Approval queue for high-risk requests → HTTP 202 pending
- **D-011:** Approve/reject endpoints per approval request
- **D-012:** Kill-switch: both global (POST /v1/oversight/kill-switch) AND per-tenant (POST /v1/oversight/kill-switch/{tenant_id})
- **D-013:** Session summary endpoint (metadata only, no raw content)
- **D-014:** Approval queue in PostgreSQL + approval actions in immutable audit trail (Phase 11 hash chain)

### Governance Object Versioning
- **D-015:** All governance objects versioned forever — never overwrite
- **D-016:** Versioning applies to: policies, providers, presets
- **D-017:** Per-version: approval history, diff history (what changed), rollback support
- **D-018:** This enables audit answers: who changed what, when, why, and what exactly changed

### Lifecycle Management
- **D-019:** 6 lifecycle stages: DRAFT → REVIEW → APPROVED → PRODUCTION → DEPRECATED → RETIRED
- **D-020:** Stage transitions require approvals
- **D-021:** Production activation gates: completed testing + risk assessment + governance approval

### Transparency
- **D-022:** Response headers: X-AnonReq-Processed (true/false), X-AnonReq-Entity-Count (N)
- **D-023:** Periodic transparency reports (monthly, configurable)
- **D-024:** Real-time status endpoint: GET /v1/governance/transparency with current period aggregated stats
- **D-025:** Transparency records per session (metadata only)
- **D-026:** No raw content in transparency records

### Conformity Assessment
- **D-027:** Both: on-demand dynamic generation (GET /v1/admin/compliance/conformity-package returns fresh ZIP)
- **D-028:** AND release-time snapshot as static artifact
- **D-029:** Package includes: SBOM, governance export, risk assessments, config audit history, bias report, manifest

### the agent's Discretion
- Exact governance record schema (owners, review dates, fields)
- Risk scoring methodology (1-5 scale, likelihood definitions)
- Approval queue API design (request/response schemas)
- Kill-switch implementation mechanism (global flag, per-tenant flag)
- Version diff format (JSON Patch, YAML diff)
- Email notification template
- Transparency report format and content

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` §Phase 14 — Goal and 6 success criteria
- `.planning/REQUIREMENTS.md` §Req 27-31, 35 — Governance, Risk, Oversight, Transparency, Lifecycle, Conformity
- `req/requirements_v2.md` — Enterprise governance requirements
- `.planning/phases/11-operational-observability-compliance/11-CONTEXT.md` — PostgreSQL, hash chain, audit infrastructure
- `.planning/phases/08-Enterprise-Policy-Engine/08-CONTEXT.md` — Policy versioning integration

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 11 PostgreSQL — governance records, approval queue, version storage
- Phase 11 Audit Trail — immutable logging of governance actions
- Phase 8 Policy Engine — policies are governance objects that need versioning
- Phase 5 Config — provider and preset configurations that need lifecycle management

### Integration Points
- Kill-switch feeds into ForwardingGuard (block all provider traffic)
- Approval queue linked to PDP #2 (REQUIRE_APPROVAL action)
- Version history enhances Phase 8 policy CRUD
- Transparency headers added to all responses

</code_context>

<specifics>
## Specific Ideas

- Version-forever model mirrors infrastructure-as-code best practices (Terraform, Kubernetes)
- Dual kill-switch (global + per-tenant) follows enterprise security pattern (Datadog, CrowdStrike)
- Transparency headers + periodic reports cover both real-time and retrospective compliance
- 6 lifecycle stages align with ISO/IEC 42001 AI system lifecycle

</specifics>

<deferred>
## Deferred Ideas

- Automated policy migration between stages (future pipeline)
- Advanced risk assessment workflows with external scoring (future)
- Governance dashboard UI (Phase 14 Admin Portal — actually a frontend concern)

</deferred>

---

*Phase: 14-ai-governance-oversight*
*Context gathered: 2026-06-20*
