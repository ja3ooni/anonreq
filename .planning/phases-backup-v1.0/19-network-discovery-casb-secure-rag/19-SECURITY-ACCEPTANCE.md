# Phase 19 Security Acceptance: Network Discovery / CASB / Secure RAG

## Controls

- **Shadow AI Detection**: DNS + proxy passive analysis identifies unauthorized AI usage without active scanning
- **RAG Ingestion Inspection**: Full PII/PHI/MNPI detection before content enters vector store — prevents sensitive data embedding
- **RAG Retrieval Inspection**: Retrieved chunks re-inspected at LLM prompt injection point — catches data missed at ingestion
- **Retrieval Policy Engine**: Per-chunk access control prevents cross-department leakage, permission bypass, and vector store oversharing
- **CASB Policy Enforcement**: AI SaaS app usage classified and governed — unsanctioned apps blocked (HTTP 451)
- **AI Risk Score**: 6-dimension numeric risk score provides objective, auditable risk assessment per service
- **No Active Scanning**: Discovery is entirely passive — no network disruption risk, no legal exposure
- **No PII in Audit Events**: Shadow AI, CASB, RAG events contain metadata only — no raw entity values

## Required Audit Events

| Event Type | Source | Fields (no raw values) |
|-----------|--------|----------------------|
| `shadow_ai_detected` | Discovery | source_ip, destination_host, estimated_service, timestamp |
| `shadow_ai_merged` | Inventory | service_name, source (dns|proxy|both), first_seen, last_seen |
| `unsanctioned_ai_access` | CASB | user_id (if available), application, tenant_id, action_taken |
| `casb_action_applied` | CASB | application, classification, action, user_group |
| `rag_content_anonymized` | RAG Ingestion | source_type, chunks_anonymized_count, entities_detected_count |
| `rag_chunk_filtered` | RAG Retrieval | chunk_id, policy_rule_id, classification_level, reason_code |
| `rag_restoration_applied` | RAG Retrieval | session_id, tokens_restored_count |
| `risk_score_updated` | Risk Engine | service_name, previous_score, new_score, dimension_breakdown |

## Required Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `anonreq_discovery_events_total` | Counter | source (dns|proxy), service_type |
| `anonreq_casb_events_total` | Counter | application, classification, action |
| `anonreq_rag_chunks_ingested_total` | Counter | source_type |
| `anonreq_rag_chunks_retrieved_total` | Counter | source_type |
| `anonreq_rag_chunks_filtered_total` | Counter | rule_id, reason_code |
| `anonreq_rag_entities_detected_total` | Counter | phase (ingestion|retrieval) |
| `anonreq_inventory_services_total` | Gauge | risk_band, provider |
| `anonreq_inventory_risk_distribution` | Gauge | risk_band (low|medium|high|critical) |
| `anonreq_rag_policy_evaluations_total` | Counter | rule_id, result (allow|deny) |
| `anonreq_risk_score_calculation_duration_seconds` | Histogram | — |

## Retrieval Policy Rules (Default Configuration)

| Rule ID | Name | Condition | Action | Enabled |
|---------|------|-----------|--------|---------|
| RULE-001 | classification_clearance | chunk.classification_level > user.clearance_level | DENY | Yes |
| RULE-002 | entity_type_restriction | user.roles excludes chunk.entity_types_present | DENY | Yes |
| RULE-003 | cross_app_isolation | chunk.source_app_id NOT IN user.app_ids | DENY | Yes |
| RULE-004 | business_unit_isolation | chunk.business_unit != user.business_unit AND chunk.classification >= Confidential | DENY | Yes |

## Risk Score Dimensions (Default Weights)

| Dimension | Weight | Min Score | Max Score | Description |
|-----------|--------|-----------|-----------|-------------|
| Provider Trust | 25% | 0 | 100 | Provider tier, jurisdiction, SLA, certifications |
| Data Sensitivity | 20% | 0 | 100 | Classification levels observed in traffic |
| Shadow Usage | 20% | 10 | 90 | Sanctioned/tolerated/blocked status |
| Approval Status | 15% | 5 | 100 | Approved/pending/not_reviewed/denied |
| Model Location | 10% | 10 | 90 | Data residency region |
| Retention Policy | 10% | 10 | 100 | Data retention period |

## Release Gate

- Shadow AI detection functional end-to-end: DNS log + proxy log → match → event → inventory merge
- RAG round-trip: ingest → anonymize → store → retrieve → policy → detect → restore → byte-for-byte match
- All 4 Retrieval Policy rules enforced correctly in integration tests
- CASB app classification: sanctioned (allow), tolerated (alert), unsanctioned (block) all functional
- AI Asset Inventory: populated from all 3 data sources, exportable as JSON and CSV
- Risk Score Engine: scores deterministic, bounds 0–100, bands correct
- Zero raw PII in any Phase 19 audit event
- Zero false positives from Retrieval Policy in default-allow configuration
- Cost attribution: token volumes tracked correctly per provider/model
- Prometheus metrics emitted for all required metric types
- All Req 53, 54, 55 acceptance criteria satisfied
