# Phase 19: Network Discovery / CASB / Secure RAG - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-26
**Phase:** 19-network-discovery-casb-secure-rag
**Areas discussed:** Shadow AI Detection Strategy, RAG Architecture, CASB Policy Model, AI Asset Inventory Scope, AI Risk Score, Retrieval Policy Engine, Content-Type Routing, Active Scanning, Cost Attribution, User Identification

---

## Shadow AI Detection Strategy
| Option | Selected |
|--------|----------|
| Proxy-only | |
| DNS-only | |
| Proxy + DNS | ✓ |

**User's choice:** Proxy + DNS. DNS tells you WHAT was queried; Proxy tells you WHAT data was sent. Best: DNS Logs → Shadow AI Discovery, Proxy Traffic → Usage Analysis, Merge → AI Asset Inventory.

**Reasoning:** DNS catches traffic that never reaches the proxy (e.g., users with direct API keys). Proxy provides depth — user identity, token counts, data patterns. Combined gives both breadth and depth.

**Risks:** DNS logs may be incomplete depending on network architecture. Proxy logs may miss traffic from non-proxied subnets.

**Mitigations:** Both pipeline legs operate independently; inventory merges from both. Each leg emits events independently.

## RAG Architecture
| Option | Selected |
|--------|----------|
| Custom LangChain/LlamaIndex middleware | |
| AnonReq proxy (no middleware) | ✓ |
| Hybrid (proxy + optional SDK) | |

**User's choice:** Route through AnonReq proxy. Do NOT build LangChain/LlamaIndex middleware or custom SDK.

**Reasoning:** RAG has TWO inspection points — ingestion and retrieval. Both are covered by the existing Detection Engine pipeline. Building middleware would couple AnonReq to specific RAG frameworks. Middleware would also bypass the existing fail-secure guarantees.

**Risks:** Some RAG frameworks may not easily support proxy-based interception for the retrieval step.

**Mitigations:** Content-Type Dispatcher with `document_ingest` and `retrieved_context` types provides clear routing regardless of RAG framework. Document the proxy configuration required per RAG framework.

## RAG Inspection Points
| Option | Selected |
|--------|----------|
| Ingestion only | |
| Retrieval only | |
| Both ingestion + retrieval | ✓ |

**User's choice:** Both. INGESTION: Document → Chunk → Embed → Store (dedicated `/v1/rag/ingest` endpoint). RETRIEVAL: Question → Search → Retrieved Chunks → LLM (standard proxy path).

**Reasoning:** Ingestion-time detection prevents sensitive data from ever entering the vector store. Retrieval-time detection catches newly sensitive data or data that was not detected at ingestion time (e.g., context-dependent PII). Both are needed for defense in depth.

## CASB App Classification Location
| Option | Selected |
|--------|----------|
| Separate CASB config file | |
| Phase 8 YAML extension | ✓ |
| Hardcoded app list | |

**User's choice:** Phase 8 YAML extension. Keep policy model unified.

**Reasoning:** CASB classification is a policy decision — the same YAML that handles routing, DLP, and PDP #2 should also handle app classification. Separate config files fragment the policy model.

## AI Asset Inventory Scope
| Option | Selected |
|--------|----------|
| Basic (name, count, status) | |
| Detailed (full fields + cost) | ✓ |
| Full (detailed + automated remediation) | |

**User's choice:** Detailed. Must include: Provider, Model, User Count, Application Count, Token Volume, Estimated Cost, Data Classification, Approval Status, Risk Score, Last Seen, Owner, Business Unit. Plus COST ATTRIBUTION (by provider/model/requests/tokens/estimated spend).

**Reasoning:** Basic inventory lacks the dimensions needed for risk assessment and procurement decisions. Cost attribution answers "what are we spending on AI and where?" — the #1 question from finance teams.

## AI Risk Score
| Option | Selected |
|--------|----------|
| No risk scoring (just classification) | |
| Simple binary (approved/not approved) | |
| Numeric score (0–100) | ✓ |

**User's choice:** NEW component. Numeric risk score 0–100 with 6 dimensions: Provider Trust, Data Sensitivity, Shadow Usage, Approval Status, Model Location, Retention Policy.

**Reasoning:** Binary classification loses nuance (e.g., ChatGPT Enterprise is lower risk than DeepSeek Public). A numeric score enables threshold-based policy enforcement and comparative risk ranking. Analogous to CVSS for AI.

**Risks:** Score could be misleading if dimensions are weighted incorrectly.

**Mitigations:** Configurable per-tenant weights. Score breakdown available in inventory. Auditable calculation — no black box.

## Retrieval Policy Engine
| Option | Selected |
|--------|----------|
| No policy engine (all chunks pass) | |
| Greedy (deny all, allowlist) | |
| Permission-based (per-chunk evaluation) | ✓ |

**User's choice:** NEW component. Flow: Retrieved Chunks → Chunk Classification → Retrieval Policy → Allowed Chunks → LLM.

**Reasoning:** Solves critical RAG security problems that most deployments ignore: cross-department leakage, vector store oversharing, insider threats. Vector stores are typically "read all or read nothing" — the policy engine adds granular per-chunk access control.

**Risks:** False denials could break RAG applications that legitimately cross departments. Policy evaluation adds latency.

**Mitigations:** Default-allow with opt-in restrictive policies. Performance target ≤ 5ms per chunk. Audit trail for all denials enables tuning.

## Content-Type Routing
| Option | Selected |
|--------|----------|
| Separate gateway for Phase 19 | |
| Phase 9 Content-Type Dispatcher | ✓ |
| Both | |

**User's choice:** Everything through Phase 9 Content-Type Dispatcher. Not separate gateways.

**Reasoning:** Single gateway with `content_type` routing keeps all security guarantees in one place — fail-secure, audit, metrics, PDP. Separate gateways would need to duplicate all infrastructure.

## Active Scanning
| Option | Selected |
|--------|----------|
| No active scanning | ✓ |
| Passive + active (opt-in) | |
| Active always on | |

**User's choice:** No active scanning without explicit opt-in. Detection is entirely passive.

**Reasoning:** Active scanning creates network disruption risk and legal exposure. DNS + proxy analysis provides sufficient visibility for all three sub-products.

## Cost Attribution
| Option | Selected |
|--------|----------|
| No cost tracking | |
| Basic token counting | |
| Per-provider pricing model integration | ✓ |

**User's choice:** Track token volume per provider/model. Estimate cost using provider pricing tables.

**Reasoning:** Cost attribution is critical for procurement — "how much are we spending on each AI service?" Token counting at the proxy is the most accurate method since every request passes through.

## User Identification
| Option | Selected |
|--------|----------|
| Header-based (X-AnonReq-User-ID) | |
| JWT token extraction | |
| Proxy-inserted header | |
| Configurable chain: header → JWT → proxy | ✓ |

**User's choice:** Configurable chain. Extract from request headers first, then JWT, then proxy-inserted headers.

**Reasoning:** Different enterprises use different identity methods. A configurable chain ensures CASB and Retrieval Policy work without requiring all organizations to adopt a single identity pattern.
