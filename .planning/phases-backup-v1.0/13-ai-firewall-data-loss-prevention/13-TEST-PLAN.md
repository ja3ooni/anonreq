# Phase 13 Test Plan: AI Firewall & Data Loss Prevention

## Unit Tests
- DLP Engine detects all 8 core categories
- Tenant custom categories loaded from dlp.yaml
- Exfiltration encoding detection: Base64, hex, stego patterns
- Shannon entropy calculation: correctly identifies high-entropy content
- Contextual rules: category wins, then tighten by unit + classification
- Action precedence: BLOCK > QUARANTINE > REDACT > ANONYMIZE > ALLOW

## Integration Tests
- Full pipeline: Threat → Classification → DLP → PDP #2
- Inbound DLP blocks sensitive data (HTTP 451)
- Outbound DLP blocks exfiltrated data (HTTP 451)
- QUARANTINE: blocks + logs metadata, no payload stored
- REDACT: sensitive spans removed from content (not restorable)
- ANONYMIZE: sensitive spans tokenized (restorable)
- Tenant custom categories active only for their tenant

## Property Tests
- DLP detection monotonic: more sensitive content never reduces action severity
- Exfiltration encoding detection: encoded sensitive content always detected
- Contextual rule: tightening only, never loosening
- Tenant isolation: tenant A custom categories never affect tenant B

## Security Tests
- Exfiltration via Base64: correctly detected
- Exfiltration via hex encoding: correctly detected
- Exfiltration via steganography-like patterns: correctly detected
- No payload in quarantine audit events
