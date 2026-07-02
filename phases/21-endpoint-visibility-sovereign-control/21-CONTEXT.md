# Phase 21: Endpoint Visibility & Sovereign Control - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 21 delivers the Appliance-tier network-level AI governance capabilities — the features that elevate AnonReq from an application-level proxy to a full sovereign network security appliance. It encompasses transparent proxy interception (no app config changes), voice and meeting audio stream sanitization, agent/tool-call governance via MCP protocol inspection, and a self-hosted AI firewall blocking injection/jailbreak at the network edge. All traffic routes through the Phase 9 Content-Type Dispatcher using a single `content_type` routing field — NOT separate gateways for chat/RAG/agents.

This phase consumes Req 48, 50, 51, 52 (appliance tier) and Req 57, 58, 59, 60 (sovereign control).

</domain>

<decisions>
## Implementation Decisions

### Architecture: Single Gateway via Content-Type Dispatcher
- **D-001:** Everything routes through Phase 9 Content-Type Dispatcher. No separate gateways for chat/RAG/agents/voice/agents. Single `content_type` routing field (e.g., `chat`, `rag`, `voice`, `agent_tool_call`, `agent_tool_result`).
- **D-002:** The Content-Type Dispatcher is extended to recognize new content types: `voice_stream`, `agent_tool_call`, `agent_tool_result`, `mcp_message`.
- **D-003:** New route handlers register with the dispatcher via the existing plugin/handler pattern; no dispatcher core changes.

