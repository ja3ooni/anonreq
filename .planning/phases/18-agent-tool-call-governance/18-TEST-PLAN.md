# Phase 18 Test Plan: Agent & Tool Call Governance

## Unit Tests
- Tool permission parsing from Phase 8 YAML
- Tool call extraction: OpenAI format parsed
- Tool call extraction: Anthropic format parsed
- Tool call extraction: MCP format parsed
- Tool permission evaluation: correct action per permission
- Reconstruction detection: known patterns detected

## Integration Tests
- Tool allowed → forwarded with anonymized params
- Tool blocked → HTTP 403
- Tool require_human_approval → HTTP 202 + polling
- Tool result with PII → suppression/alert
- Tool result with reconstruction → alert
- Full agent flow: tool call → PDP #2 → anonymization → provider → result inspection

## Security Tests
- Tool policies cannot be bypassed by format switching (OpenAI → MCP)
- Tool parameters always anonymized before external API
- Reconstruction detection catches attempt to regenerate PII
- Approval polling auth-protected
