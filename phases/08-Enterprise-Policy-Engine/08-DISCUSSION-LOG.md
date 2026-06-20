# Phase 08: Enterprise Policy Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 08-Enterprise-Policy-Engine
**Areas discussed:** Scope, Lifecycle Position, Policy Storage, Tenant/Department Hierarchy, Evaluation Model, Policy YAML Schema, Jurisdiction, Admin API, PASS Semantics, REQUIRE_APPROVAL, PDP/ForwardingGuard Integration, Config Reload, Default Action, Audit Detail, Classification Mapping

---

## Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Narrow: Rate Limits + Spend | Phase 8 = RPM/TPM/concurrent limits + spend budgets, HTTP 429/402 | |
| Broad: Enterprise Policy Engine | Full policy framework: PDP, PEP, routing, classification, jurisdiction, provider rules | ✓ |
| Somewhere between | Rate limits + spend + basic routing | |

**User's choice:** Phase 8 is the Enterprise Policy Engine. NOT rate limiting only. Implement the policy framework that future enterprise controls use.

---

## Lifecycle Position

| Option | Description | Selected |
|--------|-------------|----------|
| Before detection/anon | Evaluate policy before any processing — fail-fast | |
| After detection, before provider | Let detection classify content, then policy decides | |
| Both gates | Pre-detection gate for BLOCK/ROUTE_LOCAL + post-detection gate for ROUTE_PROVIDER/REQUIRE_APPROVAL | ✓ |

**User's choice:** Both gates. PDP #1 (Pre-Detection) for fast metadata decisions. PDP #2 (Post-Classification) for context-aware decisions using detected entities, risk scores, classification levels.

---

## Policy Storage

| Option | Description | Selected |
|--------|-------------|----------|
| YAML files on disk, hot-reloaded | Versioned YAML in known directory | |
| Valkey/Redis | Stored in existing Valkey, CRUD via admin API | |
| Hybrid | YAML source of truth, compiled to internal model, optional Valkey cache | ✓ |

**User's choice:** Hybrid. YAML files are SOURCE OF TRUTH. Versioned in Git. Compiled to PolicyBundle at startup/reload. Valkey caching only for compiled snapshots — never authoritative.

---

## Tenant/Department Hierarchy

| Option | Description | Selected |
|--------|-------------|----------|
| Flat tenants only | Each tenant has policies, departments are subgroups | |
| Tenant → Department hierarchy | Tenant-level policies with department overrides | ✓ |

**User's choice:** Tenant → Department hierarchy. Global → Tenant → Department. More specific overrides less specific.

---

## Evaluation Model

| Option | Description | Selected |
|--------|-------------|----------|
| First-match wins | Ordered rules, first match wins | |
| Priority-based | Each rule has priority number | |
| Combine | Priority for allow/deny, first-match for routing at same priority | ✓ |

**User's choice:** Combine. Collect matching rules, sort by priority (highest first). DENY > ALLOW > ROUTE. Multiple ROUTE at same priority: first-match within group. No match: BLOCK by default. Decision precedence: BLOCK > REQUIRE_APPROVAL > ROUTE_LOCAL > ROUTE_PROVIDER > ALLOW.

---

## Policy YAML Schema

| Option | Description | Selected |
|--------|-------------|----------|
| Rule-based YAML | List of rules with match + action + priority | |
| Declarative YAML | Top-level keys for each concern | ✓ |
| Sketch together | Propose schema, user iterates | |

**User's choice:** Declarative YAML with sections: version, tenant, defaults, classification, jurisdiction, departments. Compiled to PolicyBundle with Rules, RoutingRules, JurisdictionRules, DepartmentRules.

---

## Jurisdiction

| Option | Description | Selected |
|--------|-------------|----------|
| Country-based in policy YAML | Jurisdiction rules in policy file | ✓ |
| Separate jurisdiction config | Dedicated file merged at compile time | |
| Defer | Add later when schema stable | |

**User's choice:** Country-based in policy YAML.

---

## Admin API

| Option | Description | Selected |
|--------|-------------|----------|
| Full CRUD | GET/POST/PUT/DELETE for policies | ✓ |
| Read-only + GitOps | Only GET, changes through Git | |
| CRUD now, GitOps gate later | Start with CRUD, add GitOps validation later | |

**User's choice:** Full CRUD for policies.

---

## PASS Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| PASS = skip anonymization | Don't touch request, forward as-is | ✓ |
| PASS = forward after checks | Passed policy, proceed normal pipeline | |
| Two-tier PASS | PASS_BYPASS vs PASS_THROUGH | |

**User's choice:** PASS = skip anonymization. Bypass detection entirely, forward as-is to default route.

---

## REQUIRE_APPROVAL

| Option | Description | Selected |
|--------|-------------|----------|
| Synchronous block + webhook | Block request, fire webhook, return 202 with approval_token | |
| Async with audit trail | Log decision, return 202, out-of-band review | |
| Defer | Define action type, implement later | ✓ |

**User's choice:** Defer to later phase. Define action type now, implement approval flow later.

---

## PDP/ForwardingGuard Integration

| Option | Description | Selected |
|--------|-------------|----------|
| PDP wraps ForwardingGuard | ForwardingGuard checks PDP before proceeding | |
| PDP before ForwardingGuard | PDP runs as separate step before ForwardingGuard | ✓ |
| ForwardingGuard absorbs PDP | ForwardingGuard becomes PEP | |

**User's choice:** PDP runs before ForwardingGuard as a separate step.

---

## Config Reload

| Option | Description | Selected |
|--------|-------------|----------|
| Hot-reload via file watch | Inotify/kqueue, atomic PolicyBundle swap | |
| Admin API triggers reload | POST /v1/admin/policies/reload endpoint | |
| Both | File watch + reload endpoint | ✓ |

**User's choice:** Both. File watch for dev convenience, reload endpoint for production GitOps.

---

## Default Action

| Option | Description | Selected |
|--------|-------------|----------|
| ALLOW + forward to default route | Least restrictive default | |
| BLOCK by default | Most restrictive default | ✓ |
| Configurable default | Administrator chooses | |

**User's choice:** BLOCK by default. Most restrictive.

---

## Audit Detail

| Option | Description | Selected |
|--------|-------------|----------|
| Full audit: rule_id, action, matched_conditions, policy_version | Rich but high volume | |
| Minimal: action + rule_id only | Low volume | |
| Decision summary: action, policy_version, matched_scope | Middle ground | ✓ |

**User's choice:** Decision summary: action, policy_version, matched_scope.

---

## Classification Mapping

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded in code | Entity→classification mapping in Python | |
| Configurable in YAML | Mapping section in policy YAML | |
| Hybrid: defaults in code, overridable in YAML | Best flexibility | ✓ |

**User's choice:** Hybrid. Sensible defaults in Python code, overridable in policy YAML.

---

## the agent's Discretion

- PDP #1 match condition syntax (IP, payload size, application patterns)
- PDP #2 classification level threshold definitions
- CRUD API endpoint design details (request/response schemas)
- Valkey cache key schema for compiled policy snapshots
- File watch implementation details (library choice, polling interval)
- Policy compilation/validation exact logic
- Multi-tenant policy directory structure

## Deferred Ideas

- Rate limiting policy plugin (future phase)
- Spend control policy plugin (future phase)
- REQUIRE_APPROVAL implementation (future phase)
- Data residency routing details (future phase)
