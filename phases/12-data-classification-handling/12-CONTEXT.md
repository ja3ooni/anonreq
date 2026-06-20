# Phase 12: Data Classification & Handling Policies - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 12 adds data classification to every request: 5 sensitivity levels (Public, Internal, Confidential, Restricted, Highly Restricted), auto-classification by highest-sensitivity detected entity, client-asserted classification override (increase only, never decrease), and per-level handling policies that feed into PDP #2.

</domain>

<decisions>
## Implementation Decisions

### Classification Levels
- **D-001:** Fixed enum in code: Public, Internal, Confidential, Restricted, Highly Restricted
- **D-002:** Display names configurable in policy YAML (Phase 8) per tenant
- **D-003:** Undetected defaults to Internal

### Auto-Classification
- **D-004:** Deterministic highest-sensitivity calculation: `highest = max(entity_mapping[e] for e in entities)`
- **D-005:** No AI, no scoring, no confidence blending. Purely deterministic mapping.
- **D-006:** All detected entity labels preserved in result alongside highest classification

### Entity-Type-to-Classification Mapping
- **D-007:** Default mapping in Python code (sensible defaults per entity type)
- **D-008:** Overridable per tenant in Phase 8 policy YAML

### Client-Asserted Classification
- **D-009:** Client may never decrease classification. Client may increase classification.
- **D-010:** Higher of client-asserted vs detected wins. All overrides logged.
- **D-011:** This allows enterprise use cases: M&A documents, board materials, trade secrets, unreleased products that detection models won't recognize.

### Per-Level Handling Policies
- **D-012:** Defaults: Public/Internal → PASS, Confidential → ANONYMIZE, Restricted → ANONYMIZE + AUDIT, Highly Restricted → BLOCK
- **D-013:** Overridable in Phase 8 policy YAML per tenant
- **D-014:** Classification result feeds into PDP #2 for policy evaluation

### Audit & Observability
- **D-015:** Classification_Level stamped on RequestContext after detection
- **D-016:** Classification in every audit log entry via RequestContext
- **D-017:** Response header X-AnonReq-Classification-Result only when explicitly requested via X-AnonReq-Debug: true or X-AnonReq-Return-Classification: true

### Integration with Phase 8
- **D-018:** Classification mapping and per-level handling policies live in Phase 8 policy YAML
- **D-019:** Classification result is an input to PDP #2 for policy-based routing/blocking decisions

### the agent's Discretion
- Default entity-to-classification mapping table (e.g., PERSON → Internal, IBAN → Restricted, SOURCE_CODE → Highly Restricted)
- Exact RequestContext field name for classification
- Debug header parsing and validation
- Policy YAML section naming conventions for classification config

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` §Phase 12 — Goal and success criteria
- `.planning/REQUIREMENTS.md` §Req 41 — CLASS-01 through CLASS-05
- `.planning/phases/08-Enterprise-Policy-Engine/08-CONTEXT.md` — Policy YAML format, PDP #2 integration
- `.planning/phases/02-core-pipeline-classification-non-streaming/02-CONTEXT.md` — Entity types, detection pipeline

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 2 entity detection — provides entity types for classification mapping
- Phase 8 Policy YAML — classification config lives here
- Phase 8 PDP #2 — receives classification result as policy input
- Phase 5 AuditLogger — reads classification from RequestContext

### Integration Points
- Classification computed after Phase 2 entity detection
- Classification stamped on RequestContext before PDP #2
- Classification consumed by Phase 8 PDP #2 for policy evaluation
- Classification logged by Phase 5 AuditLogger via RequestContext

</code_context>

<specifics>
## Specific Ideas

- Deterministic max ensures auditable, explainable classification for regulated enterprises
- Client increase-only mirrors enterprise DLP classification models (customer can mark docs more sensitive, never less)
- Defaults-to-Internal avoids unclassified data being treated as public
- Classification in PDP #2 enables policy-based routing by sensitivity

</specifics>

<deferred>
## Deferred Ideas

- Advanced classification rules (ML-based confidence blending) — not needed, explicit design choice
- Classification override webhook for external DLP integration (future)
- Dynamic classification level creation (beyond fixed enum — not planned)

</deferred>

---

*Phase: 12-data-classification-handling*
*Context gathered: 2026-06-20*
