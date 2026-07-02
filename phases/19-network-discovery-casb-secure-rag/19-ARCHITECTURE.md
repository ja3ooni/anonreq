# Phase 19 Architecture: Network Discovery / CASB / Secure RAG

## System Overview

```
                     ┌─────────────────────────────────────────────────┐
                     │            Phase 19 — Three Sub-Products         │
                     │                                                   │
                     │  ┌─────────────────┐  ┌──────────────────────┐   │
                     │  │ Shadow AI        │  │ AI Asset Inventory    │   │
                     │  │ Discovery        │──│ (Merged View)        │   │
                     │  │ ┌──────┐┌──────┐│  │ ┌──┐┌──┐┌──┐┌──┐   │   │
                     │  │ │DNS   ││Proxy ││  │ │Pr││Mo││Us││Co│   │   │
                     │  │ │Logs  ││Traffic││  │ │ov││de││er││st│   │   │
                     │  │ └──────┘└──────┘│  │ └──┘└──┘└──┘└──┘   │   │
                     │  └─────────────────┘  └──────────────────────┘   │
                     │                                                   │
                     │  ┌──────────────────────────────────────┐         │
                     │  │ Secure RAG                           │         │
                     │  │  ┌────────────────┐ ┌──────────────┐│         │
                     │  │  │ INGESTION       │ │ RETRIEVAL    ││         │
                     │  │  │ /v1/rag/ingest  │ │ (proxy path) ││         │
                     │  │  └────────────────┘ └──────────────┘│         │
                     │  └──────────────────────────────────────┘         │
                     │                                                   │
                     │  ┌──────────────────────────────────────┐         │
                     │  │ CASB — Policy YAML Extension          │         │
                     │  │ CASB │ Risk Score │ Retrieval Policy  │         │
                     │  └──────────────────────────────────────┘         │
                     └─────────────────────────────────────────────────┘
```

## Shadow AI Discovery Flow

```
DNS Log Sources ──┐
(Infoblox,       │  ┌──────────────┐    ┌──────────────────┐
Bind, pdns)      ├──→│ DNS Log      │───→│ AI Hostname      │
                  │  │ Parser       │    │ Matcher          │
Proxy Log Sources─┘  └──────────────┘    │ · DNS signatures │
(Squid, Zscaler, │                       │ · IP ranges      │
Palo Alto)       │                       │ · TLS SNI        │
                 │                       └────────┬─────────┘
                 │                                │ match found
                 │                                ↓
                 │                       ┌──────────────────┐
                 │                       │ Usage Analyzer   │
                 │                       │ · request_count  │
                 │                       │ · user_count     │
                 │                       │ · token_volume   │
                 │                       │ · data patterns  │
                 │                       └────────┬─────────┘
                 │                                │
                 │                                ↓
                 │                       ┌──────────────────┐
                 │                       │ Shadow AI Event  │
                 │                       │ event_type:      │
                 │                       │ shadow_ai_detected│
                 │                       │ → Audit Log      │
                 │                       │ → Asset Inventory│
                 │                       │ → Alert (optional)│
                 │                       └──────────────────┘
```

## Secure RAG — Ingestion Flow

```
User Application
      │
      ▼
┌─────────────────┐
│ POST /v1/rag/    │  content_type: document_ingest
│ ingest           │
│ { document,      │
│   metadata }     │
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│ Content-Type     │  Phase 9 Dispatcher
│ Dispatcher       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Detection Engine │  Phase 2 — PII/PHI/MNPI detection
│ · Entity scan    │
│ · Classification │
│ · Chunk boundary │
│   awareness      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Anonymize        │  Tokenize detected entities
│ Detected Spans   │  Store mapping per session
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Chunk + Embed    │  Chunk with metadata:
│                  │  · classification_level
│                  │  · entity_types_present
│                  │  · source_app_id
│                  │  · original_doc_id
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Vector Store     │  Stores anonymized chunks only
│ (connector)      │  Original values never stored
└──────────────────┘

Audit Event: rag_content_anonymized
  · source_type: vector_database_type
  · chunks_anonymized_count
  · entities_detected_count
```

