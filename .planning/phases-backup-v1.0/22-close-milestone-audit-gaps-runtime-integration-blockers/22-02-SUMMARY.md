# 22-02 SUMMARY: Wire DLP & Tool Governance into Runtime Pipeline

## Status

Completed. All stages created, registered, integration-tested.

## What was built

### New pipeline stages

- **`src/anonreq/pipeline/dlp.py`** — `InboundDLPStage` (inspects request text via `DLPEngine.inspect_request()` before provider forwarding; fails closed on BLOCK) and `OutboundDLPStage` (inspects provider response text via `DLPEngine.inspect()` before client delivery; fails closed on BLOCK/QUARANTINE).
- **`src/anonreq/pipeline/tool_governance.py`** — `ToolGovernanceStage` (extracts tool calls from OpenAI/Anthropic/MCP formats via `ToolExtractor`, evaluates via `PDPToolEvaluator`, blocks BLOCK decisions/crashes with `ToolBlockedError`).

### Runtime registration (`src/anonreq/routing/chat.py`)

- `build_pre_provider_pipeline()` — added `InboundDLPStage` then `ToolGovernanceStage` after `PolicyEnforcementStage`, before `TokenizationStage`.
- `build_pipeline()` — added `OutboundDLPStage` after `ProviderStage`, before `RestorationStage`.

### Integration tests

- `tests/integration/test_runtime_dlp_pipeline.py` — 3 tests verifying stage presence in `build_pipeline()`, inbound BLOCK calls `fail_secure()`, and outbound BLOCK prevents response delivery.
- `tests/integration/test_runtime_tool_governance.py` — 3 tests verifying OpenAI tool call evaluation, BLOCK decisions trigger fail-secure, and malformed arguments fail closed.

## Verification

```text
33 passed in 29.85s
```
