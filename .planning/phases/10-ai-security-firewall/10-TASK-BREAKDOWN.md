# Phase 10 Task Breakdown: AI Security Firewall

## Epics
1. Rule engine with YAML rule loading
2. ML model integration (small ONNX model)
3. Inbound firewall (pre-anon + post-anon gates)
4. Outbound firewall (pre-restore + post-restore gates)
5. Streaming detection with sliding window
6. Admin API for rules
7. Audit events + Prometheus metrics
8. Property-based + security tests

## Stories
- As a security officer, inbound prompts are inspected for 7 attack categories
- As a security officer, outbound responses are inspected for policy violations
- As a platform operator, jailbreak rules hot-reload within 60s
- As an SRE, firewall events are logged with structured audit entries and Prometheus counters
- As a developer, blocked requests return clear HTTP status codes (400, 451)

## Tasks
- Implement YAML rule loader with semantic rules + patterns
- Integrate small ONNX ML model for deep analysis
- Implement inbound pre-anon firewall middleware
- Implement inbound post-anon firewall middleware
- Implement outbound pre-restore firewall middleware
- Implement outbound post-restore firewall middleware
- Implement sliding window buffer for streaming detection
- Implement per-category configurable thresholds
- Implement per-severity outbound violation handling
- Implement hot-reload mechanism (shared with Phase 5 pattern)
- Implement GET /v1/admin/prompt-security/rules endpoint
- Add Prometheus counter anonreq_prompt_security_events_total
- Add structured audit entries for all firewall events
- Add property-based tests for detection invariants
- Add integration tests for all gates
