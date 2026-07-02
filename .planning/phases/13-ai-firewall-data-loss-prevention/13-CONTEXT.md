# Phase 13: AI Firewall & Data Loss Prevention - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 13 delivers the Data Protection Engine — a DLP detection and enforcement layer that runs alongside the Phase 10 Threat Detection Engine. It inspects AI traffic for 8 core DLP categories (extensible with tenant custom categories), detects data exfiltration encoding, and enforces per-category actions. Executes after Phase 12 Classification and before PDP #2.

</domain>

<decisions>
## Implementation Decisions

### Architecture: AI Firewall
- **D-001:** Two parallel engines:
  AI Firewall ├── Threat Engine (Phase 10) └── DLP Engine (Phase 13)
- **D-002:** Execution order: Threat Detection (Phase 10) → Classification (Phase 12) → DLP (Phase 13) → PDP #2 → Provider
- **D-003:** Phase 10 and Phase 13 share infrastructure, audit logging, and policy management but remain distinct engines

### DLP Categories
- **D-004:** Fixed core categories in code: PII, Financial, Health, Source Code, Credentials, Legal, Export Controlled, Intellectual Property
- **D-005:** Tenant custom categories via dedicated dlp.yaml configuration (e.g., TRADING_STRATEGY, MERGER_DATA, PATENT_DRAFTS)
- **D-006:** DLP configuration in dedicated dlp.yaml (separate from Phase 8 policy YAML)

### Per-Category Actions
- **D-007:** Actions: allow, anonymize, redact, quarantine, block
- **D-008:** Anonymize = tokenize (restorable), Redact = remove entirely (not restorable)
- **D-009:** Quarantine = block request + log metadata only (no payload stored)

### Contextual Rules
- **D-010:** Category wins, then filter: category determines base action. Business unit and classification_level refine (tighten) the action, never loosen.

### Data Exfiltration Detection
- **D-011:** Hybrid approach: heuristic pattern matching (Base64-like, hex-encoded, high-entropy strings) + Shannon entropy analysis for unknown encodings
- **D-012:** Detection at both inbound (exfiltration attempt in prompt) and outbound (exfiltrated data in response) gates

### MITRE ATT&CK
- **D-013:** Dedicated MITRE mapping config file linking DLP rules → MITRE techniques
- **D-014:** MITRE technique IDs in audit events for compliance reporting

### Inbound/Outbound
- **D-015:** Inbound DLP: detect sensitive data in prompts before provider sees it
- **D-016:** Outbound DLP: detect sensitive data in LLM responses before client receives it
- **D-017:** Outbound data exfiltration via encoding (Base64, hex, stego) → HTTP 451

### Integration with Phase 8
- **D-018:** DLP actions (block, anonymize, redact, quarantine) enforced as PDP #2 decisions
- **D-019:** DLP audit events emitted to existing audit logger

### the agent's Discretion
- DLP category detection patterns and rules
- dlp.yaml schema design
- Shannon entropy threshold values
- Custom category regex/pattern format
- MITRE mapping config file format
- Encoding detection implementation (Base64/hex/stego detection libraries)

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` §Phase 13 — Goal and success criteria
- `.planning/REQUIREMENTS.md` §APPL-05, APPL-02
- `.planning/phases/10-ai-security-firewall/10-CONTEXT.md` — Threat Engine foundation
- `.planning/phases/12-data-classification-handling/12-CONTEXT.md` — Classification levels, PDP #2 input
- `.planning/phases/08-Enterprise-Policy-Engine/08-CONTEXT.md` — PDP #2, action types
- `req/requirements_v2.md` — APPL-05 (AI Firewall), APPL-02 (AI DLP)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 10 Threat Detection Engine — shares pipeline infrastructure, audit logging, policy management
- Phase 12 Classification Engine — provides classification level for contextual DLP rules
- Phase 8 PDP #2 — enforcement point for DLP decisions
- Phase 5 AuditLogger — structured event emission for DLP events
- Phase 8 Policy YAML — base platform for policy configuration (dlp.yaml separate)

### Integration Points
- DLP Engine at same pipeline layer as Threat Engine
- DLP results feed into PDP #2 alongside classification
- Audit events: dlp_violation, dp_exfiltration_detected, dp_action_applied

</code_context>

<specifics>
## Specific Ideas

- Separate Threat + DLP engines reflects how enterprise security products operate (different teams own different risks)
- Exfiltration detection before provider is critical — once data reaches OpenAI/Anthropic, you've already lost control
- Tenant custom categories make the platform useful for specialized industries (finance, pharma, legal)
- Category-wins-then-filter mirrors DLP products like Symantec/Digital Guardian/Varonis

</specifics>

<deferred>
## Deferred Ideas

- Advanced steganography detection (beyond Base64/hex — Phase 20+)
- DLP incident management dashboard (Phase 14 Admin Portal)
- Automated DLP response workflows (Phase 14+)

</deferred>

---

*Phase: 13-ai-firewall-data-loss-prevention*
*Context gathered: 2026-06-20*
