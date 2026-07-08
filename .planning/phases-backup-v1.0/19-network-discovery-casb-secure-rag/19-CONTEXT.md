# Phase 19: Network Discovery / CASB / Secure RAG - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 19 delivers three integrated sub-products that extend the Appliance from a request-level proxy into a network-level AI governance platform:

1. **Shadow AI Discovery (CASB-lite)**: Detect unauthorized AI service usage via DNS log analysis and proxy traffic inspection, without requiring active scanning or endpoint agents.
2. **Secure RAG**: Protect retrieval-augmented generation pipelines by inspecting documents at ingestion time and retrieved chunks at inference time, all routed through the existing AnonReq proxy.
3. **AI Asset Inventory**: Track all observed AI services, usage patterns, costs, and risk scores in a single unified inventory with cost attribution and detailed reporting.

All three sub-products route through the Phase 9 Content-Type Dispatcher. No separate gateways for each workflow type.

</domain>

<decisions>
## Implementation Decisions

### Shadow AI Detection
- **D-001:** Dual detection pipeline: DNS log analysis + proxy traffic inspection. DNS identifies WHAT was queried; proxy identifies WHAT data was sent.
- **D-002:** DNS Log → Shadow AI Discovery (identification); Proxy Traffic → Usage Analysis (depth). Results merged → AI Asset Inventory.
- **D-003:** No active scanning. Detection is entirely passive — based on existing network telemetry (DNS logs, proxy access logs). No port scanning, no credential testing.
- **D-004:** Shadow AI detection triggers: unrecognized AI API hostname, anomalous request patterns (high volume to new endpoints), traffic bypassing the AnonReq proxy.

### Secure RAG
- **D-005:** RAG traffic routed through existing AnonReq proxy. No LangChain/LlamaIndex middleware or custom SDK integration.
- **D-006:** Two distinct RAG inspection points:
  - **INGESTION** (`content_type: document_ingest`): Document → Chunk → Embed → Store. Dedicated `/v1/rag/ingest` endpoint with full PII/PHI/MNPI detection.
  - **RETRIEVAL** (`content_type: retrieved_context`): Question → Search → Retrieved Chunks → LLM. Standard proxy path with chunk-level anonymization.
- **D-007:** Retrieved chunks inspected at the point of insertion into the LLM prompt — the retrieval injection point — using the existing Detection Engine pipeline.
- **D-008:** RAG Restoration: Tokens in RAG-anonymized content restored in the LLM response using the same Mapping mechanism. Original values returned inside enterprise perimeter.

### CASB Policy
- **D-009:** CASB app classification defined as Phase 8 YAML extension. Policy model stays unified with existing enforcement framework.
- **D-010:** Per-app classification levels: `sanctioned`, `tolerated`, `blocked`. Per-app config: risk score (0–100), allowed user groups, enforcement action (`allow`, `alert`, `block`).
- **D-011:** CASB classification applies to SaaS AI applications (ChatGPT Plus, GitHub Copilot, Notion AI, Salesforce Einstein) — not just API endpoints.

### AI Asset Inventory
- **D-012:** Detailed inventory (not basic). Required fields: Provider, Model, User Count, Application Count, Token Volume, Estimated Cost, Data Classification, Approval Status, Risk Score, Last Seen, Owner, Business Unit.
- **D-013:** Cost attribution by: provider, model, requests, tokens, estimated spend. Spend tracked via provider-reported token costs.
- **D-014:** Inventory populated by merging: DNS discovery data + proxy usage data + CASB application classification data + manual admin entries.

### AI Risk Score
- **D-015:** NEW standalone component. Risk Score Engine calculates per-service risk on a 0–100 scale.
- **D-016:** Risk score dimensions: Provider Trust, Data Sensitivity, Shadow Usage, Approval Status, Model Location, Retention Policy.
- **D-017:** Score formula: weighted sum of dimension scores. Weights configurable per tenant.
- **D-018:** Thresholds: 0–30 Low, 31–60 Medium, 61–80 High, 81–100 Critical.

### Retrieval Policy Engine
- **D-019:** NEW component. Flow: Retrieved Chunks → Chunk Classification → Retrieval Policy → Allowed Chunks → LLM.
- **D-020:** Solves: cross-department leakage, RAG permission bypass, vector store oversharing, insider threats.
- **D-021:** Policy rules evaluated per chunk: deny if chunk classification_level exceeds user clearance, deny if chunk contains entity types user shouldn't access, deny if chunk source application differs from user's application.
- **D-022:** Chunk classification derived from entity detection during ingestion. Classification level stored alongside chunk metadata (not in vector embedding).

### Content-Type Routing
- **D-023:** All Phase 19 traffic routed through Phase 9 Content-Type Dispatcher. New content types registered: `document_ingest`, `retrieved_context`.
- **D-024:** Existing content types extended: `chat_prompt` (standard), `tool_result`, `mcp_payload` — inspected per current pipeline.

