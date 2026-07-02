# Phase 18: Agent & Tool Call Governance - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 18 delivers agent and tool call governance: per-tool permission policies (allow, allow_with_audit, require_human_approval, block), inspection of MCP/OpenAI/Anthropic tool calls and results, async human approval via Phase 14 oversight queue, and detection of PII/sensitive data in tool results including reconstruction attempts.

</domain>

<decisions>
## Implementation Decisions

### Tool Permission Policies
- **D-001:** Defined as Phase 8 policy YAML extension (tools section)
- **D-002:** Permissions: allow, allow_with_audit, require_human_approval, block
- **D-003:** Tool name pattern matching (glob or exact match per tool)

### Enforcement Point
- **D-004:** Integrated into PDP #2. Tool permissions evaluated as part of policy decision.

### Human Approval Flow
- **D-005:** Async model: tool call suspended, added to Phase 14 oversight queue
- **D-006:** Client receives HTTP 202 with approval_token
- **D-007:** Client polls approval status via GET /v1/oversight/approvals/{token}
- **D-008:** Notification sent when approval decision made

### Tool Call Formats
- **D-009:** Supports MCP protocol format, OpenAI tool_calls, Anthropic tool_use
- **D-010:** Tool parameters anonymized before forwarding to external API targets (Phase 9)

### Tool Result Inspection
- **D-011:** Both: standard PII/sensitive data detection (Phase 2 pipeline) AND reconstruction attempt detection
- **D-012:** Reconstruction detection looks for attempts to regenerate PII from anonymized tokens

### Audit Events
- **D-013:** tool_allowed, tool_blocked, tool_approval_required with structured details
- **D-014:** Audit fields: tool_name, action, provider, tenant_id, session_id, timestamp

### Per-Provider Governance (vs. Per-Tool)
- **D-015:** Governance policies are per-provider, not per-tool. Each AI provider (OpenAI, Anthropic, Gemini, Ollama, etc.) has an independent governance policy defining which tools are available, what credentials to supply, and what scope/context is provided.
- **D-016:** Credentials, configuration, and scope are provisioned on a per-delegation basis. Each tool invocation carries its own credential context, preventing cross-delegation credential leakage.
- **D-017:** Tool risk classification framework: tools are classified as Low (read-only, no sensitive data), Medium (read access to structured data), High (write access or sensitive data), or Critical (destructive operations, data exfiltration risk). Classification feeds into per-provider policy decisions.

### Strict Tool Isolation
- **D-018:** Model-exposed tools (MCP tools defined by the model provider) and host-exposed tools (enterprise tools connected via MCP client) are strictly isolated. Model MCP tools never see host tools. Host tools never see model MCP tools.
- **D-019:** Isolation is structural — separate tool registries, separate credential stores, separate audit namespaces. No tool listing from one domain is visible in the other.
- **D-020:** The governance layer inspects tool calls from both domains but applies independent policy sets per domain.

### the agent's Discretion
- Tool policy YAML schema details
- Reconstruction detection heuristics
- Approval token format and expiry
- Polling endpoint implementation
- Tool name pattern matching (glob, prefix, exact)
- Risk classification mapping rules
- Credential isolation implementation

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` §Phase 18 — Goal and success criteria
- `.planning/REQUIREMENTS.md` §APPL-04 (Req 51)
- `req/requirements_v2.md` — APPL-04
- `.planning/phases/08-Enterprise-Policy-Engine/08-CONTEXT.md` — PDP #2, policy YAML
- `.planning/phases/09-multimodal-document-anonymization/09-CONTEXT.md` — Tool call anonymization
- `.planning/phases/14-ai-governance-oversight/14-CONTEXT.md` — Oversight queue for approvals

</canonical_refs>

---

*Phase: 18-agent-tool-call-governance*
*Context gathered: 2026-06-20*
