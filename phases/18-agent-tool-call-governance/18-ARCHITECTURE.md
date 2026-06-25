# Phase 18 Architecture: Agent & Tool Call Governance

## Tool Governance Flow
```
Agent Request (Tool Call)
  → Content-Type Dispatcher (Phase 9)
  → Tool Call Extraction (OpenAI/Anthropic/MCP)
  → Parameter Anonymization (Phase 9)
  → Classification (Phase 12)
  → PDP #2 (tool permission evaluation)
    ├── allow_with_audit → log + forward
    ├── allow → forward
    ├── block → HTTP 403
    └── require_human_approval → HTTP 202 + oversight queue

LLM Response (Tool Result)
  → Tool Result Inspection
    ├── PII/sensitive data detection
    └── Reconstruction attempt detection
  → Policy enforcement
```

## Tool Policy YAML (Phase 8 extension)
```yaml
tools:
  slack_send:
    permission: allow_with_audit
    allowed_params: [channel, message]
  code_executor:
    permission: require_human_approval
  db_query:
    permission: block
```

## Approval Flow
```
Tool: require_human_approval
  → HTTP 202 { approval_token: "at_xxx", status: "pending" }
  → Added to Phase 14 oversight queue
  → Human approves/rejects
  → Result available: GET /v1/oversight/approvals/{token}
  → Webhook notification on decision
```
