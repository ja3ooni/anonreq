# Phase 18 Security Acceptance: Agent & Tool Call Governance

## Controls
- Per-tool permissions enforced at PDP #2 (can't bypass)
- Tool parameters anonymized before external forwarding
- Tool results inspected for PII and reconstruction attempts
- Approval flow auth-protected
- Block action prevents tool execution entirely

## Required Audit Events
- `tool_allowed` — per allowed tool call
- `tool_blocked` — per blocked tool call
- `tool_approval_required` — per approval-queued tool call
- `tool_approval_granted` / `tool_approval_denied`
- `tool_result_pii_detected` — per PII in result
- `tool_result_reconstruction_detected` — per reconstruction attempt

## Required Metrics
- `anonreq_tool_calls_total` by permission label
- `anonreq_tool_blocks_total` by tool label
- `anonreq_tool_result_violations_total` by type label

## Release Gate
- All 4 permission levels enforced correctly
- Tool calls anonymized before forwarding (confirmed by inspection)
- Tool result inspection detects PII and reconstruction
- Approval flow complete (suspend → queue → approve/reject → resume)
- No tool governance bypass via format switching
