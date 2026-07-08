# Phase 14 Security Acceptance: AI Governance & Oversight

## Controls
- Governance objects versioned forever (append-only, never overwrite)
- Kill-switch: both global and per-tenant, auth-protected
- Approval queue: auth-protected, actions in immutable audit trail
- Transparency records: metadata only, no raw content
- Lifecycle stages: production gate requires testing + risk assessment + approval

## Required Audit Events
- `governance_record_updated` — per record change
- `risk_assessment_updated` — per assessment change
- `approval_request_created` — per new approval
- `approval_granted` / `approval_denied` — per decision
- `kill_switch_activated` / `kill_switch_deactivated` — per toggle
- `lifecycle_transition` — per stage change
- `version_rollback` — per rollback
- `conformity_package_generated` — per package

## Required Metrics
- `anonreq_governance_overdue_reviews` — by tenant
- `anonreq_oversight_approvals_pending` — by tenant
- `anonreq_kill_switch_state` — 0/1 per scope

## Release Gate
- Versioning: append-only enforced (never overwrite)
- Kill-switch blocks all/tenant traffic when enabled
- Approval queue: full lifecycle tested (create → approve/reject → forward/deny)
- Transparency headers present on all responses
- Conformity package generates valid ZIP with all required docs
- No raw content in transparency or governance records
