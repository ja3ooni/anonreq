# Phase 10 Security Acceptance: AI Security Firewall

## Controls
- Dual-gate inbound detection (pre-anon + post-anon) prevents injection at both layers
- Dual-gate outbound detection (pre-restore + post-restore) catches violations at both layers
- Configurable thresholds per category prevent over/under-blocking
- Latency budgets prevent performance degradation under attack
- Hot-reload enforces no-downtime rule updates
- All audit events metadata-only

## Required Detection Categories
All 7 categories must be detectable with configurable thresholds:
- prompt_injection
- jailbreak
- system_prompt_extraction
- instruction_override
- role_escalation
- hidden_tool_invocation
- secret_exfiltration

## Required Audit Events
- `firewall_injection_detected` — per detected injection
- `firewall_outbound_violation` — per outbound violation
- `firewall_rule_reloaded` — per rule hot-reload

## Required Metrics
- `anonreq_prompt_security_events_total` with labels: event_type, tenant_id, category

## Release Gate
- All 7 categories detected in integration tests
- Latency budgets not exceeded under load (50ms normal, 200ms flagged)
- Zero false blocks on benign test corpus
- Hot-reload completes within 60s without dropped events
- No raw prompt/response content in any audit event
