# Phase 19 Task Breakdown: Network Discovery / CASB / Secure RAG

## Epic: Phase 19 Network Discovery / CASB / Secure RAG

### Stories
1. As a security administrator, I want unauthorized AI service usage detected via DNS and proxy logs, so that shadow AI is identified and governed.
2. As a data owner, I want RAG pipeline documents inspected and anonymized at ingestion time, so that sensitive data is never embedded in vector stores.
3. As a data owner, I want retrieved RAG chunks inspected and filtered before LLM exposure, so that retrieval permission bypass is prevented.
4. As a cloud security architect, I want CASB-style governance controls for AI SaaS applications, so that corporate data policies extend to all AI tooling.
5. As a CISO, I want a unified AI asset inventory with risk scoring and cost attribution, so that I have complete visibility into AI usage across the enterprise.

## Shadow AI Discovery (Req 53)

### Tasks
- **T-001:** Implement DNS log parser — support syslog, JSON, and raw-text formats; extract hostname, source_ip, timestamp.
- **T-002:** Build AI hostname/IP signature database — known AI provider endpoints (OpenAI, Anthropic, Gemini, Bedrock, Azure OpenAI, Mistral, Cohere, local LLM CIDR ranges).
- **T-003:** Implement AI hostname matcher — match parsed DNS queries against signature database with wildcard/multi-level domain matching.
- **T-004:** Implement proxy traffic parser — parse proxy access logs (Squid, Zscaler, Palo Alto format) for AI API endpoints.
- **T-005:** Implement usage analyzer — compute request_count, user_count, token_volume, data classification patterns per discovered service.
- **T-006:** Implement shadow AI event generation — emit `event_type: shadow_ai_detected` with source_ip, destination_host, estimated_service.
- **T-007:** Implement alert integration — configurable webhook notification on shadow AI detection.
- **T-008:** Implement discovery deduplication and timeline merge across DNS + proxy sources.

## Secure RAG — Ingestion (Req 55)

### Tasks
- **T-009:** Register `content_type: document_ingest` in Phase 9 Content-Type Dispatcher.
- **T-010:** Implement `POST /v1/rag/ingest` endpoint — accepts document body + metadata, returns anonymized chunks + chunk metadata.
- **T-011:** Implement document chunking — split document at configurable boundaries (paragraph, sentence, token count) with awareness of entity boundaries.
- **T-012:** Implement ingestion-time detection — run Detection Engine (Phase 2) on each chunk before embedding.
- **T-013:** Implement ingestion-time anonymization — tokenize detected entities in chunk content before storage.
- **T-014:** Implement chunk metadata schema — store classification_level, entity_types_present, source_app_id, original_doc_id alongside each chunk.
- **T-015:** Implement vector store connector interface — abstract base with pluggable backends (Pinecone, Weaviate, Chroma, pgvector).
- **T-016:** Implement standard embed-and-store flow — chunk → embed → store with metadata.
- **T-017:** Implement RAG ingestion audit events — emit `event_type: rag_content_anonymized` with source_type, chunks_anonymized_count, entities_detected_count.
- **T-018:** Implement ingestion-time Prometheus metrics — `anonreq_rag_chunks_ingested_total`, `anonreq_rag_entities_detected_total`.

## Secure RAG — Retrieval (Req 55)

### Tasks
- **T-019:** Register `content_type: retrieved_context` in Phase 9 Content-Type Dispatcher.
- **T-020:** Implement retrieval inspection point — intercept retrieved chunks before LLM prompt assembly.
- **T-021:** Implement Retrieval Policy Engine (see separate tasks below).
- **T-022:** Implement retrieval-time re-detection — run Detection Engine on allowed chunks before prompt.
- **T-023:** Implement retrieval-time anonymization — tokenize any newly detected entities in retrieved content.
- **T-024:** Implement RAG restoration — restore tokens in LLM response using session-scoped mapping.
- **T-025:** Implement RAG retrieval audit events — emit `event_type: rag_chunk_filtered` per denied chunk with chunk_id, policy_rule_id, classification_level.
- **T-026:** Implement retrieval-time Prometheus metrics — `anonreq_rag_chunks_retrieved_total`, `anonreq_rag_chunks_filtered_total`.

## CASB Policy (Req 54)

### Tasks
- **T-027:** Extend Phase 8 Policy YAML schema — add `apps:` section with classification, risk_score, allowed_groups, action, notes.
- **T-028:** Implement CASB app classification loader — parse `apps:` section from policy YAML, validate against schema.
- **T-029:** Implement CASB action resolver — map sanctioned→allow, tolerated→alert, unsanctioned→block.
- **T-030:** Implement CASB enforcement — intercept requests matching known AI SaaS apps, apply per-app policy action.
- **T-031:** Implement CASB user group resolution — extract user_id from request (header/JWT/proxy-inserted), resolve group membership.
- **T-032:** Implement CASB policy override support — per-group overrides in YAML.
- **T-033:** Implement CASB audit events — emit `event_type: unsanctioned_ai_access` with user_id, application, tenant_id.
- **T-034:** Implement CASB Prometheus metrics — `anonreq_casb_events_total` by application, classification, action labels.
- **T-035:** Implement `GET /v1/admin/casb/activity` endpoint — queryable by user_id, application, time range.

