# Phase 12 Test Plan: Data Classification & Handling Policies

## Unit Tests
- ClassificationEngine returns correct highest level for entity combinations
- Default entity mapping produces correct classification for all known entity types
- Undetected input defaults to Internal
- Client-asserted classification increase works (Detected: Internal, Client: Restricted → Restricted)
- Client-asserted classification decrease rejected (Detected: Restricted, Client: Public → Restricted)
- Max algorithm deterministic: same input → same output
- Response classification header only emitted when debug header present

## Integration Tests
- Full pipeline: detection → classification → RequestContext stamp → PDP #2
- Client-asserted classification logged as override
- Per-level handling: Confidential → ANONYMIZE, Highly Restricted → BLOCK
- Blocked requests return HTTP 451 with classification in body
- Response header present/absent based on request header

## Property Tests
- Classification is monotonic: more sensitive entities never lower classification
- Classification is deterministic: same entity set → same classification
- Client increase monotonic: client can only increase, never decrease
- All audit entries contain classification_level field

## Security Tests
- Client cannot bypass detection by asserting lower classification
- Classification override attempts logged
- No PII in classification-related audit events
