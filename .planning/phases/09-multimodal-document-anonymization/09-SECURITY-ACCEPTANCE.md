# Phase 09 Security Acceptance: Multimodal Document Anonymization

## Controls
- Unknown content type → ROUTE_LOCAL, never FORWARD
- Payload limits enforced before processing (5MB JSON, 50MB multipart, depth 50)
- JSON structural validity preserved after anonymization
- No raw PII in audit logs for any content type
- Tool call arguments fully sanitized before provider forwarding
- All metadata-only audit invariant preserved across text/JSON/multipart

## Required Property Invariants
- `restore(anonymize(x)) == x` for all content types
- `json_structure_preserved == True`
- `no_raw_pii_after_anonymize == True`
- `token_collisions == False`

## Required Audit Events
- `content_type_unsupported` — when Content-Type has no analyzer
- `payload_limit_exceeded` — when limits are exceeded
- `tool_call_anonymized` — per tool call in request
- `tool_result_anonymized` — per tool result in response

## Required Metrics
- `anonreq_multimodal_payloads_total` by content_type label
- `anonreq_multimodal_rejections_total` by reason label

## Release Gate
- All property tests pass for text, JSON, and multipart payloads
- Unknown content type tests confirm zero provider forwards
- Oversized payload tests confirm controlled failure
- All Phase 2 security acceptance gates remain green
