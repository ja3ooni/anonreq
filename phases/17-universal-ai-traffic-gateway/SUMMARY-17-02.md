# Plan 17-02: AI Traffic Detection + MCP Inspection — Complete

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `src/anonreq/gateway/__init__.py` | 22 | Package exports |
| `src/anonreq/gateway/detector.py` | 310 | AI detection + MCP inspection |
| `src/anonreq/gateway/router.py` | 180 | Route table + reverse proxy routing |
| `tests/test_gateway_detector.py` | 286 | Unit tests (detector + MCP + block-all-unintercepted) |
| `tests/test_gateway_router.py` | 143 | Unit tests (route table) |
| `tests/test_gateway_property.py` | 170 | Hypothesis property-based tests |

## What Was Built

### AI Traffic Detection (`detector.py`)
- **`AIDetector`**: Detects AI provider traffic via hostname patterns (9 providers: openai, anthropic, gemini, ollama, deepseek, mistral, cohere, together, perplexity), endpoint path patterns, and request body model-name inference
- **`TrafficClassification`**: Structured classification with `is_ai_traffic`, `provider`, `endpoint_type`, `detected_by_hostname`, `confidence`
- **`ProviderMatch`**: Hostname match result with confidence score
- Custom pattern injection via `custom_patterns` constructor arg

### MCP Protocol Inspection (`detector.py`)
- **`MCPInspector`**: Parses MCP JSON-RPC 2.0 messages (requests, notifications, responses, errors)
- **`MCPMessage`**: Dataclass with `method_category`/`method_name` property extraction (e.g., `tools/call` → category=`tools`, name=`call`)
- `contains_tool_calls()` / `extract_tool_names()`: Tool use detection in request bodies

### Route Table (`router.py`)
- **`RouteTable`**: Hostname-to-provider mapping with wildcard support (e.g., `*.openai.com`)
- Default routes for all 9 known providers with target URLs
- Dynamic `add_route`/`remove_route`/`list_routes` operations
- `resolve_provider_url()`: Build full upstream URL from provider name + path
- Case-insensitive matching

### block-all-unintercepted-AI Support
- `TrafficClassification.detected_by_hostname` flag distinguishes known-hostname traffic from body-inferred
- `AIDetector.classify_request()` correctly classifies AI traffic even when hostname is unknown but body matches

## Test Results

- **80 tests**: 48 unit + 9 integration + 23 property-based (Hypothesis)
- **95 total** (including 15 existing Phase 17-01 tests)
- P95 passthrough latency: <5ms verified
- Determinism verified via Hypothesis