## Secure RAG — Retrieval Flow

```
User Query
      │
      ▼
┌──────────────────┐
│ Question → Embed │
│ → Search         │
└────────┬─────────┘
         │ Retrieved Chunks
         ▼
┌──────────────────┐
│ Content-Type     │  content_type: retrieved_context
│ Dispatcher       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Retrieval Policy │  NEW — Phase 19
│ Engine           │
│                  │
│ For each chunk:  │
│ 1. Get chunk     │
│    classification│
│ 2. Get user      │
│    clearance     │
│ 3. Evaluate      │
│    policy rules  │
│ 4. Allow / Deny  │
└────────┬─────────┘
         │ allowed chunks only
         ▼
┌──────────────────┐
│ Detection Engine │  Phase 2 — re-detect on
│ (Re-inspection)  │  retrieved content
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Anonymize        │  Tokenize any PII in
│ (if needed)      │  retrieved chunks
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Provider (LLM)   │  Anonymized chunks in prompt
└────────┬─────────┘
         │ Response
         ▼
┌──────────────────┐
│ Restoration      │  Restore tokens in LLM
│ Engine           │  response
└────────┬─────────┘
         │ Restored Response
         ▼
┌──────────────────┐
│ Client           │  Original values restored
│ Application      │  inside enterprise perimeter
└──────────────────┘

Audit Event: rag_chunk_filtered (per denied chunk)
  · chunk_id
  · policy_rule_id
  · classification_level
```

## AI Asset Inventory Pipeline

```
┌──────────────┐
│ DNS Log Data │───┐
│ · hostname   │   │
│ · source_ip  │   │
│ · timestamp  │   ├──┐
└──────────────┘   │  │
                   │  │
┌──────────────┐   │  │
│ Proxy Traffic│───┘  │
│ · endpoint   │      │
│ · user_id    │      │
│ · token_ct   │      │
│ · data_class │      │
└──────────────┘      │
                      │
┌──────────────┐      │
│ CASB Data    │──────┘
│ · app_class  │      │
│ · risk_score │      │
│ · policy     │      │
└──────────────┘      │
                      ▼
              ┌──────────────────┐
              │ Merge + Dedupe   │
              │ · Hostname key   │
              │ · FK: endpoint   │
              │ · Timeline merge │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────────┐
              │ AI Asset Inventory   │
              │ Record:              │
              │ · service_name       │
              │ · provider           │
              │ · model(s)           │
              │ · user_count         │
              │ · app_count          │
              │ · token_volume       │
              │ · estimated_cost     │
              │ · data_classification│
              │ · approval_status    │
              │ · risk_score         │
              │ · last_seen          │
              │ · owner              │
              │ · business_unit      │
              └────────┬─────────────┘
                       │
          ┌────────────┴──────────────┐
          │                            │
          ▼                            ▼
┌──────────────────┐      ┌──────────────────────┐
│ GET /v1/admin/   │      │ Cost Attribution     │
│ discovery/       │      │ · by provider         │
│ inventory        │      │ · by model            │
│ (JSON / CSV)     │      │ · by business_unit    │
└──────────────────┘      │ · by application      │
                          │ · time-windowed       │
                          └──────────────────────┘
```

## Retrieval Policy Engine Flow

```
┌──────────────────┐
│ Retrieved Chunks │  From vector store
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Chunk Metadata   │  extract:
│ Extractor        │  · classification_level
│                  │  · entity_types_present
│                  │  · source_app_id
│                  │  · allowed_roles
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ User Context     │  from request:
│                  │  · user_id / role
│                  │  · user_clearance
│                  │  · user_applications
│                  │  · business_unit
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ Policy Evaluation (per chunk)        │
│                                      │
│ RULE-001: classification_clearance   │
│   IF chunk.classification >          │
│      user.clearance → DENY           │
│                                      │
│ RULE-002: entity_type_restriction    │
│   IF user.roles EXCLUDES             │
│      chunk.entity_types → DENY       │
│                                      │
│ RULE-003: cross_app_isolation        │
│   IF chunk.source_app NOT IN         │
│      user.applications → DENY        │
│                                      │
│ RULE-004: business_unit_isolation    │
│   IF chunk.business_unit !=          │
│      user.business_unit AND          │
│      chunk.classification >          │
│      Internal → DENY                 │
│                                      │
│ DEFAULT: ALLOW                       │
└────────┬─────────────────────────────┘
         │
         ├── allowed → Detection Engine → LLM
         │
         └── denied  → Filter out + audit event
```

