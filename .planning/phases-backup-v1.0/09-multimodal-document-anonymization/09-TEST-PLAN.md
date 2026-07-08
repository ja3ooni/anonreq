# Phase 09 Test Plan: Multimodal Document Anonymization

## Unit Tests
- Content-Type header parsing maps to correct analyzer
- JSON Analyzer walks tree to max_depth and stops
- Key-pattern detection matches standard sensitive keys
- Multipart Analyzer extracts all parts correctly
- Payload limit validation rejects oversized payloads (5MB JSON, 50MB multipart)
- Unknown Content-Type returns ROUTE_LOCAL decision
- Tool call extraction parses OpenAI, Anthropic, and MCP formats

## Integration Tests
- Full pipeline: PDP #1 → Content-Type Dispatcher → JSON Analyzer → Anonymization → PDP #2
- Full pipeline: PDP #1 → Content-Type Dispatcher → Multipart Analyzer → Anonymization → PDP #2
- Unsupported content type → ROUTE_LOCAL, no provider forwarded
- Exceeded payload limits → ROUTE_LOCAL or BLOCK
- Tool call anonymization → provider receives sanitized arguments
- Tool call restoration → response tokens replaced correctly

## Property Tests
- `restore(anonymize(x)) == x` for text, JSON, multipart payloads
- `json_structure_preserved == True` after anonymization
- `no_raw_pii_after_anonymize == True` for all content types
- `token_collisions == False` across simultaneous sessions
- Streaming round-trip: split at every possible Token index

## Security Tests
- Unknown content types never forwarded
- Oversized payloads trigger controlled failure, not silent truncation
- No PII in audit logs for JSON/multipart/tool call processing
- All metadata-only audit invariant preserved
