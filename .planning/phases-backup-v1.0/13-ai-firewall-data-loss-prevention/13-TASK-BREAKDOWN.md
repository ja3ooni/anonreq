# Phase 13 Task Breakdown: AI Firewall & Data Loss Prevention

## Epics
1. DLP Engine core framework
2. 8 core DLP categories with detection patterns
3. Tenant custom categories via dlp.yaml
4. Data exfiltration encoding detection (Base64, hex, stego)
5. Contextual rule evaluation
6. Outbound DLP inspection
7. MITRE ATT&CK mapping config
8. DLP audit events + metrics

## Stories
- As a security officer, sensitive data in 8 categories is detected before reaching the LLM provider
- As a security officer, data exfiltration via encoding is detected in both directions
- As a platform operator, tenant-specific DLP categories are configurable via dlp.yaml
- As a compliance officer, DLP events include MITRE ATT&CK technique IDs

## Tasks
- Implement DLP Engine core (runs alongside Threat Engine)
- Implement detection patterns for 8 core categories
- Implement dlp.yaml parser for tenant custom categories
- Implement per-category action enforcement
- Implement contextual rule evaluation (category → business unit → classification)
- Implement inbound DLP inspection
- Implement outbound DLP inspection
- Implement exfiltration encoding detection (Base64, hex, stego heuristics + entropy)
- Implement MITRE mapping config loader
- Add MITRE technique IDs to DLP audit events
- Add Prometheus counters for DLP events
- Add property-based tests for DLP invariants
