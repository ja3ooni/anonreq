# Phase 17 Test Plan: Universal AI Traffic Gateway

## Unit Tests
- TLS termination with tenant CA certificates
- PAC file generation: correctly lists all supported providers
- Hostname allowlist: matches known AI provider domains
- MCP message parsing: valid messages parsed, invalid rejected
- Proxy-only mode: no detection/anonymization invoked

## Integration Tests
- Transparent proxy full flow: client → PAC → gateway → provider
- block-all-unintercepted-AI: traffic bypassing gateway → HTTP 403
- MCP traffic: inspected, policy enforced
- Modes: proxy-only < 5ms P95, full mode normal budgets

## Performance Tests
- P50 < 2ms, P95 < 5ms, P99 < 10ms (proxy-only)
- Throughput: requests/second with proxy-only
- Concurrent connections with TLS termination

## Security Tests
- Invalid CA certs rejected
- TLS re-origination uses proper cipher suites
- block-all-unintercepted-AI cannot be bypassed
- MCP inspection cannot be bypassed by encoding tricks
