# Phase 18 Architecture: Agent & Tool Call Governance

## Tool Governance Flow
```
Agent Request (Tool Call)
  → Content-Type Dispatcher (Phase 9)
  → Provider Context Resolution
    ├── Determine provider (OpenAI/Anthropic/Gemini/etc.)
    └── Load per-provider governance policy
  → Tool Domain Classification
    ├── Model MCP tools (defined by model provider)
    └── Host tools (enterprise tools via MCP client)
  → Tool Call Extraction (OpenAI/Anthropic/MCP)
  → Tool Risk Classification (Low/Medium/High/Critical)
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

## Strict Tool Isolation
```
┌─────────────────────────────────────────────────┐
│                 Governance Layer                 │
│  ┌─────────────────┐  ┌─────────────────────┐   │
│  │ Model Tool Domain│  │  Host Tool Domain   │   │
│  │ (MCP tools from  │  │ (Enterprise tools   │   │
│  │  model provider) │  │  via MCP client)    │   │
│  ├─────────────────┤  ├─────────────────────┤   │
│  │ - tool_list     │  │ - db_query          │   │
│  │ - code_exec     │  │ - slack_send        │   │
│  │ - web_search    │  │ - email_read        │   │
│  │ - file_read     │  │ - api_call          │   │
│  └─────────────────┘  └─────────────────────┘   │
│  Separate registries │  Separate cred stores    │
│  Separate audit NS   │  Separate policies       │
│  ═══════════════════║═══════════════════════    │
│  NO CROSS-DOMAIN VISIBILITY                      │
└─────────────────────────────────────────────────┘
```

## Per-Provider Governance YAML (Phase 8 extension)
```yaml
providers:
  openai:
    tool_risk_classification:
      code_interpreter: critical
      file_search: high
      web_browsing: high
    governance:
      credentials: per_delegation
      config: per_delegation
      scope: per_delegation

  anthropic:
    tool_risk_classification:
      computer_use: critical
      text_editor_20241022: high
      bash_20241022: critical
    governance:
      credentials: per_delegation
      config: per_delegation
      scope: per_delegation

  host_mcp:
    tool_risk_classification:
      db_query: critical
      slack_send: medium
      email_read: high
      file_read: medium
    governance: isolated
```

## Tool Risk Classification
| Level | Examples | Default Action |
|-------|----------|----------------|
| Low | Read-only, no sensitive data | allow |
| Medium | Read access to structured data | allow_with_audit |
| High | Write access or sensitive data | allow_with_audit or require_human_approval |
| Critical | Destructive ops, exfiltration risk | require_human_approval or block |

## Approval Flow
```
Tool: require_human_approval
  → HTTP 202 { approval_token: "at_xxx", status: "pending" }
  → Added to Phase 14 oversight queue
  → Human approves/rejects
  → Result available: GET /v1/oversight/approvals/{token}
  → Webhook notification on decision
```
