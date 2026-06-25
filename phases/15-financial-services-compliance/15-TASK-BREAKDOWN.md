# Phase 15 Task Breakdown: Financial Services Compliance

## Epics
1. MNPI Presidio recognizer bundle
2. Tenant restricted-names list
3. SEC 17a-4 retention (dedicated WORM bucket)
4. Model Risk Management (SR 11-7)
5. Third-party provider inventory (DORA ICT)
6. Financial crime context boosting
7. AML webhook integration
8. DORA incident escalation
9. Compliance report generation

## Stories
- As a compliance officer, MNPI is detected via ticker symbols and deal codenames
- As a compliance officer, tenant-specific restricted names are configurable and hot-reloadable
- As an MRM officer, unapproved models are blocked from production
- As a third-party risk manager, DORA ICT concentration risk is tracked per provider
- As a financial crime investigator, AML-relevant events fire configurable webhooks

## Tasks
- Implement MNPI Presidio recognizer (ticker symbols, deal codenames)
- Implement tenant restricted-names list with hot-reload
- Configure dedicated MinIO WORM bucket for MNPI (SEC 17a-4)
- Implement model inventory with Phase 14 lifecycle integration
- Implement model approval gating (block unapproved at ForwardingGuard)
- Implement third-party provider inventory with DORA ICT risk flagging
- Implement provider suspension endpoint
- Implement context-word boosting in Presidio pipeline (+0.15 within 50 chars)
- Implement AML webhook with configurable tenant thresholds
- Implement DORA incident auto-escalation per criticality tier
- Write compliance mapping document
- Implement compliance report endpoint (GET /v1/admin/compliance/report)
- Add property tests for MNPI and financial crime invariants
