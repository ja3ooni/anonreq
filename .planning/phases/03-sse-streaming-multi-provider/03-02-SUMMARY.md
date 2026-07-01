---
phase: 03-sse-streaming-multi-provider
plan: 02
type: execute
status: complete
requirements:
  - PROV-02
  - PROV-03
  - PROV-04
  - PROV-06
  - PROV-08
subsystem: Multi-Provider Adapter Layer
tags:
  - provider-adapter
  - anthropic
  - gemini
  - ollama
  - streaming
  - tdd
depends_on:
  requires:
    - 02-05 (ProviderAdapter ABC, core types, registry, capabilities)
  affects:
    - 03-03 (ProviderRouter integration)
    - 03-04 (Full-multiplexer integration)
tech-stack:
  added:
    - "httpx 0.28.1 (AsyncClient, stream API)"
    - "respx 0.23.1 (HTTP mocking)"
  patterns:
    - "ProviderAdapter ABC with translate_request/execute/stream_events/translate_response lifecycle"
    - "TDD: RED/GREEN/REFACTOR per adapter"
    - "Async error normalization for both sync and streaming paths"
    - "Lazy HTTP client initialization per adapter"
    - "YAML-based capability resolution"
key-files:
  created:
    - src/anonreq/providers/anthropic.py (416 lines)
    - src/anonreq/providers/gemini.py (415 lines)
    - src/anonreq/providers/ollama.py (344 lines)
  modified:
    - tests/unit/providers/test_adapters.py (+27 test cases across 3 providers)
  created (infrastructure):
    - tests/unit/providers/conftest.py (mock API key env vars)
metrics:
  tasks_total: 8
  tasks_completed: 8
  tests_added: 27
  tests_passing: 27
  commits: 7
  files_created: 4
  files_modified: 1
  duration_minutes: ~45
---

# Phase 03 Plan 02: Multi-Provider Adapter Layer Summary

One-liner: Implemented three provider adapters (Anthropic Claude, Google Gemini, Ollama) following TDD with 27 passing tests — each adapter translates OpenAI-compatible requests to provider-native format, executes HTTP calls with fail-secure error normalization, and normalises streaming events to the canonical StreamEvent model.

---

## Tasks Executed

| Task | Name | Type | Status | Commit Hash |
|------|------|------|--------|-------------|
| 1 | Core adapter types (ProviderRequest, ProviderResponse, ProviderResult, ProviderCapabilities, ProviderAdapter ABC) | auto | ✅ | `e9640ee` |
| 2 | ProviderRegistry + CapabilityResolver + YAML config | auto | ✅ | `fe19322` |
| 3 | AnthropicAdapter (TDD) — RED → GREEN → REFACTOR | tdd | ✅ | `af794b1` (RED), `3142264` (GREEN) |
| 4 | GeminiAdapter (TDD) — RED → GREEN | tdd | ✅ | `c05f99b` (RED), `562c75b` (GREEN) |
| 5 | OllamaAdapter (TDD) — RED → GREEN | tdd | ✅ | `b80ffd4` (RED), `d12e95f` (GREEN) |

### Task 1: Core Adapter Types (e9640ee)

Created the foundational types in `adapter.py`:
- `ProviderRequest` — URL, headers, body, timeout, method (wraps httpx.Request-like shape)
- `ProviderResponse` — status_code, body (dict), headers (dict of lists)
- `ProviderResult` — response vs error branching envelope
- `ProviderCapabilities` — streaming, tools, system_prompt, max_context_length
- `ProviderAdapter` — abstract base with `translate_request`, `execute`, `stream_events`, `translate_response`, `capabilities` property

Also created `RestoredResponse` dataclass and the `src/anonreq/streaming/stream_event.py` module (StreamEvent, EventType, FinishReason) as a shared dependency for streaming.

### Task 2: ProviderRegistry + CapabilityResolver (fe19322)

Created:
- `ProviderRegistry` — maps provider name → adapter class via YAML config, lazy adapter import, `ProviderNotFoundError`
- `CapabilityResolver` — reads `config/capabilities.yaml` at startup, caches per-provider capabilities
- `resolve_api_key()` — checks `ANONREQ_{PROVIDER}_API_KEY` → `{PROVIDER}_API_KEY` → ValueError
- `config/providers.yaml` — maps anthropic/gemini/ollama to adapter class paths
- `config/capabilities.yaml` — per-provider feature flags (streaming, tools, system_prompt, locales, max tokens)

### Task 3: AnthropicAdapter (TDD, 9 tests)

- **translate_request**: OpenAI messages → Anthropic Messages API format
  - System message extracted to `system` top-level param
  - Roles preserved (user/assistant)
  - Tools converted to `name`/`description`/`input_schema` format
  - API key via `x-api-key` header, `anthropic-version: 2023-06-01`
- **execute**: POST to `/v1/messages`, error normalization
- **stream_events**: SSE parsing with `event:` / `data:` lines
  - `message_start` → EventType.START
  - `content_block_delta.text_delta` → EventType.TEXT_DELTA
  - `content_block_delta.input_json_delta` → EventType.TOOL_CALL_DELTA
  - `message_delta` with stop_reason → EventType.FINISH
  - `error` → EventType.ERROR
- **translate_response**: Anthropic content blocks → OpenAI `choices[].message.content`
- Error normalization: all HTTP error paths → 502 (fail-secure), no keys/URLs/content in messages
- Sync (`_normalize_error`) and async (`_normalize_error_async`) paths
- REFACTOR: minimal — `_normalize_error_raw` → `_normalize_error_async` for streaming error handling

### Task 4: GeminiAdapter (TDD, 9 tests)

