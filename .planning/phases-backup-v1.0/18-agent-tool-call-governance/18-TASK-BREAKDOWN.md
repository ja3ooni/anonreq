# Phase 18 Task Breakdown: Agent & Tool Call Governance

## Epics
1. Tool permission policy (Phase 8 YAML extension)
2. Tool call interception and extraction (OpenAI/Anthropic/MCP)
3. PDP #2 tool permission evaluation
4. Async human approval flow (Phase 14 integration)
5. Tool result inspection (PII + reconstruction)
6. Audit events and metrics

## Stories
- As a security officer, each tool has a permission policy (allow, audit, approve, block)
- As an agent developer, tool parameters are anonymized before reaching external APIs
- As a compliance officer, tool results are inspected for sensitive data
- As a security analyst, blocked and approved tool calls generate audit events

## Tasks
- Implement Phase 8 policy YAML tools section parser
- Implement tool call extraction for OpenAI format
- Implement tool call extraction for Anthropic format
- Implement tool call extraction for MCP format
- Implement tool permission evaluation in PDP #2
- Implement async approval flow (HTTP 202 + oversight queue)
- Implement approval polling endpoint
- Implement tool result PII detection
- Implement reconstruction attempt detection
- Implement tool audit events
- Add property tests for tool governance invariants
