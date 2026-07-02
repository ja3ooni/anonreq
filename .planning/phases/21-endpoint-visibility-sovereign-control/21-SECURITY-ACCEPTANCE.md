# Phase 21 Security Acceptance: Endpoint Visibility & Sovereign Control

## Controls

| Control ID | Control | Mechanism | Verification |
|------------|---------|-----------|--------------|
| C-001 | TLS interception uses enterprise CA | Dynamic cert gen signed by loaded CA cert | Integration test: intercept → verify cert chain |
| C-002 | Non-AI traffic fail-closed | Unknown schema detection → HTTP 451 | Integration test: non-AI request → 451 |
| C-003 | Certificate-pinned traffic blocked | TLS handshake pinning detection → block or log | Integration test: pinned client → 451 (fail-closed) |
| C-004 | Fail-closed on any error | All pipeline errors → HTTP 5xx, never forward | Property test: simulate each failure → 5xx |
| C-005 | Local STT only (no audio exfiltration) | Whisper runs in-process, no network egress | Security test: STT process network namespace isolation |
| C-006 | Audio sanitization non-reversible | Muted/beeped frames contain no original speech data | Property test: spectral analysis of sanitized frames |
| C-007 | Audio latency budget enforced | Voice pipeline latency tracked, alert on P99 >150ms | Integration test: measure P99 under load |
| C-008 | Tool call injection detection | AI Firewall scans arguments, blocks if malicious | Integration test: known injection patterns → block |
| C-009 | Tool result key preservation | JSON keys never mutated during tokenization | Property test: round-trip → keys unchanged |
| C-010 | Tool error redaction | Stack traces, internal IPs, env vars replaced with `[REDACTED_ERROR]` | Integration test: tool output with stack trace → redacted |
| C-011 | AI Firewall inline before all processing | Pipeline order enforced; blocked requests never reach downstream | Integration test: blocked request → 403, zero downstream calls |
| C-012 | AI Firewall latency budget | Full evaluation <20ms P99 | Performance benchmark: measure under load |
| C-013 | AI Firewall no external dependency | Local ONNX classifier, no LLM-as-judge | Integration test: run firewall with no network access |
| C-014 | No PII in logs | Audit events are metadata-only, field allowlist enforced | Security test: grep audit output for raw values |
| C-015 | Protocol fidelity preserved | HTTP headers, keep-alive, timeouts mirrored to upstream | Integration test: compare request/response headers |
| C-016 | Outbound TLS 1.3 minimum | Upstream connections enforce TLS 1.3 | Security test: verify TLS version in outbound connections |

## Required Audit Events

| Event Type | Source | Required Fields |
|------------|--------|-----------------|
| `firewall_block` | AI Firewall | `detection_type`, `confidence_score`, `mitre_atlas_id`, `tenant_id`, `session_id` |
| `firewall_injection_detected` | AI Firewall | `injection_type`, `confidence_score`, `mitre_atlas_id: AML-T0018` |
| `firewall_jailbreak_detected` | AI Firewall | `jailbreak_pattern_id`, `confidence_score`, `mitre_atlas_id: AML-T0025` |
| `firewall_bypass_attempt` | AI Firewall | `bypass_technique`, `confidence_score` |
| `agent_tool_call_injected` | Agent Governance | `tool_name`, `argument_path`, `mitre_atlas_id` |
| `agent_tool_result_sanitized` | Agent Governance | `entity_count`, `entity_types`, `content_type` |
| `agent_tool_error_redacted` | Agent Governance | `redacted_type`, `mitre_atlas_id` |
| `mcp_protocol_violation` | Agent Governance | `message_type`, `violation_reason` |
| `voice_stream_started` | Voice Pipeline | `connector_type`, `audio_format`, `tenant_id` |
| `voice_stream_ended` | Voice Pipeline | `duration_ms`, `chunks_processed`, `entities_detected` |
| `voice_entity_detected` | Voice Pipeline | `entity_type`, `confidence`, `timestamp_ms` |
| `voice_audio_sanitized` | Voice Pipeline | `frame_count`, `method` (mute/beep), `duration_ms` |
| `voice_latency_exceeded` | Voice Pipeline | `actual_ms`, `budget_ms:150` |
| `proxy_tls_intercepted` | Transparent Proxy | `domain`, `cert_serial`, `tenant_id` |
| `proxy_cert_pinning_detected` | Transparent Proxy | `domain`, `action` (block/log) |
| `proxy_non_ai_blocked` | Transparent Proxy | `protocol`, `domain`, `policy` (fail-closed) |
| `proxy_forward_error` | Transparent Proxy | `upstream`, `error`, `bytes_before_failure` |
| `fail_closed_triggered` | All | `component`, `failure_reason`, `mitre_atlas_id` |

## Required Metrics

