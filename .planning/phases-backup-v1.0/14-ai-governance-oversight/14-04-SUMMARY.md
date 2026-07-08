# Plan 14-04: Notifications + Full Test Suite — Complete

## Webhook Notifications
- **NotificationEventType** enum: `review_overdue`, `risk_threshold_breached`, `kill_switch_activated`, `governance_record_updated`, `risk_assessment_created`
- **NotificationChannel** enum: `webhook`, `email`
- **NotificationService**: `create_config()`, `list_configs()`, `get_config()`, `update_config()`, `delete_config()`, `notify()`
- Webhook dispatch via `httpx.AsyncClient` with 10s timeout, fire-and-forget
- Event-type filtering and enabled/disabled toggle
- Cache-backed via Valkey HASH

## Email Template System
- Three built-in templates: `review_overdue`, `risk_threshold_breached`, `kill_switch_activated`
- Template rendering via `str.format()` with context variables
- `render_email_template()` method for standalone use

## API Endpoints
- Notification config CRUD exposed via service layer (admin routes)

## Property-Based Tests
- 12 Hypothesis property tests covering:
  - Approval request invariants (risk score range 0-1, valid statuses, non-empty IDs)
  - Change entry invariants (version ≥ 1, non-empty changed_by)
  - Governance officer field validation
  - Lifecycle stage enum coverage
  - Notification event type/channel enum validation
  - Transparency record invariants (positive entity counts, non-empty session IDs)
  - Oversight batch creation count invariant
  - Kill-switch state invariant (inactive → active after activation)

## Full Governance Test Suite: 111 tests passing
- `test_governance_records.py` — 18 tests
- `test_governance_risk.py` — 19 tests
- `test_oversight.py` — 22 tests
- `test_lifecycle.py` — 17 tests
- `test_transparency.py` — 12 tests
- `test_governance_notifications.py` — 11 tests
- `test_governance_property.py` — 12 tests

## Files
- `src/anonreq/services/notifications.py` — NotificationService, email templates, webhook dispatch
- `tests/test_governance_notifications.py` — 11 tests
- `tests/test_governance_property.py` — 12 property tests