## AI Asset Inventory (Req 53)

### Tasks
- **T-036:** Design inventory data model — service_name, provider, model, user_count, app_count, token_volume, estimated_cost, data_classification, approval_status, risk_score, last_seen, owner, business_unit.
- **T-037:** Implement inventory merge pipeline — merge DNS discovery data + proxy usage data + CASB classification data.
- **T-038:** Implement inventory deduplication — dedupe by hostname endpoint key with timeline conflict resolution.
- **T-039:** Implement manual admin entry support — add/update inventory records via admin API.
- **T-040:** Implement `GET /v1/admin/discovery/inventory` endpoint — return inventory as JSON or CSV.
- **T-041:** Implement cost attribution — track token volume per provider/model, estimate cost using provider pricing tables.
- **T-042:** Implement cost attribution endpoint — `GET /v1/admin/discovery/costs` with provider, model, business_unit, time-windowed breakdown.
- **T-043:** Implement inventory update — periodic refresh from DNS/proxy sources.
- **T-044:** Implement inventory Prometheus metrics — `anonreq_inventory_services_total`, `anonreq_inventory_risk_distribution`.

## AI Risk Score Engine

### Tasks
- **T-045:** Implement Risk Score Engine — standalone component calculating per-service risk score.
- **T-046:** Implement Provider Trust dimension — score service by provider tier, jurisdiction, SLA, certifications.
- **T-047:** Implement Data Sensitivity dimension — score by observed classification levels in traffic.
- **T-048:** Implement Shadow Usage dimension — score by sanctioned/tolerated/blocked status.
- **T-049:** Implement Approval Status dimension — score by approved/pending/not_reviewed/denied.
- **T-050:** Implement Model Location dimension — score by data residency region.
- **T-051:** Implement Retention Policy dimension — score by configured data retention period.
- **T-052:** Implement weighted sum calculator — configurable per-tenant dimension weights.
- **T-053:** Implement risk band classification — 0–30 Low, 31–60 Medium, 61–80 High, 81–100 Critical.
- **T-054:** Implement risk score update — recalculate on any input change (new traffic, policy change, provider update).

## Retrieval Policy Engine

### Tasks
- **T-055:** Implement Retrieval Policy Engine — standalone component between vector store and LLM prompt assembly.
- **T-056:** Implement chunk metadata extractor — parse classification_level, entity_types_present, source_app_id, allowed_roles from stored chunk metadata.
- **T-057:** Implement user context resolver — extract user_id, role, clearance level, business_unit from request context.
- **T-058:** Implement RULE-001 (classification_clearance): deny if chunk classification > user clearance.
- **T-059:** Implement RULE-002 (entity_type_restriction): deny if user roles exclude chunk entity types.
- **T-060:** Implement RULE-003 (cross_app_isolation): deny if chunk source_app not in user's applications.
- **T-061:** Implement RULE-004 (business_unit_isolation): deny cross-BU access for ≥ Confidential chunks.
- **T-062:** Implement policy rule evaluation engine — evaluate all rules per chunk, DENY wins.
- **T-063:** Implement chunk filtering — pass only allowed chunks to LLM prompt assembly; log filtered chunks.
- **T-064:** Implement Retrieval Policy configuration — YAML-based rule definition with enable/disable per rule.
- **T-065:** Implement retrieval policy audit events — `event_type: rag_chunk_filtered` per denial.
- **T-066:** Implement retrieval policy Prometheus metrics — `anonreq_rag_policy_evaluations_total` by rule_id, result labels.

## Testing

### Tasks
- **T-067:** Write unit tests for Shadow AI Discovery pipeline (parser, matcher, analyzer).
- **T-068:** Write unit tests for RAG ingestion pipeline (chunking, detection, metadata).
- **T-069:** Write unit tests for Retrieval Policy Engine (all 4 rules, edge cases).
- **T-070:** Write unit tests for Risk Score Engine (weighted sum, dimension scoring, band classification).
- **T-071:** Write unit tests for CASB policy loader and action resolver.
- **T-072:** Write integration tests for RAG round-trip (ingest → detect → store → retrieve → detect → restore).
- **T-073:** Write integration tests for DNS → Inventory pipeline.
- **T-074:** Write property-based tests for RAG round-trip invariants.
- **T-075:** Write security tests for retrieval policy bypass attempts.
- **T-076:** Write performance tests for RAG ingestion throughput.
