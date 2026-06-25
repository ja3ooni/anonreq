# Phase 17: Universal AI Traffic Gateway - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 17 transforms the gateway into a universal AI traffic interception point supporting reverse proxy, transparent proxy (MITM with tenant CA), and virtual appliance deployment. Routes all AI interaction types (chat, voice, agents, RAG, MCP, email/CRM) through a single enforcement point with P95 < 5ms / P99 < 10ms proxy-only overhead.

</domain>

<decisions>
## Implementation Decisions

### Deployment Topologies
- **D-001:** Reverse proxy: existing FastAPI proxy (Phase 1)
- **D-002:** Transparent proxy: MITM with tenant-managed CA certificate
- **D-003:** Virtual appliance: same Docker Compose packaged as VM/AMI image

### TLS Interception
- **D-004:** MITM model: gateway terminates TLS (tenant CA), re-originates to provider
- **D-005:** CA management: admin API + file-based (dual path)
- **D-006:** Tenant uploads CA cert via API, file watch for updates

### AI Traffic Detection (block-all-unintercepted-AI)
- **D-007:** 3 layers: PAC file + hostname allowlist + flow analysis
- **D-008:** Enforcement via Phase 8 policy engine rule
- **D-009:** Gateway serves auto-generated PAC file, admin API for custom rules
- **D-010:** Hostname allowlist: known AI provider domains (OpenAI, Anthropic, Gemini, etc.)
- **D-011:** Flow analysis: detect AI API patterns in traffic that bypasses PAC/proxy config

### MCP Protocol
- **D-012:** Full MCP inspection: parse MCP messages, inspect tool calls/results, apply policy
- **D-013:** Integration with Phase 9 Content-Type Dispatcher for MCP content types

### Performance
- **D-014:** Proxy-only mode targets: P50 < 2ms, P95 < 5ms, P99 < 10ms
- **D-015:** Measured: gateway-internal timing (request receipt to ForwardingGuard decision)
- **D-016:** No anonymization/policy in proxy-only mode — just routing + TLS + audit

### Appliance
- **D-017:** Virtual appliance only (VM/AMI). No physical appliance this phase.
- **D-018:** Same Docker Compose services, packaged as VM image with systemd
- **D-019:** Appliance mode may exclude non-essential services (MinIO, Grafana) for minimal footprint

### Modes of Operation
- **D-020:** Proxy-only: routing + TLS + audit only, P95 < 5ms
- **D-021:** Full inspection: proxy + policy + detection + anonymization, normal latency budgets

### the agent's Discretion
- CA certificate format and validation
- PAC file format details
- Hostname allowlist contents
- Flow analysis heuristics
- VM image build process (Packer? Manual?)
- MCP protocol parser library
- Appliance management agent

</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` §Phase 17 — Goal and success criteria
- `.planning/REQUIREMENTS.md` §APPL-01 (Req 48)
- `req/requirements_v2.md` — APPL-01
- `.planning/phases/01-foundation-fail-secure-auth/01-CONTEXT.md` — FastAPI proxy, ForwardingGuard
- `.planning/phases/08-Enterprise-Policy-Engine/08-CONTEXT.md` — Policy engine for enforcement
- `.planning/phases/09-multimodal-document-anonymization/09-CONTEXT.md` — Content-Type Dispatcher for MCP

</canonical_refs>

---

*Phase: 17-universal-ai-traffic-gateway*
*Context gathered: 2026-06-20*