### Transparent Proxy Architecture
- **D-004:** TLS interception uses a tenant-managed enterprise CA certificate loaded at deployment. Dynamic on-the-fly TLS certificate generation for intercepted domain names.
- **D-005:** Network traffic redirection via iptables (Linux), eBPF (high-performance), or DNS overrides — configurable at deployment.
- **D-006:** Unknown/non-AI traffic handling controlled by `Fail_Open` vs `Fail_Closed` policy. `Fail_Closed` is default (block if can't parse/intercept).
- **D-007:** Certificate-pinned traffic detection: if TLS handshake fails due to pinning, apply block-all-unintercepted-AI policy per Req 48 AC-4.
- **D-008:** Protocol fidelity: preserve HTTP headers, keep-alive, connection timeouts between original client and upstream host.

### Deployment Topologies
- **D-009:** Four deployment modes:
  (a) **Reverse proxy** — client apps change `base_url` to point at AnonReq
  (b) **Transparent proxy** — network routing intercepts AI API traffic, no app reconfig
  (c) **Virtual appliance** — VM image for customer hypervisor (VMware, Hyper-V, KVM)
  (d) **Physical appliance** — pre-configured hardware for air-gapped deployments
- **D-010:** Topology selection at deployment/startup time via `DEPLOYMENT_MODE` env var. Core proxy logic is shared; only network-layer attachment differs.

### Voice & Meeting Protection Pipeline
- **D-011:** Streaming ingestion via configurable connectors: SIP trunk (SIP proxy insertion), WebRTC (media server integration), WebSockets, gRPC bidirectional streams.
- **D-012:** Audio formats: PCM, WAV, Opus encoded packets.
- **D-013:** Local self-hosted STT (Whisper) running on internal hardware, no audio transmitted externally per Req 50 AC-2. GPU acceleration where available.
- **D-014:** Sliding-window detection: streaming text chunks evaluated in overlapping windows of configurable size (default 500ms) with context carryover.
- **D-015:** Two output paths:
  - **Text path**: tokenize identified sensitive spans in outbound text stream
  - **Audio path**: overwrite sensitive audio frames with silence or masking tone (beeping) at millisecond precision
- **D-016:** Latency budget: 150ms P99 added to audio transport stream (Req 58 AC-6).

### Agent & Tool-Call Governance
- **D-017:** Parse native OpenAI `tool_calls`/`tool_outputs` and Anthropic `tool_use`/`tool_result` structures in all inbound/outbound payloads.
- **D-018:** Two inspection directions:
  - **Outbound tool calls** (LLM → tool): scan `arguments` for injection/malicious code, enforce AI Firewall schemas
  - **Inbound tool results** (tool → LLM): force through Detection_Engine, tokenize sensitive values
- **D-019:** Structural JSON key preservation: only values tokenized, keys/column names/programmatic variables remain untouched (Req 59 AC-4).
- **D-020:** Error redaction: tool output containing stack traces, internal IPs, environment variables → generalized error token + audit flag (Req 59 AC-5).

### AI Firewall
- **D-021:** Inline before all other processing (Threat Detection, DLP, everything). Blocked requests return HTTP 403, incur zero model spend.
- **D-022:** Local inference only — no LLM-as-judge. Uses optimized small-footprint classifier (ONNX-optimized model) executing locally.
- **D-023:** Detection vectors: known jailbreak patterns, system prompt override attempts, adversarial optimization signatures, role manipulation, code injection.
- **D-024:** Latency budget: 20ms per request at P99 for full evaluation stack (Req 60 AC-5).
- **D-025:** Locally cached threat signature database, regularly updatable via policy push.

### MITRE ATLAS Mapping
- **D-026:** All security events (firewall blocks, injection detections, governance violations) include MITRE ATLAS technique IDs in audit events.
- **D-027:** Dedicated `mitre_atlas.yaml` mapping config, separate from MITRE ATT&CK map (Phase 13) — ATLAS is AI-specific.

### Fail-Closed Behavior
- **D-028:** Default mode is fail-closed: any error in interception, detection, cache, timeout → HTTP 5xx, never forward unsanitized data.
- **D-029:** Transparent proxy non-AI pass-through configurable: unknown traffic either forwarded untouched (`Fail_Open`) or blocked (`Fail_Closed`). Default: `Fail_Closed`.
- **D-030:** Certificate pinning detection → block if `Fail_Closed`, log + forward if `Fail_Open`.

### No Active Scanning
- **D-031:** No active network scanning without explicit operator opt-in (per user direction in discussion).

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` §Phase 21 — Goal and success criteria
- `req/requirements_v2.md` §Req 48 — Universal AI Traffic Gateway
- `req/requirements_v2.md` §Req 50 — Voice and Meeting AI Protection
- `req/requirements_v2.md` §Req 51 — Agent and Tool Call Governance
- `req/requirements_v2.md` §Req 52 — AI Firewall
- `req/requirements_v2.md` §Req 57 — Universal AI Traffic Interception (Transparent Proxy)
- `req/requirements_v2.md` §Req 58 — Voice and Meeting AI Protection (Real-Time Audio)
- `req/requirements_v2.md` §Req 59 — Agent and Tool-Call Governance (MCP)
- `req/requirements_v2.md` §Req 60 — Self-Hosted AI Firewall
- `.planning/phases/09-content-type-dispatcher/09-CONTEXT.md` — Routing foundation
- `.planning/phases/10-ai-security-firewall/10-CONTEXT.md` — Threat Engine
- `.planning/phases/13-ai-firewall-data-loss-prevention/13-CONTEXT.md` — DLP Engine
- `.planning/phases/18-agent-tool-call-governance/18-CONTEXT.md` — Enterprise-tier agent governance

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 9 Content-Type Dispatcher — routing infrastructure will be extended with new content types
- Phase 10 Threat Detection Engine — shares inference patterns with AI Firewall
- Phase 13 DLP Engine — shares pipeline infrastructure for voice/agent content inspection
- Phase 2 Detection Engine — text detection pipeline reused for tool result inspection and voice transcripts
- Phase 8 PDP #2 — enforcement point for AI Firewall and governance decisions
- Phase 5 Audit Logger — structured event emission for all new security events

### Integration Points
- AI Firewall executes inline BEFORE all other processing (before even Threat Engine)
- Transparent proxy attaches at network layer BEFORE the FastAPI proxy handler
- Voice pipeline streams through Content-Type Dispatcher as `voice_stream` content type
- Agent governance parses `content_type: agent_tool_call` and `agent_tool_result` in dispatcher
- MITRE ATLAS events emitted to existing audit logger with new event types

</code_context>

<specifics>
## Specific Ideas

- Transparent proxy with TLS interception mirrors how enterprise DLP/SSO products (Zscaler, Netskope) operate — the user's network already trusts a CA, so this is a familiar pattern
- Single gateway via content type avoids the complexity of separate proxy instances while maintaining clean separation of processing paths
- Local Whisper STT keeps audio data air-gapped, critical for financial/health voice compliance
- Sliding-window detection with audio timeline mapping enables frame-accurate audio redaction
- AI Firewall as local classifier (not LLM-as-judge) avoids recursive model dependency and keeps latency under 20ms
- MITRE ATLAS extends existing ATT&CK mapping to cover AI-specific adversarial techniques

</specifics>

<deferred>
## Deferred Ideas

- Active network scanning/discovery (Req 53) — requires explicit opt-in, deferred to later phase
- AI CASB functionality (Req 54) — broader cloud access broker integration
- Secure RAG pipeline protection (Req 55) — specialized RAG flow security
- AI SOC integration (Req 56) — SIEM/SOAR feed connectors
- Advanced steganography detection beyond audio masking (Phase 22+)
- Federated deployment topology (multi-appliance active/active) — Phase 22+

</deferred>

---

*Phase: 21-endpoint-visibility-sovereign-control*
*Context gathered: 2026-06-26*
