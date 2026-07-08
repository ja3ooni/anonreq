# Phase 17 Security Acceptance: Universal AI Traffic Gateway

## Controls
- MITM TLS termination with tenant-managed CA
- block-all-unintercepted-AI via Phase 8 policy engine (3-layer detection)
- MCP full inspection cannot be bypassed
- Proxy-only mode: no data leakage (no detection/anon needed)
- CA cert management auth-protected (admin role)

## Required Audit Events
- `proxy_connection_established` — per new TLS session
- `block_all_unintercepted_triggered` — per blocked bypass attempt
- `mcp_message_inspected` — per MCP message
- `proxy_mode_switched` — per mode change

## Required Metrics
- `anonreq_proxy_latency_ms` — P50/P95/P99
- `anonreq_proxy_connections_active` — concurrent
- `anonreq_unintercepted_blocked_total` — count

## Release Gate
- TLS termination verified with test CA
- PAC file generates correct proxy configuration
- block-all-unintercepted-AI blocks bypassing traffic
- MCP inspection parses and enforces policy
- Proxy-only: P95 < 5ms, P99 < 10ms confirmed
