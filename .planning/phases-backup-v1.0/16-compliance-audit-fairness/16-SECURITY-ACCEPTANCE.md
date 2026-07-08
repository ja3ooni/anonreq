# Phase 16 Security Acceptance: Compliance, Audit & Fairness

## Controls
- Immutable data lineage (no modify/delete)
- Legal Hold blocks deletion across all storage tiers
- DSAR erasure removes token→entity mappings
- DSAR restriction blocks future processing
- Breach notifications: metadata-only payload
- Fairness: recall disparity threshold (≤ 0.05) enforced in CI/CD

## Required Audit Events
- `fairness_evaluation_completed` — per CI/CD run
- `fairness_drift_detected` — per runtime drift
- `incident_created` — per incident (with classification)
- `legal_hold_activated` / `legal_hold_released`
- `dsar_request_received` — per DSAR
- `dsar_completed` — per DSAR with result
- `breach_notification_sent` — per notification

## Required Metrics
- `anonreq_fairness_recall_disparity` — per evaluation
- `anonreq_incidents_by_severity` — per classification
- `anonreq_legal_holds_active` — count

## Release Gate
- Fairness CI/CD gate enforces disparity ≤ 0.05
- Data lineage append-only verified
- Legal Hold blocks deletion across all tiers
- DSAR erasure removes mappings
- DSAR restriction blocks requests
- Breach notification sends to all contacts with escalation
- eDiscovery export generates all 3 formats (JSONL, PDF, EDRM XML)
