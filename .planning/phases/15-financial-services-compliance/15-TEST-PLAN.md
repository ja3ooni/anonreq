# Phase 15 Test Plan: Financial Services Compliance

## Unit Tests
- MNPI recognizer detects ticker symbols, deal codenames, restricted names
- Context boosting: confidence +0.15 within 50 chars
- Context boosting: capped at 1.0
- Model lifecycle stages enforce approval gate
- Third-party provider flagging: concentration risk detected
- DORA incident creation per criticality tier

## Integration Tests
- MNPI detected → 4 policy actions (anonymize, flag, block, quarantine)
- Unapproved model → blocked at ForwardingGuard
- Provider suspension → all routes to that provider blocked
- AML webhook fires at configured threshold
- Compliance report generated per framework
- MNPI audit events → MinIO WORM bucket

## Security Tests
- MNPI data never in raw audit logs
- Model approval gating cannot be bypassed
- Provider suspension cannot be bypassed
- SEC 17a-4 WORM policy enforced (no delete, no overwrite)
- AML webhook payload metadata-only