## CASB YAML Structure

```yaml
# Extension to Phase 8 policy YAML

apps:
  chatgpt:
    classification: sanctioned
    risk_score: 18
    allowed_groups: ["engineering", "product"]
    action: allow
    notes: "ChatGPT Enterprise — approved contract in place"
  claude:
    classification: sanctioned
    risk_score: 18
    allowed_groups: ["engineering", "research"]
    action: allow
    notes: "Anthropic Claude Enterprise — approved"
  deepseek:
    classification: blocked
    risk_score: 89
    allowed_groups: []
    action: block
    notes: "Not approved for any use — data residency concerns"
  github_copilot:
    classification: tolerated
    risk_score: 35
    allowed_groups: ["engineering"]
    action: alert
    notes: "Personal accounts — not enterprise licensed"
  notion_ai:
    classification: unsanctioned
    risk_score: 45
    allowed_groups: []
    action: block
    notes: "No enterprise agreement — block pending procurement review"

actions:
  sanctioned: allow
  tolerated: alert    # log + flag, does not block
  unsanctioned: block # HTTP 451 + audit event

# Override per user group
overrides:
  - group: "executive"
    overrides: { notion_ai: { action: allow } }
```

## AI Risk Score Calculation

| Dimension | Weight (default) | Inputs | Calculation |
|-----------|-----------------|--------|-------------|
| Provider Trust | 25% | Provider tier (Major/Regional/Unknown), jurisdiction, SLA, certification | 0–100: Major + US/EU + certified → low. Unknown + no cert → high. |
| Data Sensitivity | 20% | Classification levels observed in traffic | 0–100: Weighted average of observed classifications. Highly Restricted traffic → 100. |
| Shadow Usage | 20% | Sanctioned/tolerated/blocked status | 0–100: Sanctioned → 10, Tolerated → 50, Blocked/Unknown → 90. |
| Approval Status | 15% | Approved / Pending / Not Reviewed | 0–100: Approved → 5, Pending → 50, Not Reviewed → 80, Denied → 100. |
| Model Location | 10% | Data residency region | 0–100: In-region → 10, Same continent → 30, Different → 60, Unknown → 90. |
| Retention Policy | 10% | Data retention period | 0–100: No retention → 10, 30-day → 30, 90-day → 50, Indefinite → 90, Unknown → 100. |

**Score = Σ(dimension_score × weight) / Σ(weights)**

Risk bands:
- **0–30 Low**: Sanctioned, approved, major provider. Standard monitoring.
- **31–60 Medium**: Tolerated or unclassified. Enhanced monitoring + quarterly review.
- **61–80 High**: Unapproved or high data sensitivity. Monthly review + access restriction.
- **81–100 Critical**: Blocked or unknown. Immediate action required. Auto-block.

## Pipeline Integration

```
Inbound Request
      ↓
PDP #1
      ↓
Threat Engine (Phase 10)
      ↓
Content-Type Dispatcher (Phase 9)
      │
      ├── content_type: chat_prompt ──────→ Standard pipeline
      ├── content_type: document_ingest ──→ RAG Ingestion pipeline
      ├── content_type: retrieved_context ─→ RAG Retrieval pipeline
      └── content_type: tool_result ──────→ Standard pipeline (with Phase 19 awareness)
      ↓
Detection + Anonymization (Phase 2/13)
      ↓
Classification (Phase 12)
      ↓
PDP #2 (Phase 8 + CASB rules)
      ↓
ForwardingGuard → Provider → Restore → Client
```

## Actions (most → least restrictive)
1. **BLOCK** — reject request (HTTP 451)
2. **ALERT** — log + flag, forward with `X-AnonReq-Warning` header
3. **ALLOW** — no action (default for sanctioned)
