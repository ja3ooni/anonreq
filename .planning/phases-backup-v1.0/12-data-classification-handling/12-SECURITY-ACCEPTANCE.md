# Phase 12 Security Acceptance: Data Classification & Handling Policies

## Controls
- Deterministic classification: no AI, no scoring, no confidence blending
- Client increase-only: never decrease classification
- Undetected defaults to Internal (not Public)
- Per-level handling defaults block Highly Restricted
- Classification stamped on RequestContext for all downstream consumers
- Classification in every audit log entry

## Required Audit Events
- `classification_computed` — per request, includes highest level + entity labels
- `classification_client_override` — when client assertion changes result
- `classification_blocked` — when Highly Restricted blocks request

## Required Metrics
- `anonreq_classifications_total` by level label

## Release Gate
- Deterministic max algorithm verified: same input → same output, always
- Client increase-only enforced: all attempts to decrease rejected
- Default entity mapping covers all entity types from Phase 2
- Classification in every audit entry confirmed
- Blocked requests return HTTP 451 with structured body
