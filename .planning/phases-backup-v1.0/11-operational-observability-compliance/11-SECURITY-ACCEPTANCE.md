# Phase 11 Security Acceptance: Operational Observability & Compliance

## Controls
- SHA-384 hash chain prevents retroactive audit event tampering
- Daily chain anchoring prevents full-chain rewrite
- Append-only audit trail with no modify/delete API
- Tenant-configurable retention (default 7 years)
- MinIO WORM bucket for immutable archive
- cosign attestation for SBOM integrity

## Required Audit Events
- `audit_event_stored` — per audit event
- `chain_anchor_created` — per daily anchor
- `slo_breach_detected` — per SLO breach
- `compliance_export_completed` — per monthly export

## Required Metrics
- `anonreq_slo_success_total` — by tenant
- `anonreq_slo_breaches_total` — by SLO type
- `anonreq_audit_events_total` — by event_type

## Release Gate
- Hash chain verification tests pass
- Daily chain anchoring verified
- SLO computation matches manual calculation
- Audit events never contain raw payloads
- SBOM generated, published, attested per release
- MinIO WORM bucket configured with retention policy
