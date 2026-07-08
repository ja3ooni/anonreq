# Phase 19 Test Plan: Network Discovery / CASB / Secure RAG

## Unit Tests

### Shadow AI Discovery
- DNS log parser: syslog format, JSON format, raw-text format
- AI hostname matcher: exact match, wildcard match, multi-level domain match
- AI IP range matcher: CIDR match, range match, negative match
- Usage analyzer: correct request_count, user_count, deduplication
- Proxy log parser: Squid format, Zscaler format, Palo Alto format
- Shadow AI event generation: correct event_type, source_ip, destination_host
- Dedup merge: same service from DNS + proxy merged correctly

### RAG Ingestion
- Document chunker: paragraph boundary, sentence boundary, token-count boundary
- Chunk boundary awareness: entity not split across chunks
- Chunk metadata generation: correct classification_level, entity_types_present
- Vector store connector interface: abstract method dispatch
- Embed-and-store flow: correct dispatch to configured backend
- Audit event generation: correct event_type, chunk counts, entity counts

### RAG Retrieval
- Retrieval inspection point: chunks intercepted before prompt assembly
- Retrieval-time detection: Detection Engine applied to retrieved content
- Retrieval-time anonymization: entities tokenized, mapping stored
- RAG restoration: tokens restored in LLM response
- Audit event emission: correct event_type per filtered chunk

### CASB Policy
- YAML parser: apps section parsed, validated against schema
- Action resolver: sanctioned→allow, tolerated→alert, unsanctioned→block
- User group resolver: user_id extracted from header/JWT/proxy
- Policy override: per-group overrides applied correctly
- Action enforcement: correct HTTP response per action

### AI Asset Inventory
- Inventory merge: DNS + proxy + CASB data correctly merged
- Deduplication: same hostname deduped with timeline conflict resolution
- Cost attribution: token volume converted to cost correctly
- Risk score integration: score from Risk Engine correctly attached

### AI Risk Score Engine
- Provider Trust dimension: correct score per provider tier/jurisdiction
- Data Sensitivity dimension: correct score per classification mix
- Shadow Usage dimension: correct score per policy status
- Approval Status dimension: correct score per approval state
- Model Location dimension: correct score per region
- Retention Policy dimension: correct score per retention period
- Weighted sum calculator: correct output with custom weights
- Risk band classification: 0–30 → Low, 31–60 → Medium, 61–80 → High, 81–100 → Critical

### Retrieval Policy Engine
- Chunk metadata extractor: correct classification, entity types, source app
- User context resolver: correct user_id, role, clearance, BU
- RULE-001 (classification_clearance): deny when chunk > user clearance
- RULE-002 (entity_type_restriction): deny when user roles exclude entity types
- RULE-003 (cross_app_isolation): deny when chunk app not in user apps
- RULE-004 (business_unit_isolation): deny cross-BU for ≥ Confidential
- Combined evaluation: DENY wins when multiple rules match
- ALLOW when no rule matches

## Integration Tests

### Shadow AI Discovery Pipeline
- Full pipeline: DNS log → parser → matcher → analyzer → event → inventory
- Full pipeline: proxy log → parser → matcher → analyzer → event → inventory
- DNS + proxy merge: cross-source dedup produces correct merged record
- Shadow AI detection triggers configured webhook

### RAG Round-Trip
- Document ingested → anonymized → chunked → stored with metadata
- Chunk retrieved → policy evaluated → allowed chunks inspected → LLM prompt
- LLM response → tokens restored → original values returned to client
- Session-scoped token mapping persists across ingestion-retrieval-restore cycle
- Entities detected at ingestion are not re-anonymized at retrieval (preserved token)
- New entities detected at retrieval are anonymized with new tokens

### CASB Policy Enforcement
- Sanctioned app: request allowed, no audit event
- Tolerated app: request allowed, alert audit event emitted
- Unsanctioned app: request blocked (HTTP 451), audit event emitted
- User group override: executive group bypasses block for notion_ai
- CASB audit event has correct user_id, application, tenant_id

### AI Asset Inventory
- Inventory populated from DNS + proxy + CASB sources
- Duplicate entries from multiple sources merged correctly
- Cost attribution returns correct breakdowns
- `GET /v1/admin/discovery/inventory` returns valid JSON and CSV

### Risk Score
- Risk score recalculated when traffic classification changes
- Risk score recalculated when policy status changes
- Risk band changes trigger correct inventory classification
- Custom dimension weights produce different score

### Retrieval Policy Pipeline
- Full pipeline: retrieved chunks → metadata extractor → user context → policy evaluation → filtered chunks → LLM
- Cross-BU isolation: Engineering user cannot retrieve Sales chunks classified ≥ Confidential
- Classification clearance: Internal-clearance user cannot retrieve Highly Restricted chunks
- Cross-app isolation: User with App-A cannot retrieve chunks from App-B
- Policy evaluation audit events emitted for each denied chunk

## Property Tests (Hypothesis)

- **RAG round-trip correctness**: Document ingested with PII → retrieved → anonymized → LLM response → restored → byte-for-byte match with original for all JSON structures containing detectable entities
- **Token consistency**: Entities detected at ingestion use same tokens at retrieval for same session
- **Policy monotonicity**: Adding more restrictive policies never allows more chunks through
- **Risk score bounds**: All risk scores are 0–100 regardless of input combinations
- **DNS+Proxy completeness**: Every AI service visible in DNS is also discoverable via proxy (or vice versa) under normal conditions — false negative rate < 0.1%
- **CASB YAML validity**: All valid YAML configurations produce valid policy state; all invalid configurations produce parse error
- **Retrieval policy determinism**: Same chunk + same user context + same policy → same allow/deny decision regardless of processing order

## Performance Tests

- RAG ingestion throughput: ≥ 100 chunks/second per document
- Retrieval policy evaluation: ≤ 5ms per chunk (excluding detection)
- Risk score calculation: ≤ 10ms per service recalc
- DNS log parsing: ≥ 10,000 entries/second
- AI hostname matching: ≥ 50,000 lookups/second
- Inventory merge: ≤ 100ms for 10,000 records

## Security Tests

- **Retrieval policy bypass**: Attempt to access chunks from unauthorized BU — correctly denied
- **Retrieval policy bypass**: Attempt to access chunks above clearance level — correctly denied
- **Shadow AI evasion**: Service using obscure DNS patterns — still detected by IP range matching
- **CASB override abuse**: Non-executive user cannot leverage executive override
- **No PII in RAG chunk metadata**: Metadata fields never contain raw entity values
- **No PII in CASB audit events**: Audit events contain metadata only, no raw values
- **No PII in Shadow AI events**: Events contain service name and IP, not raw data content

## Acceptance Tests

- ALL 3 sub-products functional end-to-end with no PII exposure
- ALL Req 53 acceptance criteria satisfied
- ALL Req 54 acceptance criteria satisfied
- ALL Req 55 acceptance criteria satisfied
- RAG round-trip preserves data integrity (byte-for-byte match)
- Retrieval Policy Engine prevents documented bypass scenarios
- Risk Score Engine produces deterministic, auditable scores
- Inventory merges across all 3 data sources correctly
