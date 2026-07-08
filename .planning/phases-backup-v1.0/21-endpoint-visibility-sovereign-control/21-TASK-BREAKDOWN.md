# Phase 21 Task Breakdown: Endpoint Visibility & Sovereign Control

## Epics
1. Transparent proxy with TLS interception
2. Deployment topology support (reverse, transparent, VM, physical)
3. Voice/meeting channel connectors (SIP, WebRTC, WebSocket, gRPC)
4. Local STT integration (Whisper)
5. Audio stream sanitization (muting/beeping)
6. MCP protocol parsing and governance
7. Tool call argument/result inspection
8. AI firewall with jailbreak/injection detection
9. MITRE ATLAS mapping for all security events
10. Fail-closed network policy enforcement

## Stories

- **S-01:** As an enterprise architect, I can deploy AnonReq as a transparent proxy that intercepts all AI traffic at the network level without changing any application configuration.
- **S-02:** As an enterprise architect, I can deploy AnonReq in reverse proxy, VM, or physical appliance topologies to match my infrastructure requirements.
- **S-03:** As a compliance officer, I can intercept and sanitize voice/meeting audio streams so that spoken PII is redacted before reaching external AI services, with <150ms added latency.
- **S-04:** As an AI governance officer, I can monitor and sanitize agent tool calls and tool results so that autonomous agents do not leak sensitive data via MCP or function calls.
- **S-05:** As a CISO, injection/jailbreak attacks are blocked at the network edge by the AI Firewall before any processing budget is spent, within 20ms per request.
- **S-06:** As a security officer, all security events from these capabilities are mapped to MITRE ATLAS technique IDs for compliance reporting.
- **S-07:** As a security officer, the system fails closed: any error in interception, detection, or processing prevents unsanitized data from reaching external providers.

## Tasks

### T-001: Transparent Proxy Core
- Implement TCP/HTTP proxy listener with TLS interception support
- Dynamic TLS certificate generation signed by enterprise CA
- Integration with iptables/eBPF/DNS redirection mechanisms
- Certificate pinning detection and blocking
- Non-AI traffic pass-through detection (unknown schema → fail-open or fail-closed)

### T-002: Deployment Topology Abstraction
- `DEPLOYMENT_MODE` env var: `reverse`, `transparent`, `virtual`, `physical`
- Shared core proxy logic with topology-specific network attachment
- VM build scripts (cloud-init, OVF template)
- Physical appliance provisioning scripts

### T-003: Content-Type Dispatcher Extension
- Register new content types: `voice_stream`, `agent_tool_call`, `agent_tool_result`, `mcp_message`
- Route handlers for each new content type
- Ensure existing chat/completion/rag paths are unaffected

### T-004: Voice Channel Connectors
- SIP trunk proxy insertion (SIP proxy mode)
- WebRTC media stream inspection
- WebSocket streaming ingestion
- gRPC bidirectional stream proxy
- Audio format handling: PCM, WAV, Opus

### T-005: Local STT Integration
- Self-hosted Whisper model inference engine
- GPU acceleration detection and fallback to CPU
- Streaming transcription with overlapping chunk assembly
- In-memory transcript buffer (no disk writes)
- Configurable model size (tiny/base/small/medium/large)

### T-006: Sliding-Window Text Detection for Audio
- Overlapping window buffer (configurable, default 500ms)
- Context carryover between windows
- Cross-window entity continuity (same entity spanning windows)
- Timestamp mapping: entity start/end positions → millisecond-range audio frames

### T-007: Audio Stream Sanitization
- Audio frame-level muting (silence replacement)
- Audio spectrum masking (configurable beep tone generation)
- Millisecond-precision frame overwrite based on detection timestamps
- Outbound resynchronization of sanitized frames into stream

### T-008: MCP Protocol Parsing
- MCP message frame detection and parsing
- Mapping MCP tool_call/tool_result schemas to internal AnonReq schema
- Protocol version negotiation passthrough
- Unknown MCP message passthrough (structured data, no detection, fail-safe)

### T-009: Tool Call Injection Inspection
- Parse `tool_calls` and `tool_use` argument structures
- AI Firewall scan of argument values for injection/malicious code
- Schema enforcement: validate argument structure against expected schema
- Block or sanitize on violation, emit MITRE ATLAS event

### T-010: Tool Result Anonymization
- Force `tool_outputs` / `tool_result` through Detection_Engine
- Tokenize sensitive values while preserving structural JSON keys
- Error redaction: stack traces, internal IPs, env vars → `[REDACTED_ERROR]`
- Internal IP/stack trace pattern detection in tool outputs
- Audit flag on error redaction

### T-011: AI Firewall Implementation
- Local ONNX-optimized classifier model integration
- Jailbreak pattern database (locally cached, updatable)
- System prompt override detection
- Semantic injection scoring via vector embedding distance
- Execution within 20ms budget
- HTTP 403 response with generic security message

### T-012: MITRE ATLAS Mapping
- Dedicated `mitre_atlas.yaml` mapping config file
- Technique IDs for: prompt injection (AML-T0018), jailbreak (AML-T0025), model theft (AML-T0021), data poisoning (AML-T0016), supply chain (AML-T0015)
- ATLAS technique IDs in all new audit events

### T-013: AI Firewall Audit Events
- `firewall_block` — per blocked request
- `firewall_injection_detected` — per detected injection
- `firewall_jailbreak_detected` — per detected jailbreak
- `firewall_bypass_attempt` — per detected evasion attempt

### T-014: Agent Governance Audit Events
- `agent_tool_call_injected` — per blocked tool call
- `agent_tool_result_sanitized` — per tool result with tokenization
- `agent_tool_error_redacted` — per error redaction
- `mcp_protocol_violation` — per MCP parse failure

### T-015: Voice Pipeline Audit Events
- `voice_stream_started` / `voice_stream_ended` — per stream lifecycle
- `voice_entity_detected` — per sensitive entity in transcript
- `voice_audio_sanitized` — per audio frame overwrite
- `voice_latency_exceeded` — if P99 exceeds 150ms budget

### T-016: Transparent Proxy Audit Events
- `proxy_tls_intercepted` — per TLS interception
- `proxy_cert_pinning_detected` — per pinning detection
- `proxy_non_ai_blocked` — per non-AI traffic blocked
- `proxy_forward_error` — per upstream forward failure

### T-017: Fail-Closed Integration Tests
- All interception paths: TLS failure → 500, never forward
- Detection timeout → 500
- Cache failure → 500
- Classifier failure → 500 (not allow)
- Verified in every deployment topology

### T-018: Prometheus Metrics
- `anonreq_firewall_blocks_total` by detection_type label
- `anonreq_agent_tool_calls_inspected_total` by action label
- `anonreq_voice_streams_active` gauge
- `anonreq_voice_latency_ms` histogram (P50, P95, P99)
- `anonreq_proxy_tls_intercepted_total` by domain label
- `anonreq_fail_closed_total` by failure_reason label

### T-019: Property-Based Tests
- Round-trip: tool call anonymization → restoration → byte-for-byte match (keys preserved)
- Audio frame overwrite: silent/beep frames never contain original audio data
- AI Firewall: blocked requests always return 403, never spend
- Fail-closed: simulate failure in every pipeline component → always HTTP 5xx
- Cross-request token randomization for agent sessions
