# Phase 16 Architecture: Compliance, Audit & Fairness

## Retention Architecture
```
Storage        Purpose            Retention
─────────────────────────────────────────────
PostgreSQL     Operational queries  90 days
MinIO WORM     Compliance archive   7 years
Valkey         Token mappings       TTL-based
Legal Hold     Override             Infinite until release
```

## Data Subject Rights Flow
```
DSAR Request
  → Identity verification
  → Retention check
  → No hold?     → Delete mapping (Valkey), mark as deleted
  → Legal hold?  → Restrict processing (block future requests)
  → Result: subject_status { deleted, processing_restricted, legal_hold }
```

## Breach Notification Flow
```
Breach Detected
  → Load notification templates
  → Lookup per-tenant contacts (governance records)
  → Send notifications with escalation path
  → Log to regulator notification queue
  → Track delivery status
```

## Fairness Pipeline
```
CI/CD Build
  → Fetch fairness datasets from MinIO (by hash)
  → Run bias assessment
  → Recall disparity ≤ 0.05? → Pass / Fail build

Runtime
  → Monitor detection quality drift
  → Compare production metrics against fairness baseline
  → Alert on threshold breach
```
