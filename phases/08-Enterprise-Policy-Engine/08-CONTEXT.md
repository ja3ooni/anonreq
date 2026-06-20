# Phase 08: Enterprise Policy Engine - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 8 delivers the Enterprise Policy Engine framework — a dual-gate Policy Decision Point / Policy Enforcement Point (PDP/PEP) architecture that enterprise controls plug into. This is the foundation for all future enterprise policy features (rate limiting, spend controls, DLP, AI firewall, CASB).

Rate limiting and spend controls are explicitly deferred to later phases as policy plugins built on top of this framework.

</domain>

<decisions>
## Implementation Decisions

### Scope & Positioning
- **D-001:** Phase 8 is the Enterprise Policy Engine framework, not just rate limiting. Implements the PDP/PEP architecture that future enterprise controls plug into.
- **D-002:** Rate limiting and spend controls are deferred to a later phase as policy plugins.

### Architecture: Dual-Gate PDP
- **D-003:** Two PDP/PEP gates in the request lifecycle:
  - PDP #1 (Pre-Detection): Fast metadata-based decisions before classification/anonymization. Actions: BLOCK, ROUTE_LOCAL, PASS.
  - PDP #2 (Post-Classification): Context-aware decisions using detected entities, risk scores, classification levels. Actions: PASS, ANONYMIZE, ROUTE_PROVIDER, ROUTE_LOCAL, REQUIRE_APPROVAL, BLOCK.
- **D-004:** PDP runs before ForwardingGuard as a separate step.

### Policy Model
- **D-005:** Declarative YAML policy format with sections: version, tenant, defaults, classification, jurisdiction, departments.
- **D-006:** Internally compiled to PolicyBundle model with Rules, RoutingRules, JurisdictionRules, DepartmentRules.
- **D-007:** Hybrid storage: YAML files as source of truth (versioned in Git), compiled to internal PolicyBundle at startup/reload. Optional Valkey caching for compiled snapshots only. Valkey is never the authoritative policy store.
- **D-008:** Tenant → Department hierarchy: Global → Tenant → Department scope precedence. More specific overrides less specific. Evaluation order: Global → Tenant → Department → Request Context.

### Policy Evaluation
- **D-009:** Evaluation model: Combine (priority + first-match). Collect matching rules, sort by priority (highest first). Apply DENY first, then ALLOW, then ROUTE. Multiple ROUTE at same priority: first-match wins. No match: BLOCK by default.
- **D-010:** Decision precedence: BLOCK > REQUIRE_APPROVAL > ROUTE_LOCAL > ROUTE_PROVIDER > ALLOW. Most restrictive action wins.

### Policy Actions
- **D-011:** Action types: PASS (skip anonymization, forward as-is), ANONYMIZE, ROUTE_LOCAL, ROUTE_PROVIDER, REQUIRE_APPROVAL, BLOCK.
- **D-012:** REQUIRE_APPROVAL action type defined now; approval flow implementation deferred to later phase.

### Classification
- **D-013:** Classification-to-entity mapping is hybrid: sensible defaults in Python code, overridable in policy YAML.

### Jurisdiction
- **D-014:** Jurisdiction rules are country-based and defined in the policy YAML.

### Admin API
- **D-015:** Full CRUD for policies: GET/POST/PUT/DELETE for /v1/admin/policies and /v1/admin/tenants/{id}/policies.

### Configuration Reload
- **D-016:** Both mechanisms: file watch (inotify/kqueue) for dev convenience + POST /v1/admin/policies/reload endpoint for production GitOps workflows.

### Audit & Observability
- **D-017:** Policy decision audit records: action, policy_version, matched_scope. Decision summary level — not full matched conditions.

### Canonical YAML Example
```yaml
version: 1
tenant: acme-bank
defaults:
  route: openai
classification:
  source_code:
    action: route_local
  pii:
    action: anonymize
jurisdiction:
  eu:
    allowed_providers:
      - openai-eu
      - mistral
departments:
  legal:
    route: local-llama
  engineering:
    route: anthropic
```

### the agent's Discretion
- PDP #1 match condition syntax (IP, payload size, application patterns)
- PDP #2 classification level threshold definitions
- CRUD API endpoint design details (request/response schemas)
- Valkey cache key schema for compiled policy snapshots
- File watch implementation details (library choice, polling interval)
- Policy compilation/validation exact logic
- Multi-tenant policy directory structure

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Boundary & Requirements
- `.planning/ROADMAP.md` §Phase 8 — Phase 8 goal and success criteria
- `.planning/ARCHITECTURE_GUARDRAILS.md` §Phase 8 — Multi-tenant platform guidance
- `.planning/REQUIREMENTS.md` — Req 21, 22, 29, 30, 36, 41, 46, 48, 49
- `req/requirements_v2.md` — Enterprise/appliance requirements (Req 22–56)

### Architecture & Integration
- `.planning/phases/01-foundation-fail-secure-auth/01-CONTEXT.md` — ForwardingGuard, request context, FastAPI middleware patterns
- `.planning/phases/02-core-pipeline-classification-non-streaming/02-CONTEXT.md` — Classification tiers, detection pipeline, entity types
- `.planning/phases/05-configuration-observability/05-CONTEXT.md` — Existing config patterns, audit logger, metrics registry

### Policy Engine Design
- `phases/08-Enterprise-Policy-Engine/08-SECURITY-ACCEPTANCE.md` — Security acceptance gates
- `phases/08-Enterprise-Policy-Engine/08-TEST-PLAN.md` — Test plan template
- `phases/08-Enterprise-Policy-Engine/08-ARCHITECTURE.md` — Existing batch-generated architecture doc

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- ForwardingGuard from Phase 1 — PDP sits before it, PDP decision gates whether ForwardingGuard fires
- RequestContext from Phase 1 — carries tenant_id, metadata that PDP #1 consumes
- AuditLogger from Phase 5 — structured JSON logging, extended for policy decision events
- MetricsRegistry from Phase 5 — Prometheus counters extended for policy metrics
- Valkey client from Phase 1 — optional caching for compiled policy snapshots

### Established Patterns
- Fail-secure: any policy evaluation failure returns HTTP 5xx, never forwards unsanitized
- Metadata-only audit: policy decisions record action + policy_version + matched_scope, never raw payloads
- Config loaded at startup with validation, hot-reload supported

### Integration Points
- PDP #1 intercepts request before detection pipeline
- PDP #2 intercepts after detection pipeline, before ForwardingGuard
- Policy CRUD API as new /v1/admin/ route group
- Policy reload endpoint as new admin capability
- Policy decision audit events emitted to existing audit logger

</code_context>

<specifics>
## Specific Ideas

- Modeled after Zscaler/Netskope/Palo Alto dual-gate architecture: fast policy → inspection → advanced policy
- YAML as source of truth mirrors Kubernetes-style declarative config
- Compiled PolicyBundle approach follows the existing config compilation pattern from Phase 5

</specifics>

<deferred>
## Deferred Ideas

- Rate limiting policy plugin (future phase)
- Spend control policy plugin (future phase)
- REQUIRE_APPROVAL implementation (future phase — action type defined now)
- Data residency routing implementation details (future phase)
- AI firewall, DLP, MCP Governance, CASB (future enterprise phases — plug into PDP #2)

</deferred>

---

*Phase: 08-Enterprise-Policy-Engine*
*Context gathered: 2026-06-20*
