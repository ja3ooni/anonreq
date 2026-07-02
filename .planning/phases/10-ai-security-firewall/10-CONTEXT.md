# Phase 10: AI Security Firewall - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 10 builds the AI Security Firewall — a hybrid rule+ML detection engine that inspects inbound prompts and outbound LLM responses for prompt injection, jailbreak attempts, and policy-violating content. It sits in both pre-anonymization and post-anonymization gates (inbound), and both pre-restoration and post-restoration gates (outbound). Phase 10 is the foundation; Phase 13 (AI Firewall & DLP) builds on this with DLP categories, MITRE ATT&CK mapping, and deeper analysis.

</domain>

<decisions>
## Implementation Decisions

### Detection Architecture
- **D-001:** Hybrid approach: fast rule-based pre-filter for normal requests (≤50ms), ML model for deeper analysis on flagged/suspicious requests (≤200ms total)
- **D-002:** Latency budgets: normal_budget = 50ms (rules only), flagged_budget = 200ms (rules + ML)

### Detection Categories
- **D-003:** Seven explicit detection categories:
  - prompt_injection (direct injection, indirect injection)
  - jailbreak (attempts to bypass security controls)
  - system_prompt_extraction (attempts to leak system prompt)
  - instruction_override (attempts to override instructions)
  - role_escalation (attempts to escalate privileges)
  - hidden_tool_invocation (hidden/covert tool calls)
  - secret_exfiltration (attempts to extract secrets)

### Pipeline Position
- **D-004:** Inbound: Both pre-anonymization (raw input) and post-anonymization (before ForwardingGuard)
- **D-005:** Outbound: Both pre-restoration (raw provider output) and post-restoration (before client delivery)

### Jailbreak Rule Format
- **D-006:** YAML rule set with both regex patterns AND semantic descriptions for ML model. Rules loaded as classification context for ML.

### Streaming Detection
- **D-007:** Buffer + sliding window approach (window size ~2KB). Detection runs on sliding window at chunk boundaries.

### Outbound Violation Handling
- **D-008:** Configurable per severity: HIGH → BLOCK (HTTP 451), MEDIUM → flag_and_forward, LOW → monitor. Severity thresholds configurable.

### Rule Administration
- **D-009:** Hot-reload rules within 60s without restart (same mechanism as Req 11 / Phase 5 config reload)
- **D-010:** GET /v1/admin/prompt-security/rules endpoint listing active rules

### Phase Boundary with Phase 13
- **D-011:** Phase 10 is the foundation (detection engine + rule system + basic inspection). Phase 13 (AI Firewall & DLP) adds DLP categories, MITRE ATT&CK mapping, contextual analysis, data exfiltration encoding detection.

### Audit & Metrics
- **D-012:** Events logged: event_type, session_id, tenant_id, confidence_score, rule_id, category
- **D-013:** Prometheus: anonreq_prompt_security_events_total with event_type, tenant_id, category labels

### the agent's Discretion
- ML model selection (small local ONNX model — e.g., ProtectAI, rebuff, or custom fine-tuned)
- Rule YAML schema details (patterns, severity levels, actions)
- Sliding window exact implementation strategy
- ML model inference optimization (quantization, caching, batching)
- Admin API design beyond the GET rules endpoint
- Threshold tuning (default 0.85 per FIREWALL-02)

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` §Phase 10 — Goal, success criteria, 5 success criteria
- `.planning/REQUIREMENTS.md` §Req 36 — FIREWALL-01 through FIREWALL-08
- `.planning/phases/08-Enterprise-Policy-Engine/08-CONTEXT.md` — PDP #1/#2, policy gates
- `.planning/phases/09-multimodal-document-anonymization/09-CONTEXT.md` — Content-Type Dispatcher, middleware patterns
- `.planning/phases/05-configuration-observability/05-CONTEXT.md` — Config hot-reload mechanism

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 5 config hot-reload — shared mechanism for rule reload
- Phase 8 PDP #1/#2 gates — firewall inspection sits at the same integration points
- Phase 9 Content-Type Dispatcher — pattern for middleware composition

### Integration Points
- Inbound pre-anon: after PDP #1, before Content-Type Dispatcher
- Inbound post-anon: before ForwardingGuard
- Outbound pre-restore: after provider response
- Outbound post-restore: before client delivery

</code_context>

<specifics>
## Specific Ideas

- Two-tier latency budget keeps competitive with OpenAI/Anthropic/Bedrock security features
- Seven categories align with OWASP LLM Top 10 threat categories
- Semantic rules + patterns fills the gap between regex-only (brittle) and ML-only (black box)
- Configurable severity per outbound violation gives operators control without code changes

</specifics>

<deferred>
## Deferred Ideas

- DLP categories and deep content analysis (Phase 13)
- MITRE ATT&CK for LLM mapping (Phase 13)
- Data exfiltration encoding detection (Base64, hex, stego — Phase 13)
- Full CRUD for rule management (beyond GET /v1/admin/prompt-security/rules)

</deferred>

---

*Phase: 10-ai-security-firewall*
*Context gathered: 2026-06-20*
