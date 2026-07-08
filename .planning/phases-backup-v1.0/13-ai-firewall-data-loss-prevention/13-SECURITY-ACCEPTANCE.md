# Phase 13 Security Acceptance: AI Firewall & Data Loss Prevention

## Controls
- DLP inspection before PDP #2 ensures data protection before provider routing
- Outbound DLP catches exfiltration after provider response
- Exfiltration encoding detection prevents data leakage via encoding
- Category-wins-then-filter ensures deterministic contextual enforcement
- Quarantine never stores payload content

## Required DLP Categories (Core)
- PII, Financial, Health, Source Code, Credentials, Legal, Export Controlled, Intellectual Property

## Required Audit Events
- `dlp_violation` — per category violation
- `dlp_exfiltration_detected` — per encoding exfiltration
- `dlp_action_applied` — per enforcement action
- `dlp_outbound_suppressed` — per outbound suppression

## Required Metrics
- `anonreq_dlp_violations_total` by category, action labels
- `anonreq_dlp_exfiltration_total` by encoding_type label

## Release Gate
- All 8 core categories detected in integration tests
- Exfiltration encoding detection: Base64, hex, stego all detected
- Contextual rule tightening (never loosening) confirmed
- Zero payload content in quarantine audit events
- Tenant custom categories isolated per tenant
