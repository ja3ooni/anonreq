# Phase 17 Task Breakdown: Universal AI Traffic Gateway

## Epics
1. Transparent proxy (MITM with tenant CA)
2. AI traffic detection (PAC + allowlist + flow analysis)
3. MCP protocol full inspection
4. Performance optimization (P95 < 5ms proxy-only)
5. Virtual appliance packaging
6. Modes of operation (proxy-only vs full)

## Stories
- As a network admin, I deploy the gateway as a transparent proxy with tenant CA
- As a security admin, all AI traffic is routed through the gateway; bypassing is blocked
- As an operator, MCP protocol traffic is inspected and policy-enforced
- As an SRE, proxy-only mode adds <5ms P95 overhead
- As a platform engineer, I deploy the gateway as a VM appliance

## Tasks
- Implement MITM TLS termination with tenant CA
- Implement CA cert management API
- Implement CA cert file watch for hot-reload
- Implement PAC file generation endpoint (GET /v1/proxy.pac)
- Implement PAC customization API
- Implement hostname allowlist for AI provider detection
- Implement flow analysis for unidentified AI traffic
- Implement block-all-unintercepted-AI policy rule (Phase 8 extension)
- Implement MCP protocol parser
- Implement MCP message inspection in Content-Type Dispatcher
- Implement proxy-only mode (skip detection/anon)
- Profile and optimize for P95 < 5ms / P99 < 10ms
- Package Docker Compose as VM image
- Create appliance management agent
