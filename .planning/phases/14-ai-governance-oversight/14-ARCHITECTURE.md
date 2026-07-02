# Phase 14 Architecture: AI Governance & Oversight

## Governance Object Model

```
Tenant
  ├── Governance Record (owners, review cycle, status)
  ├── Risk Assessment (6 dimensions, severity/likelihood, treatment)
  ├── Policies (versioned, approval history, diff history)
  ├── Providers (versioned, lifecycle stages)
  ├── Presets (versioned, lifecycle stages)
  ├── Approval Queue
  │   ├── Pending (HTTP 202)
  │   ├── Approved
  │   └── Rejected
  └── Transparency Records (per session, metadata only)
```

## Lifecycle Stages
```
DRAFT ──→ REVIEW ──→ APPROVED ──→ PRODUCTION ──→ DEPRECATED ──→ RETIRED
  ↑                      │              │
  └── (revisions) ←──────┘              │
                                         ↓
                                  (rollback to approved)
```

## Versioning Model
```
policy_v1 (initial)
policy_v2 (diff from v1, approval_record, timestamp, operator)
policy_v3 (diff from v2, approval_record, timestamp, operator)
...
```
Never overwrite. Always append. Full rollback support.

## Oversight Flow
```
High-Risk Request → PDP #2 → REQUIRES_APPROVAL
  ↓
Approval Queue (PostgreSQL)
  ↓
Human reviews → Approve/Reject
  ↓
Approved → Continue to provider
Rejected → HTTP 403 denied
  ↓
All actions → Immutable audit trail (Phase 11 hash chain)
```

## Kill-Switch
```
POST /v1/oversight/kill-switch          → global
POST /v1/oversight/kill-switch/{tenant} → per-tenant
```
State: enabled/disabled. Persisted. Flag checked at ForwardingGuard.
