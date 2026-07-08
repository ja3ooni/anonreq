# Phase 16 Test Plan: Compliance, Audit & Fairness

## Unit Tests
- Fairness dataset metadata: id, sha256, owner, approved_by present
- Recall disparity calculation correct
- Incident classification: correct tier assignment
- Legal Hold: blocks deletion flag set
- DSAR: erasure deletes Valkey mapping
- DSAR: restriction blocks future requests
- Breach notification templates: variables substituted correctly

## Integration Tests
- Fairness CI/CD gate: disparity > 0.05 fails build
- Data lineage: written to PostgreSQL + archived to MinIO
- Legal Hold active → retention deletion blocked
- DSAR full flow: intake → process → result
- Breach notification: template → lookup → send → queue
- eDiscovery export: generates valid JSONL + PDF + EDRM XML

## Security Tests
- Data lineage immutable (no modify/delete API)
- Legal Hold cannot be bypassed by direct storage access
- DSAR results metadata-only (no raw content)
- Breach notification payload metadata-only
