# Phase 10 Architecture: AI Security Firewall

## Flow

```
Inbound Request
      |
      v
PDP #1 (Phase 8)
      |
      v
Inbound Firewall (Pre-Anon)
  ├── Rule Engine (≤50ms budget)
  └── ML Model (only if flagged, ≤200ms total)
      | categories: prompt_injection, jailbreak,
      | system_prompt_extraction, instruction_override,
      | role_escalation, hidden_tool_invocation, secret_exfiltration
      |
      +--> BLOCK → HTTP 400
      |
      v
Content-Type Dispatcher (Phase 9)
      |
      v
Detection & Anonymization (Phase 2/9)
      |
      v
PDP #2 (Phase 8)
      |
      v
Inbound Firewall (Post-Anon)
      |
      +--> BLOCK → HTTP 400
      |
      v
ForwardingGuard
      |
      v
Provider
      |
      v
Outbound Firewall (Pre-Restore)
      |
      +--> BLOCK → HTTP 451 (HIGH severity)
      +--> flag_and_forward (MEDIUM)
      +--> monitor (LOW)
      |
      v
Restore Engine (Phase 3/9)
      |
      v
Outbound Firewall (Post-Restore)
      |
      +--> BLOCK → HTTP 451
      |
      v
Client
```

## Detection Categories
| Category | Inbound | Outbound |
|----------|---------|----------|
| prompt_injection | ✓ | |
| jailbreak | ✓ | |
| system_prompt_extraction | ✓ | |
| instruction_override | ✓ | |
| role_escalation | ✓ | |
| hidden_tool_invocation | ✓ | ✓ |
| secret_exfiltration | ✓ | ✓ |

## Latency Budgets
- Normal request: rules only, ≤50ms
- Suspicious/flagged: rules + ML, ≤200ms

## Streaming
- Sliding window buffer (~2KB)
- Detection runs at chunk boundaries on window
