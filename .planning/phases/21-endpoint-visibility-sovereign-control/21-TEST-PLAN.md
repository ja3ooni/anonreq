# Phase 21 Test Plan: Endpoint Visibility & Sovereign Control

## Unit Tests

### Transparent Proxy
- Dynamic TLS cert generation for intercepted domain names
- Enterprise CA certificate loading (PEM, PKCS12, HSM)
- Certificate pinning detection in TLS handshake
- Non-AI traffic classification (known vs unknown API schema)
- Protocol header preservation (keep-alive, connection timeouts)

### Voice Pipeline
- Audio format detection: PCM, WAV, Opus headers
- Streaming chunk assembly and reassembly
- Sliding-window overlap and context carryover
- Timestamp-to-frame millisecond mapping
- Audio frame muting: output frame silence check
- Audio beep generation: configurable frequency and duration
- STT output parsing and entity position mapping to audio timeline

### Agent Governance
- OpenAI `tool_calls` argument JSON parsing
- Anthropic `tool_use` content block parsing
- MCP message frame detection and field extraction
- Structural JSON key preservation after tokenization
- Error redaction: stack trace, IP, env var detection regexes
- Schema validation: expected vs actual argument structure

### AI Firewall
- Known jailbreak pattern matching (DB lookup)
- System prompt override detection
- Semantic classification inference (ONNX model load + run)
- Injection intent scoring threshold verification
- Budget enforcement: wall-clock measurement <20ms

### Content-Type Dispatcher
- New content type routing: `voice_stream`, `agent_tool_call`, `agent_tool_result`, `mcp_message`
- Unknown content type passthrough (no match → error)
- Backward compatibility: existing `chat`/`completion`/`rag` types unchanged

## Integration Tests

### Transparent Proxy Round-Trip
- Full request flow: client → DNS resolution → transparent intercept → TLS handshake → policy pipeline → upstream → response → client
- Verify original HTTP headers preserved end-to-end
- Verify keep-alive connection reuse works
- Verify upstream TLS 1.3 outbound connection
- Non-AI blocked: HTTP 451 with fail-closed
- Certificate-pinned: HTTP 451 with fail-closed

### Voice Pipeline Latency
- Measure P99 audio-to-sanitized-audio latency under load
- Verify <150ms P99 with GPU-accelerated STT
- Verify <300ms P99 with CPU-only STT (graceful degradation)
- Streaming continuity: no gaps or frame drops after sanitization
- Entity detected at chunk boundary: verify cross-chunk detection

### Agent Tool Call Anonymization Round-Trip
- Tool call with sensitive arguments: injection scan → block/allow
- Tool result with PII: force through Detection_Engine → tokenize values → restore → byte-for-byte match
- Structural keys preserved after round-trip (field names, column labels)
- Error in tool output: stack trace replaced with `[REDACTED_ERROR]`
- MCP message with tool_call: parsed, inspected, forwarded

### AI Firewall Detection Accuracy
- Known jailbreak patterns: 100% block rate
- System prompt extraction attempts: 100% block rate
- Benign traffic: <0.1% false positive rate
- Injection in agent tool call arguments: detected and blocked
- Edge cases: multi-language injection, encoded injection, split across messages

### Fail-Closed Behavior
- TLS interception failure → HTTP 500, no forward
- Detection engine timeout → HTTP 500, no forward
- Cache (Valkey) unavailable → HTTP 500, no forward
- AI Firewall classifier crash → HTTP 500, no forward
- STT engine failure → stream closed with error, no forward
- Each verified in all 4 deployment topologies

### Deployment Topology Tests
- Reverse proxy: configure base_url, verify all pipeline end-to-end
- Transparent proxy: DNS redirect + TLS intercept, verify zero-config interception
- Virtual appliance: boot VM, verify auto-config, run pipeline
- Physical appliance: boot, verify network bonding, run pipeline

## Performance Benchmarks

| Scenario | Target | Measurement |
|----------|--------|-------------|
| Proxy pass-through (no detection) | <5ms P95 | First byte in → first byte out |
| AI Firewall evaluation | <20ms P99 | Request received → ALLOW/BLOCK |
| Voice pipeline (GPU STT) | <150ms P99 | Audio chunk → sanitized chunk out |
| Tool call inspection | <50ms P99 | Tool call → decision |
| Tool result sanitization | <200ms P99 | Tool result → tokenized result |
| Full pipeline with detection | <500ms P99 | Request in → response out (excl. provider) |

## Property-Based Tests (Hypothesis)

- **Round-trip correctness**: agent tool result → anonymize → restore → byte-for-byte match (keys preserved)
- **Audio sanitization integrity**: overwritten audio frames contain zero original data (spectral analysis)
- **Fail-closed invariant**: any simulated failure in any pipeline component → HTTP 5xx (never 2xx with unsanitized data)
- **AI Firewall monotonicity**: more adversarial input never reduces detection score below threshold
- **Tool argument key preservation**: JSON keys unchanged after all transformations (only values mutated)
- **Stream consistency**: voice stream with N entity detections produces exactly M audio overwrites (M ≤ N, dedup of overlapping)
- **Cross-request token randomization**: 1000+ session pairs, probability of token collision ≥ 1 − 2⁻³²

## Security Tests

- **Certificate pinning avoidance**: app with pinned cert still blocked (fail-closed)
- **Injection via tool arguments**: SQL injection in tool call → blocked
- **Injection via MCP**: malicious MCP message → blocked
- **Audio data leakage**: sanitized audio frames contain no recoverable speech (spectrogram verification)
- **No-sensitive-data-in-logs**: all audit events metadata-only, field allowlist enforced
- **TLS downgrade prevention**: outbound always TLS 1.3 minimum
