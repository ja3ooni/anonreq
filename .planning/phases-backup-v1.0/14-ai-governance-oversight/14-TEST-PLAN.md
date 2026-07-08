# Phase 14 Test Plan: AI Governance & Oversight

## Unit Tests
- Governance record CRUD with owner validation
- Review cycle: overdue detection triggers correctly
- Risk assessment: 6 dimensions scored correctly
- Versioning: append-only enforced (no overwrite)
- Versioning: diff between versions correct
- Lifecycle stage transitions: valid transitions enforced
- Kill-switch: global + per-tenant toggle correct

## Integration Tests
- Approval queue: request → HTTP 202 → approve → forward to provider
- Approval queue: request → HTTP 202 → reject → HTTP 403
- Kill-switch global: enabled → all provider traffic blocked
- Kill-switch per-tenant: enabled → only that tenant blocked
- Transparency headers present on all responses
- Transparency status endpoint returns period stats
- Conformity package generated on-demand (valid ZIP)
- Version rollback restores previous state

## Security Tests
- Kill-switch auth-protected (admin role only)
- Approval queue auth-protected
- Transparency records metadata-only (no raw content)
- Version history cannot be modified or deleted
- Lifecycle stage transitions require auth + approval
