# Phase 15 Security Acceptance: Financial Services Compliance

## Controls
- MNPI detected via dedicated Presidio recognizer bundle
- SEC 17a-4 retention: dedicated WORM bucket, non-erasable/non-rewritable
- Model approval gating: unapproved models blocked
- Provider suspension: immediate enforcement at forwarding layer
- AML webhook: configurable threshold, metadata-only

## Required Audit Events
- `mnpi_detected` — per MNPI entity
- `mnpi_action_applied` — per policy action
- `model_approval_gated` — blocked attempt to use unapproved model
- `provider_suspended` / `provider_unsuspended`
- `dora_incident_created` — per auto-escalation
- `aml_webhook_fired` — per AML event

## Required Metrics
- `anonreq_mnpi_detections_total` by policy_action label
- `anonreq_model_approval_gates_total` by result label
- `anonreq_provider_status` by provider label (0=suspended, 1=active)

## Release Gate
- MNPI detection verified for tickers, codenames, restricted names
- Context boosting: +0.15 within 50 chars, capped at 1.0
- Unapproved model blocked confirmed
- Provider suspension blocks all traffic
- SEC 17a-4 WORM bucket: no delete, no overwrite
- All metadata-only audit invariants preserved
