# Phase 13 Architecture: AI Firewall & Data Loss Prevention

## DLP Engine Position

```
Inbound Request
      ↓
PDP #1
      ↓
Threat Engine (Phase 10) ← injection, jailbreak, role manipulation
      ↓
Content-Type Dispatcher (Phase 9)
      ↓
Detection + Anonymization (Phase 2/9)
      ↓
Classification (Phase 12)
      ↓
DLP Engine (Phase 13) ← exfiltration, leakage, encoding detection
  Core categories:
  ├── PII
  ├── Financial
  ├── Health
  ├── Source Code
  ├── Credentials
  ├── Legal
  ├── Export Controlled
  └── Intellectual Property
  + tenant custom categories (dlp.yaml)
      ↓
PDP #2 (Phase 8)
  Enforces: allow → anonymize → redact → quarantine → block
      ↓
ForwardingGuard → Provider → Restore → Client

Outbound Response
      ↓
Outbound DLP ← exfiltration encoding detection (Base64, hex, stego)
      ↓
HTTP 451 on violation
```

## Execution Order
1. Threat Detection (Phase 10) — injection, jailbreak, manipulation
2. Classification (Phase 12) — entity-based sensitivity level
3. DLP (Phase 13) — data category detection + contextual rules
4. PDP #2 — enforce most restrictive action across all detections

## Actions (most → least restrictive)
1. BLOCK — reject request (HTTP 451)
2. QUARANTINE — block + metadata audit (no payload stored)
3. REDACT — remove sensitive spans (not restorable)
4. ANONYMIZE — tokenize (restorable)
5. ALLOW — no action

## Contextual Rule Logic
```
category_action = dlp_config[category].action  # Category wins
if business_unit in dlp_config[category].unit_overrides:
    category_action = tighten(category_action, unit_override)
if classification_level > threshold:
    category_action = tighten(category_action, level_action)
# Tighten only, never loosen
```