| Metric Name | Type | Labels | Source |
|-------------|------|--------|--------|
| `anonreq_firewall_blocks_total` | Counter | `detection_type`, `tenant_id` | AI Firewall |
| `anonreq_firewall_evaluation_duration_ms` | Histogram | `decision` (allow/block) | AI Firewall |
| `anonreq_firewall_latency_budget_exceeded_total` | Counter | - | AI Firewall |
| `anonreq_agent_tool_calls_inspected_total` | Counter | `action` (allow/block/sanitize), `tenant_id` | Agent Governance |
| `anonreq_agent_tool_results_sanitized_total` | Counter | `entity_type`, `tenant_id` | Agent Governance |
| `anonreq_agent_governance_duration_ms` | Histogram | `operation` (call_inspect/result_sanitize) | Agent Governance |
| `anonreq_voice_streams_active` | Gauge | `connector_type`, `tenant_id` | Voice Pipeline |
| `anonreq_voice_latency_ms` | Histogram | `connector_type` | Voice Pipeline |
| `anonreq_voice_entities_detected_total` | Counter | `entity_type`, `connector_type` | Voice Pipeline |
| `anonreq_voice_audio_sanitized_seconds_total` | Counter | `method` (mute/beep), `connector_type` | Voice Pipeline |
| `anonreq_voice_latency_exceeded_total` | Counter | `connector_type` | Voice Pipeline |
| `anonreq_proxy_tls_intercepted_total` | Counter | `domain`, `tenant_id` | Transparent Proxy |
| `anonreq_proxy_cert_pinning_detected_total` | Counter | `domain`, `action` | Transparent Proxy |
| `anonreq_proxy_non_ai_blocked_total` | Counter | `policy` (fail-closed) | Transparent Proxy |
| `anonreq_fail_closed_total` | Counter | `component`, `failure_reason` | All |

## MITRE ATLAS Mapping

| ATLAS ID | Technique | Phase 21 Coverage |
|----------|-----------|-------------------|
| AML-T0018 | Prompt Injection | AI Firewall: argument scan, injection scoring (T-011) |
| AML-T0025 | Jailbreak | AI Firewall: pattern DB, override detection (T-011) |
| AML-T0021 | Model Theft | AI Firewall: system prompt extraction detection (T-011) |
| AML-T0016 | Data Poisoning | Agent Governance: tool result sanitization (T-010) |
| AML-T0015 | Supply Chain Compromise | MCP governance: message validation (T-008) |
| AML-T0034 | ML Model Denial of Service | AI Firewall: resource exhaustion detection (future) |
| AML-T0040 | LLM Plugin Compromise | Agent Governance: tool call inspection (T-009) |

## Release Gates

| Gate | Criteria | Verification |
|------|----------|--------------|
| G-01 | Transparent proxy round-trip passes | Integration test: client → DNS → intercept → TLS → pipeline → upstream → response |
| G-02 | All 4 deployment topologies confirmed | Each topology runs full pipeline integration test |
| G-03 | Voice pipeline latency <150ms P99 (GPU) | Performance benchmark under load |
| G-04 | AI Firewall latency <20ms P99 | Performance benchmark under load |
| G-05 | AI Firewall detection: 100% on known jailbreaks | Integration test: known pattern set |
| G-06 | AI Firewall false positive rate <0.1% | Integration test: benign traffic corpus |
| G-07 | Tool call injection: 100% detection on test set | Integration test: injection corpus |
| G-08 | Tool result round-trip: keys preserved, values tokenized | Property test: 1000 random payloads |
| G-09 | Fail-closed: all failure modes return HTTP 5xx | Property test: simulate every component failure |
| G-10 | No PII in any audit event | Security test: grep all event types for raw values |
| G-11 | All 17 required audit events emitted | Integration test: trigger each event, verify emission |
| G-12 | All 17 Prometheus metrics registered | Integration test: scrape /metrics, verify labels |
| G-13 | MITRE ATLAS IDs present in relevant events | Integration test: verify `mitre_atlas_id` field |
| G-14 | Audio sanitization: zero original data recoverable | Property test: spectral analysis |
| G-15 | Outbound TLS 1.3 minimum enforced | Security test: verify TLS version negotiation |
| G-16 | Proxy pass-through (no detection) <5ms P95 | Performance benchmark |

## Compliance Mapping

| Regulation | Relevant Capabilities | Controls |
|------------|----------------------|----------|
| DORA Art. 17 (ICT Risk) | Transparent proxy, fail-closed, audit events | C-001, C-002, C-004, Required audit events |
| NIS2 Art. 21 (Security) | AI Firewall, agent governance, network interception | C-008–C-013 |
| EU AI Act Art. 15 (Accuracy/Robustness) | AI Firewall detection accuracy, false positive control | G-05, G-06 |
| ISO 27001 A.8.12 (Data Leakage) | Voice pipeline, tool result sanitization | C-005–C-007, C-009–C-010 |
| ISO 27001 A.8.25 (Security in Dev/Ops) | Fail-closed, no PII in logs | C-004, C-014 |
| GDPR Art. 5 (Data Minimization) | Local STT, audio sanitization | C-005, C-006 |
| HIPAA 45 CFR §164.312 (Integrity Controls) | Tool result tokenization, error redaction | C-009, C-010 |
| SEC Rule 17a-4 (Recordkeeping) | Audit events, MITRE ATLAS mapping | All audit events |

## Risk Acceptance

| Risk | Impact | Likelihood | Mitigation | Accepted By |
|------|--------|------------|------------|-------------|
| False negative in AI Firewall | Malicious prompt reaches LLM | Low | Regular DB updates, configurable severity | CISO |
| False positive in AI Firewall | Legitimate request blocked | Low | Generic 403 message, admin can whitelist | CISO |
| Certificate pinning blocks legitimate traffic | Application unavailable | Medium | Fail-open option for pinned certs (operator choice) | Enterprise Architect |
| STT model hallucinates sensitive content | False detection in audio | Low | Sliding-window context reduces hallucination rate | Compliance Officer |
| Tool result contains undetected PII | Sensitive data reaches LLM | Low | Detection Engine runs full pipeline; classification adds layer | AI Governance Officer |
