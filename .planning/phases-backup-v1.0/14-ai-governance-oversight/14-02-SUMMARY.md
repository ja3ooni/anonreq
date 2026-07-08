# Plan 14-02: Human Oversight — Complete

## Approval Queue
- **ApprovalRequest** model with `id`, `tenant_id`, `request_type`, `description`, `status` (pending/approved/rejected), `risk_score`, operator tracking
- **Endpoints**: `GET /v1/oversight/approvals`, `GET /v1/oversight/approvals/{id}`, `POST /v1/oversight/approvals/{id}/approve`, `POST /v1/oversight/approvals/{id}/reject`
- HTTP 202 pattern supported via risk-scores requiring pending approval before forwarding
- Cache-backed storage via Valkey HASH with 24h TTL
- Tenant-filtered listing, duplicate-decision prevention

## Kill-Switch
- **`POST /v1/oversight/kill-switch`** — activate/deactivate with `{"action": "activate|deactivate", "operator_id": "...", "reason": "..."}`
- **`GET /v1/oversight/kill-switch`** — returns `{"active": bool, "operator_id": ..., "activated_at": ...}`
- Immediately blocks all provider forwarding when active
- Cache-backed, no persistence (ephemeral by design)

## Versioning
- **ChangeEntry** model in `governance.py` with `version`, `changed_at`, `changed_by`, `description`, `changes` dict
- `GovernanceRecord.version` field (default 1) with `change_history` list
- `GovernanceRecordModel.version` + `change_history` columns
- Serializers updated in both `records.py` and `reviews.py`

## Files
- `src/anonreq/services/oversight.py` — OversightService
- `src/anonreq/routes/oversight.py` — FastAPI routes
- `src/anonreq/models/governance.py` — ChangeEntry, version field
- `tests/test_oversight.py` — 22 tests