### Integration
- **D-025:** Shadow AI events emitted to existing Audit Logger with `event_type: shadow_ai_detected`.
- **D-026:** RAG events emitted to existing Audit Logger with `event_type: rag_content_anonymized`.
- **D-027:** CASB events emitted to existing Audit Logger with `event_type: unsanctioned_ai_access`.
- **D-028:** All Phase 19 Prometheus metrics prefixed `anonreq_discovery_*`, `anonreq_casb_*`, `anonreq_rag_*`, `anonreq_inventory_*`.

### Agent's Discretion
- DNS log parser format (syslog, JSON, custom)
- Proxy log parser format
- AI service hostname/IP signature database structure
- Risk score dimension weights and normalization
- CASB YAML schema details
- RAG ingestion endpoint request schema
- Chunk classification metadata schema
- Cost estimation methodology (token counting → dollar conversion)
- Inventory data model (SQLite or in-memory)
- Retrieval policy rule DSL
- User identity extraction (header-based, JWT, proxy-inserted)

</decisions>

<canonical_refs>
## Canonical References

- `req/requirements_v2.md` §Req 53 — AI Network Discovery
- `req/requirements_v2.md` §Req 54 — AI Cloud Access Security Broker (CASB)
- `req/requirements_v2.md` §Req 55 — Secure RAG Pipeline Protection
- `req/requirements_v2.md` §Req 41 — Classification Levels (tie into Retrieval Policy)
- `.planning/ROADMAP.md` §Phase 19 — Goal and success criteria
- `.planning/phases/09-content-type-routing/09-CONTEXT.md` — Content-Type Dispatcher for routing Phase 19 traffic
- `.planning/phases/08-Enterprise-Policy-Engine/08-CONTEXT.md` — PDP #2, action types, YAML extension point
- `.planning/phases/02-detection-engine/02-CONTEXT.md` — Detection Engine pipeline (PII/PHI/MNPI detection)
- `.planning/phases/12-data-classification-handling/12-CONTEXT.md` — Classification levels, entity-type-to-classification mapping
- `.planning/phases/13-ai-firewall-data-loss-prevention/13-CONTEXT.md` — DLP engine (Phase 19 builds on DLP patterns)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 9 Content-Type Dispatcher — routing for new `document_ingest`, `retrieved_context` types
- Phase 2 Detection Engine — PII/PHI/MNPI detection for RAG ingestion and retrieval inspection
- Phase 5 Audit Logger — structured event emission for shadow AI, CASB, RAG events
- Phase 8 Policy Engine — PDP #2 enforcement, YAML-based configuration (CASB app classification extension)
- Phase 12 Classification Engine — classification levels for chunk-level policy enforcement
- Phase 13 DLP Engine — detection patterns for content inspection in RAG pipeline

### Integration Points
- Content-Type Dispatcher: new types `document_ingest`, `retrieved_context`
- Audit events: `shadow_ai_detected`, `unsanctioned_ai_access`, `rag_content_anonymized`, `rag_chunk_filtered`
- Policy YAML: CASB app classification section
- Metrics: `anonreq_discovery_*`, `anonreq_casb_*`, `anonreq_rag_*`, `anonreq_inventory_*`
- Cache Manager: ephemeral storage for RAG session token mappings

</code_context>

<specifics>
## Specific Ideas

- Dual DNS + Proxy detection is defense in depth: DNS catches traffic that never reaches the proxy, proxy catches data content DNS can't see.
- RAG ingestion-time detection is critical for vector DB integrity — once sensitive data is embedded, it's nearly impossible to remove without re-indexing.
- Retrieval Policy Engine prevents an insider with access to Sales data from querying Engineering's vector store — solves the "vector DB = global shared bucket" problem.
- Risk Score consolidates 6 dimensions into a single actionable number for security teams. Analogous to Tenable/CVSS for AI services.
- Cost attribution at the proxy layer eliminates the need for separate cost tracking tools — every token is counted at the gateway.

</specifics>

<deferred>
## Deferred Ideas

- Active service scanning (requires explicit opt-in — deferred to Phase 22+)
- RAG-specific vector DB connectors (Pinecone, Weaviate, Chroma, pgvector connectors — Phase 20)
- File-system document repository scanning (PDF, DOCX, TXT — Phase 20)
- Automated CASB remediation workflows (auto-block unsanctioned apps — Phase 21)
- Advanced RAG permission model (attribute-based access control for vector stores — Phase 21)
- ML-based AI service fingerprinting (beyond hostname/IP matching — Phase 22)

</deferred>

---

*Phase: 19-network-discovery-casb-secure-rag*
*Context gathered: 2026-06-26*
