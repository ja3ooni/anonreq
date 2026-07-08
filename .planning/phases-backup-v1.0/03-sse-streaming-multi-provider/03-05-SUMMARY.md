---
phase: 03-sse-streaming-multi-provider
plan: 05
status: complete
completed: 2026-07-06
subsystem: streaming chat route
tags:
  - sse
  - provider-adapters
  - fail-secure
requirements:
  - SSE-01
  - SSE-02
  - SSE-03
  - SSE-04
  - SSE-05
  - SSE-07
  - SSE-08
  - PROV-02
  - PROV-03
  - PROV-04
  - PROV-05
  - PROV-06
  - PROV-08
  - CACH-05
  - TEST-07
key-files:
  created:
    - tests/integration/test_streaming_chat_route.py
  modified:
    - src/anonreq/routing/chat.py
    - src/anonreq/pipeline/provider.py
decisions:
  - Provider ERROR stream events are normalized to generic SSE provider_error frames at the route boundary.
  - ProviderStage fails closed before any legacy HTTP POST when stream:true reaches the non-streaming provider stage.
metrics:
  focused_route_tests: 4 passed
  unit_phase3_subset: 62 passed
  property_load_gates: 19 passed
---

# Phase 03 Plan 05: Streaming Route Gap Closure Summary

`stream:true` chat completions now use the alias-resolved provider adapter streaming path at the route boundary, restore split tokens before SSE emission, expose anti-buffering headers, and clean up stream session mappings for finish, provider error, provider exception, and client disconnect terminal states.

## Completed Work

- Added route-level integration coverage in `tests/integration/test_streaming_chat_route.py`.
- Covered successful `POST /v1/chat/completions` streaming with `text/event-stream`, `data:` delta frames, `data: [DONE]`, alias resolution, adapter `stream_events()` dispatch, split-token restoration, anti-buffering headers, and session cleanup.
- Covered provider `ERROR` events and provider exceptions with generic metadata-only SSE error frames and cleanup.
- Covered client disconnect handling at the `_stream_chat_completions` route generator boundary, including stopped provider iteration and `CLIENT_DISCONNECT` cleanup.
- Hardened `src/anonreq/routing/chat.py` so adapter-provided stream error metadata cannot leak upstream URLs, env var names, raw request content, or restored sensitive values.
- Added a defensive fail-closed guard in `src/anonreq/pipeline/provider.py` so `stream:true` cannot fall through to the legacy OpenAI-compatible HTTP POST path.

## Verification Evidence

Passed:

```bash
PYTHONPATH=src uv run pytest tests/integration/test_streaming_chat_route.py -x --tb=short -v
```

Result: `4 passed in 0.40s`

Passed:

```bash
PYTHONPATH=src uv run pytest tests/unit/streaming tests/unit/providers/test_adapters.py tests/unit/routing -q
```

Result: `62 passed in 41.72s`

Passed:

```bash
PYTHONPATH=src uv run pytest tests/unit/streaming tests/unit/providers/test_adapters.py tests/unit/routing tests/property/test_streaming.py tests/property/test_disconnect.py tests/load/test_disconnect.py -q -m "not slow"
```

Result: the required verification was run in equivalent local subsets after hydrating macOS dataless source/test files:
- `PYTHONPATH=src pytest tests/integration/test_streaming_chat_route.py -x --tb=short -v` -> `4 passed in 0.45s`
- `PYTHONPATH=src pytest tests/unit/streaming tests/unit/providers/test_adapters.py tests/unit/routing -q` -> `62 passed in 1.16s`
- `PYTHONPATH=src pytest tests/property/test_streaming.py tests/property/test_disconnect.py tests/load/test_disconnect.py -q -m "not slow"` -> `19 passed in 175.54s`

The initial `uv run pytest` attempts stalled because many files under `src/anonreq`, `tests/property`, and `tests/load` were marked macOS `dataless`. After `brctl download` hydrated the relevant files, the same gates completed with direct `pytest`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Generic provider stream errors**
- **Found during:** Task 2
- **Issue:** Provider `ERROR` events were emitted with adapter-supplied metadata, which could include upstream URLs, env var names, or raw sensitive values.
- **Fix:** Route now emits a generic `{"message":"stream error","type":"provider_error"}` SSE error frame for provider `ERROR` events and raised provider exceptions.
- **Files modified:** `src/anonreq/routing/chat.py`, `tests/integration/test_streaming_chat_route.py`

**2. [Rule 2 - Missing critical functionality] Legacy stream fallthrough guard**
- **Found during:** Task 2
- **Issue:** If a streaming request reached `ProviderStage.execute()`, the legacy OpenAI-compatible POST path could still run.
- **Fix:** `ProviderStage` now fails closed before alias resolution or HTTP POST when the selected request body has `stream: true`.
- **Files modified:** `src/anonreq/pipeline/provider.py`

## Threat Flags

None. Changes are within the Phase 3 stream route/provider guard threat model and do not add new endpoints, durable persistence, or new network surfaces.

## Known Stubs

None.

## Self-Check: PASSED

- Created `tests/integration/test_streaming_chat_route.py`.
- Created `.planning/phases/03-sse-streaming-multi-provider/03-05-SUMMARY.md`.
- Verified focused route tests and Phase 3 unit subset pass.
