# Plan 17-03: Proxy-Only Mode + Remaining Capabilities — Complete

## Files Created/Modified

| File | Lines | Purpose |
|------|-------|---------|
| `src/anonreq/gateway/passthrough.py` | 124 | Proxy-only handler + gateway status |
| `tests/test_gateway_passthrough.py` | 180 | Unit + integration tests |
| `tests/test_gateway_property.py` | 170 | Hypothesis property tests (shared with 17-02) |
| `src/anonreq/main.py` | +10 | Gateway status endpoint + initialization |

## What Was Built

### Proxy-Only Mode (`passthrough.py`)
- **`ProxyOnlyHandler`**: Forwards requests without anonymization or detection
- Returns `{"status": "forwarded", "anonymization_applied": False, "mode": "proxy-only"}`
- P95 latency < 5ms verified in test
- No PII detection, no tokenization, no restoration

### block-all-unintercepted-AI
- `ProxyOnlyHandler.block_all_unintercepted_ai` flag (default: False)
- `GatewayStatus` proxy config exposes the flag and allowed providers list

### Gateway Status Endpoint
- `GET /v1/gateway/status` (auth-protected)
- Returns: service name, mode, uptime, proxy_config (block flag, allowed providers)
- Integrated into `main.py` lifespan + route registration

### Mode Enum (`ProxyMode`)
- Three modes: `proxy-only`, `full`, `transparent`
- `GatewayStatus.set_mode()` for runtime mode switching

## Integration with main.py
- `GatewayStatus`, `AIDetector`, `RouteTable` initialized in app lifespan
- `GET /v1/gateway/status` route registered after admin router

## Test Results

- All 80 new + 15 existing tests pass
- Property-based: latency, deterministic detection, route consistency
