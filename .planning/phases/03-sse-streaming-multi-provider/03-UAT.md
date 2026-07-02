---
status: testing
phase: 03-sse-streaming-multi-provider
source:
  - 03-01-SUMMARY.md
  - 03-02-SUMMARY.md
  - 03-03-SUMMARY.md
  - 03-04-SUMMARY.md
started: 2026-07-01T09:45:00Z
updated: 2026-07-01T15:46:00Z
---

## Current Test

number: 2
name: Split Token Restoration
expected: |
  When a provider stream splits a token such as `[EMAIL_0]` across chunk boundaries, the client should never receive a partial token. The final restored stream should match the original value byte-for-byte.
awaiting: user response

## Tests

### 1. Streaming Chat Completion
expected: Send an OpenAI-compatible `POST /v1/chat/completions` request with `stream: true` through the gateway. The response should be `text/event-stream`, include anti-buffering headers, emit OpenAI-compatible delta frames as chunks arrive, restore any `[TYPE_N]` tokens before they reach the client, and end with `data: [DONE]`.
result: issue
reported: "HTTP/1.1 500 Internal Server Error with body {\"error\":{\"message\":\"Internal gateway error\",\"type\":\"http_error\",\"code\":\"http_error\",\"request_id\":\"req_693ab9d38fee4b81aa05296d\"}}"
severity: blocker

### 2. Split Token Restoration
expected: When a provider stream splits a token such as `[EMAIL_0]` across chunk boundaries, the client should never receive a partial token. The final restored stream should match the original value byte-for-byte.
result: [pending]

### 3. Client Disconnect Cleanup
expected: If the client disconnects during a streaming response, the upstream stream should stop, the TailBuffer/restoration session should close, and the Valkey mapping for that session should be deleted exactly once with no orphaned keys.
result: [pending]

### 4. Model Alias Listing
expected: `GET /v1/models` should return an OpenAI-compatible model list containing configured aliases such as `fast`, `smart`, `local`, and `gemini-pro`, with metadata and without provider credentials or internal URLs.
result: [pending]

### 5. Model Alias Routing
expected: Sending a chat request with `model: "smart"` should resolve through the alias registry to the configured provider/model before forwarding. Unknown aliases should return HTTP 400 with available aliases and should not forward the request upstream.
result: [pending]

### 6. Provider Adapter Normalization
expected: Anthropic, Gemini, and Ollama adapter paths should translate requests, normalize non-streaming responses, normalize stream events into `StreamEvent`, and return generic fail-secure provider errors without API keys, URLs, or raw response body content.
result: [pending]

### 7. Streaming Property and Load Gates
expected: The Phase 3 focused test suite should pass, including streaming Hypothesis tests, disconnect property tests, provider adapter tests, alias routing tests, and the 100-concurrent-disconnect load test.
result: [pending]

## Summary

total: 7
passed: 0
issues: 1
pending: 6
skipped: 0
blocked: 0

## Gaps

- truth: "stream:true chat completions return text/event-stream chunks and end with data: [DONE]"
  status: failed
  reason: "User reported: HTTP 500 Internal gateway error for request_id req_693ab9d38fee4b81aa05296d"
  severity: blocker
  test: 1
  root_cause: "The request reached the legacy ProviderStage, which POSTed to https://api.openai.com/v1/chat/completions and received 401 Unauthorized. Phase 3 provider adapter streaming is not wired into the chat route/pipeline yet; model alias resolution sets provider/model metadata but the actual network call still uses the legacy OpenAI-compatible base URL/API key path."
  artifacts:
    - path: "src/anonreq/routing/chat.py"
      issue: "stream:true requests run through the same non-streaming PipelineManager path."
    - path: "src/anonreq/pipeline/provider.py"
      issue: "ProviderStage still POSTs to configured OpenAI-compatible base URL instead of dispatching through ProviderRegistry/ProviderAdapter.stream_events for streaming requests."
    - path: "docker-compose.yml"
      issue: "Gateway healthcheck needed Authorization header for protected /health endpoint."
  missing:
    - "Branch chat_completions on body.stream before non-streaming response validation."
    - "Use ProviderRegistry and provider adapters for alias-resolved streaming requests."
    - "Wire StreamEvent -> TailBuffer -> StreamingRestorationStage -> SSEEmitter -> StreamingResponse."
    - "Preserve fail-secure cleanup via SessionCleanup in stream generator finally block."
  debug_session: ""
