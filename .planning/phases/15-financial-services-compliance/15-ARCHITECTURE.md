# Phase 15 Architecture: Financial Services Compliance

## MNPI Flow
```
Detection Pipeline
  ├── Core Presidio Analyzers (Phase 2)
  ├── MNPI Recognizer Bundle (Phase 15)
  │   ├── Ticker symbols
  │   ├── Deal codenames
  │   └── Tenant restricted-names list
  └── Financial Crime Context Boosting
      └── High-risk word within 50 chars → confidence +0.15
```

## DORA Incident Escalation
```
Critical Service Request
  → SLO breach check
  → Auto-create incident record
  → Notify (webhook/email)

Important Service Request
  → SLO breach check
  → Log incident
  → No auto-notify

Standard Service Request
  → No escalation
  → Standard processing
```

## Retention Architecture
```
MNPI Audit Events
  ├── PostgreSQL (queryable, 90d hot)
  └── MinIO WORM Bucket (SEC 17a-4, 7y retention)
      Bucket: anonreq-mnpi-audit
      Policy: non-erasable, non-rewritable
```
