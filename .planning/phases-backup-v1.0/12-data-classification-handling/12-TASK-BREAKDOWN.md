# Phase 12 Task Breakdown: Data Classification & Handling Policies

## Epics
1. Classification engine (deterministic highest-sensitivity)
2. Entity-type-to-classification mapping (default + YAML override)
3. Client-asserted classification header handling
4. Classification → RequestContext stamping
5. Per-level handling policy integration with PDP #2
6. Debug header for response classification header
7. Classification in audit logs

## Stories
- As a platform operator, every request is auto-classified by sensitivity based on detected entities
- As a security officer, client-asserted classification can only increase sensitivity, never decrease
- As a platform operator, per-level handling policies follow defaults but are overridable in policy YAML
- As an auditor, classification level appears in every audit log entry

## Tasks
- Implement ClassificationEngine with deterministic max algorithm
- Define default entity-to-classification mapping table
- Implement YAML override for entity mapping (Phase 8 policy YAML extension)
- Implement X-AnonReq-Classification header parsing
- Implement increase-only validation (client cannot decrease)
- Stamp classification on RequestContext after detection
- Integrate with PDP #2 for per-level policy evaluation
- Implement X-AnonReq-Debug / X-AnonReq-Return-Classification response header
- Add classification to audit log entries via RequestContext
- Add property-based tests for classification invariants
