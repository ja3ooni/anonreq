# Phase 10 Test Plan: AI Security Firewall

## Unit Tests
- YAML rule loader parses semantic rules + patterns correctly
- ML model returns confidence scores within expected range
- Rule engine matches known injection/jailbreak patterns
- Sliding window buffer captures cross-chunk patterns
- Per-category configuration applies correctly
- Severity level configuration maps to correct actions

## Integration Tests
- Full inbound pipeline: PDP #1 → pre-anon firewall → dispatch → post-anon firewall → ForwardingGuard
- Full outbound pipeline: Provider → pre-restore firewall → restore → post-restore firewall → client
- BLOCK action → correct HTTP status (400 inbound, 451 outbound)
- flag_and_forward → log event + forward request
- monitor → forward request + log event
- Hot-reload: rules updated within 60s without restart

## Property Tests
- Known injection prompts always detected above configurable threshold
- Benign prompts never blocked (false positive rate ≤ stated threshold)
- Streaming detection catches injection across chunk boundaries
- Audit events never contain raw prompt/response content

## Security Tests
- Injection detection works for all 7 categories
- Inbound pre-anon catches raw injection (before it reaches detection pipeline)
- Inbound post-anon catches injection in sanitized content
- Outbound inspection blocks policy-violating content
- No PII in firewall audit events
