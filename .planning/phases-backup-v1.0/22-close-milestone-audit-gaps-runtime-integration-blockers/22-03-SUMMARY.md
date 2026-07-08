---
phase: 22-close-milestone-audit-gaps-runtime-integration-blockers
plan: 03
type: summary
status: complete
completed: 2026-07-07
---

# Phase 22-03 Summary: Proxy-to-Pipeline Dispatcher Adapter

## Objective

Create `PipelineContentDispatcher` — an adapter bridging the proxy `dispatch(content_type, body, ctx)` contract to `PipelineManager.run(ctx)` — then wire it in `main.py` so reverse and transparent proxy AI traffic enters the real runtime pipeline instead of echoing raw bodies.

## Deliverables

| File | Action | Purpose |
|------|--------|---------|
| `src/anonreq/proxy/pipeline_dispatcher.py` | Create | `PipelineContentDispatcher` class — parses JSON, builds `ProcessingContext`, runs pipeline, returns response bytes |
| `src/anonreq/proxy/__init__.py` | Modify | Export `PipelineContentDispatcher` |
| `src/anonreq/main.py` | Modify | Wrap `app.state.pipeline` with `PipelineContentDispatcher` before passing to `create_deployment_proxy()` |
| `tests/test_proxy_pipeline_dispatcher.py` | Create | 9 unit tests covering dispatch, error paths, PII absence, fail-closed behavior |

## Key Design Decisions

- **Fail-secure by default**: Non-JSON content types, empty/malformed bodies, pipeline errors, and missing response fields all return structured JSON error bytes — never the raw request body.
- **Reuses existing extraction**: `TextExtractor.extract()` from `anonreq.pipeline.extraction` is called on the parsed body, same as `routing/chat.py`.
- **No proxy class changes**: `ReverseProxy` and `TransparentProxy` already call `content_dispatcher.dispatch()` — the adapter plugs in without touching those classes.
- **No PII in output**: `restored_response` is returned when available (anonymization happened), `provider_response` only as fallback. Pipeline errors and edge cases return fixed error bytes.

## Verification Results

```text
# Proxy dispatcher tests
uv run pytest tests/test_proxy_pipeline_dispatcher.py tests/test_proxy_topology.py tests/test_proxy_integration.py -q
...........................
27 passed in 0.71s

# Adjacent pipeline integration tests
uv run pytest tests/integration/test_runtime_dlp_pipeline.py tests/integration/test_runtime_tool_governance.py -q
......
6 passed in 0.35s

Total: 33 passed, 0 failed
```

## Requirements Addressed

- **APPL-01, APPL-02, APPL-03, APPL-06**: Reverse and transparent proxy AI traffic now dispatches through the anonymization-capable pipeline path.
- **APPL-DLP-01, APPL-DLP-02**: Pipeline dispatcher runs the full pipeline (including DLP stages) for proxy traffic.
- **APPL-AGENT-01, APPL-AGENT-02**: Tool governance and agent controls in the pipeline apply to proxy-dispatched requests.

## Threat Model Mitigations

| Threat | Status | Evidence |
|--------|--------|----------|
| T-22-03-01 (Info disclosure via proxy) | Mitigated | Pipeline runs before provider forwarding; restored_response is return path |
| T-22-03-02 (Tampering via malformed payload) | Mitigated | Non-JSON, empty, malformed, and non-dict bodies rejected with fail-closed error |
| T-22-03-03 (Spoofing via ctx metadata) | Mitigated | ctx tenant defaults to "safe" when absent; request_id generated via uuid4 |
| T-22-03-04 (Info disclosure in error paths) | Mitigated | Tests assert synthetic PII absent from all error responses |