- **translate_request**: OpenAI messages → Gemini `contents[]` with `parts` format
  - System message → `system_instruction.parts[].text`
  - "assistant" role → "model" role
  - Tools → `function_declarations`
  - Endpoint selection: `:generateContent` (non-streaming) vs `:streamGenerateContent?alt=sse` (streaming)
  - API key via `x-goog-api-key` header
- **execute**: POST to Gemini endpoint, error normalization
- **stream_events**: SSE `data: {}` parsing (no `event:` prefix)
  - Text chunks → TEXT_DELTA
  - `finishReason` field → FINISH
- **translate_response**: Gemini `candidates[].content.parts[].text` → OpenAI choices
- Finish reason mapping: STOP, MAX_TOKENS → LENGTH, SAFETY/RECITATION → CONTENT_FILTER
- Error normalization per PROV-08

### Task 5: OllamaAdapter (TDD, 9 tests)

- **translate_request**: Lightweight passthrough (Ollama uses OpenAI-compatible format)
  - System messages stay in messages array
  - Streaming flag forwarded in body
  - Configurable base URL via `OLLAMA_HOST` env var (default `http://localhost:11434`)
  - Optional API key (for remote deployments) — `Authorization: Bearer` header
  - Graceful fallback if no API key configured (local mode)
- **execute**: POST to `/api/chat`, error normalization
- **stream_events**: NDJSON line-by-line parsing
  - Each line's `message.content` → TEXT_DELTA
  - `done: true` → FINISH with done_reason mapping
- **translate_response**: Ollama `message.content` → OpenAI `choices[].message.content`
- Finish reason mapping: `stop` → STOP, `length` → LENGTH

---

## Tests

| Test Suite | Tests | Coverage |
|------------|-------|----------|
| TestAnthropicTranslateRequest | 4 | translate_request format, system→param, tools, API key |
| TestAnthropicTranslateResponse | 1 | response → canonical format |
| TestAnthropicStreamEvents | 2 | text delta SSE, finish STOP |
| TestAnthropicErrorNormalization | 2 | auth error, rate limit — no sensitive data |
| TestGeminiTranslateRequest | 4 | translate_request format, system→instruction, tools, API key |
| TestGeminiTranslateResponse | 1 | response → canonical format |
| TestGeminiStreamEvents | 2 | text delta SSE, finish STOP |
| TestGeminiErrorNormalization | 2 | auth error, rate limit — no sensitive data |
| TestOllamaTranslateRequest | 4 | translate_request format, system in list, stream flag, no auth default |
| TestOllamaTranslateResponse | 1 | response → canonical format |
| TestOllamaStreamEvents | 2 | text delta NDJSON, finish |
| TestOllamaErrorNormalization | 2 | error, stream error — no sensitive data |

**Total: 27 tests, all passing.**

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Non-async error normalization in stream_events**
- **Found during:** Task 3 GREEN — running Anthropic stream tests
- **Issue:** `_normalize_error_raw` used `await response.aread()` but was a sync method
- **Fix:** Renamed to `_normalize_error_async` and made it async, updated the call site
- **Files modified:** `src/anonreq/providers/anthropic.py`
- **Commit:** `3142264`

**2. [Rule 3 - Blocking] Missing API key env vars in test environment**
- **Found during:** Task 3 GREEN — running Anthropic `translate_request` tests
- **Issue:** `resolve_api_key("anthropic")` raised `ValueError` because no env var was set in test env
- **Fix:** Added `tests/unit/providers/conftest.py` with `pytest_sessionstart` hook setting mock API keys via `os.environ.setdefault`
- **Files created:** `tests/unit/providers/conftest.py`
- **Commit:** `3142264`

**3. [Rule 3 - Blocking] Streaming test SSE data not passed to respx response**
- **Found during:** Task 3 GREEN — streaming tests yielded 0 events
- **Issue:** `respx` mocked `Response(200)` without `content` or `headers` — `response.aiter_lines()` returned nothing
- **Fix:** Added `content=sse_data, headers={"Content-Type": "text/event-stream"}` to all streaming Response mocks
- **Files modified:** `tests/unit/providers/test_adapters.py`
- **Commit:** `3142264`

**4. [Rule 2 - Missing] Gemini streaming endpoint needs `?alt=sse` query param**
- **Found during:** Task 4 GREEN — streaming URL construction
- **Issue:** Gemini API requires `?alt=sse` for proper SSE response format on `streamGenerateContent`
- **Fix:** Added `?alt=sse` suffix to streaming endpoint URL
- **Files modified:** `src/anonreq/providers/gemini.py`
- **Commit:** `562c75b`

---

## Key Decisions

1. **TDD for all three adapters** — Each adapter got RED tests first, then GREEN implementation. No REFACTOR was needed for Gemini or Ollama (code was clean on first pass).

2. **Async error normalization split** — Maintained both `_normalize_error` (sync) and `_normalize_error_async` (async) since `execute` uses `response.json()` (sync read) while `stream_events` must use `await response.aread()` (async read from stream).

3. **Ollama base URL via OLLAMA_HOST env var** — Follows Ollama's standard convention, overridable for Docker/remote deployments.

4. **All error paths → 502** — Following fail-secure principle (PROV-08). Never leak whether an error is auth (401), rate limit (429), or upstream (5xx). This is more restrictive than typical proxy behavior but fully mitigates info leakage.

5. **CapabilityResolver is startup-cached** — Matches MVP scope (no runtime discovery). Per-provider capabilities are frozen at startup from YAML config.

---

## Known Stubs

None. All adapters are fully implemented with real HTTP logic, streaming, and error handling. No placeholders or mock data remain.

## Threat Flags

None. All provider adapters follow fail-secure error normalization. No new network endpoints, auth paths, or trust boundary violations were introduced beyond the intended provider API URLs.
