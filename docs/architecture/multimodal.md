# Multimodal Document Anonymization

## Architecture Overview

The Multimodal Document Anonymization pipeline extends AnonReq's core
anonymization capabilities to handle multiple content types beyond plain
text.  It provides content-type-aware PII detection, tokenization, and
restoration for JSON, multipart form data, tool call arguments, and plain
text — all through a single unified pipeline.

```
Incoming Request
       │
       ▼
┌─────────────────────────────────────┐
│      Content-Type Dispatcher        │
│  (routes based on Content-Type      │
│   header + LocalRouter fallback)    │
└──────────┬──────────┬──────────┬────┘
           │          │          │
     text/plain  application/json  multipart/form-data
           │          │          │
           ▼          ▼          ▼
    ┌─────────┐ ┌──────────┐ ┌──────────────┐
    │  Text   │ │   JSON   │ │  Multipart   │
    │Analyser │ │ Analyzer │ │  Analyzer    │
    └─────────┘ └──────────┘ └──────────────┘
           │          │          │
           └──────────┴──────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │  Tokenization       │
           │  Engine             │
           └──────────┬──────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │  Provider Adapter   │
           │  → LLM Provider     │
           └─────────────────────┘
                      │
                      ▼ (Response)
           ┌─────────────────────┐
           │  Restoration        │
           │  Engine + PathTracker│
           └─────────────────────┘
```

## Content-Type Dispatcher

The `ContentTypeDispatcher` is the entry point for all multimodal payloads.
It parses the `Content-Type` header and routes to the appropriate analyzer.

### Routing Table

| Content-Type Header | Analyzer | Processed |
|---------------------|----------|-----------|
| `text/plain` | Text Engine | ✅ Yes |
| `text/plain; charset=utf-8` | Text Engine | ✅ Yes |
| `application/json` | JSON Analyzer | ✅ Yes |
| `application/json; charset=utf-8` | JSON Analyzer | ✅ Yes |
| `multipart/form-data; boundary=...` | Multipart Analyzer | ✅ Yes |
| `image/*`, `audio/*`, `video/*` | LocalRouter | ❌ ROUTE_LOCAL |
| `application/octet-stream` | LocalRouter | ❌ ROUTE_LOCAL |
| `application/pdf` | LocalRouter | ❌ ROUTE_LOCAL |
| Any unrecognized | LocalRouter | ❌ ROUTE_LOCAL |
| Empty/missing | Defaults to `text/plain` | ✅ Yes (safe default) |

### Unsupported Content Types

Unsupported content types are never forwarded to LLM providers. The
dispatcher returns `should_process=False` with an action of `ROUTE_LOCAL`
or `FORWARD` (for text-based types that are safe to pass through). The
`ContentTypeMiddleware` returns HTTP 415 for unsupported types.

## JSON Analyzer

The `JsonAnalyzer` recursively walks JSON structures to detect PII in
string leaf values.

### Key Features

- **Recursive walk**: Traverses dicts, lists, and nested structures
- **Sensitive key detection**: Values under sensitive keys (ssn, password,
  credit_card, api_key, etc.) get a confidence score boost (+0.15)
- **Depth limit**: Configurable `max_depth` (default 50) prevents
  unbounded recursion on deeply nested payloads
- **Non-string pass-through**: Numbers, booleans, nulls, and non-PII
  strings are analyzed without modification
- **JSON path tracking**: Each detected entity includes its JSON path
  (e.g., `$.user.profile.email`)

### Sensitive Key Patterns

The following key patterns trigger confidence score boosting:

- `ssn`, `social.security`
- `password`, `secret`, `token`
- `api.key`, `credit.card`, `bank.account`
- `pin`, `cvv`, `passport`
- `license.number`, `medical.record`
- `dob`

### Depth Limit Behavior

When `max_depth` is exceeded, the analyzer stops recursion at that depth.
Entities below the limit are not detected. This is a safety mechanism —
production deployments should set depth limits based on expected payload
structures.

## Multipart Analyzer

The `MultipartAnalyzer` parses `multipart/form-data` payloads and routes
each part to the appropriate sub-analyzer.

### Part Routing

| Part Content-Type | Handler | Description |
|-------------------|---------|-------------|
| `text/plain`, `text/html`, `text/markdown`, `text/csv` | Text engine | PII detection on decoded text |
| `application/json` | JSON Analyzer | PII detection on parsed JSON |
| `application/x-www-form-urlencoded` | Text engine | PII detection on form data |
| `image/*`, `application/octet-stream`, `application/pdf`, `audio/*`, `video/*` | Skipped | Binary content skipped (logged) |
| Unknown text-like | Text engine | Falls through to text detection |

### Metadata Scanning

File parts with filenames are scanned for PII in the filename metadata.
Field parts have their `field_name` tracked in detection results for
auditing.

## Tool Call Extraction

The `ToolCallExtractor` extracts and analyzes tool call arguments from
three provider-specific formats.

### Supported Formats

#### 1. OpenAI (`tool_calls`)

```json
{
  "role": "assistant",
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "send_email",
        "arguments": "{\"recipient\": \"alice@example.com\"}"
      }
    }
  ]
}
```

Detection path: `message.tool_calls[].function.arguments` → parsed as JSON
→ `JsonAnalyzer` → detected entities tracked per tool call.

#### 2. Anthropic (`tool_use`)

```json
{
  "role": "assistant",
  "content": [
    {"type": "text", "text": "I'll look that up."},
    {
      "type": "tool_use",
      "id": "tu_001",
      "name": "lookup_user",
      "input": {"email": "bob@example.com"}
    }
  ]
}
```

Detection path: `content[].input` for blocks with `type == "tool_use"`
→ `JsonAnalyzer` → entities tracked per tool call.

#### 3. MCP (JSON-RPC)

**Request path (tools/call):**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "lookup_user",
    "arguments": {"email": "carol@example.com"}
  }
}
```

Detection path: `params.arguments` → `JsonAnalyzer`

**Response path (result.content):**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {"type": "text", "text": "Customer name is John Smith"}
    ]
  }
}
```

Detection path: `result.content[].text` → wrapped as JSON
→ `JsonAnalyzer`

## Payload Limits

| Limit | Default | Content Type | Action When Exceeded |
|-------|---------|--------------|---------------------|
| `json_max_size_mb` | 5 MB | `application/json` | BLOCK |
| `multipart_max_size_mb` | 50 MB | `multipart/form-data` | BLOCK |
| `max_depth` | 50 | `application/json` | ROUTE_LOCAL |
| `max_parts` | 100 | `multipart/form-data` | BLOCK |

All limits are configurable via `PayloadLimits` when constructing the
`ContentTypeDispatcher`.

### Behavior

- **Size exceeded**: Payload is blocked (BLOCK action). No forwarding, no
  silent truncation — the caller receives an error response.
- **Depth exceeded**: Payload is routed to local processing (ROUTE_LOCAL)
  to avoid unbounded recursion.
- **Limit checks happen before analysis**: Payload limits are validated
  *before* any PII detection occurs, preventing resource exhaustion
  attacks.

## Restoration

The `RestoreEngine` provides path-aware token restoration:

- `restore_with_paths(text, mapping)`: Replaces tokens in text with
  original values. Supports case-insensitive and bracket-optional matching
  (both `[EMAIL_0]` and `EMAIL_0` work).
- `restore_response_with_paths(response, mapping)`: Recursively walks a
  response dict, restoring tokens in all string values.

### Path-Aware Restoration

The `PathTracker` records which JSON path each token was detected at:

```python
tracker = PathTracker()
tracker.track("[EMAIL_0]", "messages.0.tool_calls.0.function.arguments")
```

This enables:
- Precise restoration in structured responses
- Audit of where tokens were detected
- Debugging and verification

### Streaming Restoration

For SSE streaming responses, the `Tail_Buffer` pattern handles split
tokens: partial tokens at chunk boundaries are buffered and resolved once
the token completes. The `RestoreEngine` supports this via its
case-insensitive, bracket-optional matching.

## Configuration

```python
from anonreq.multimodal.dispatcher import ContentTypeDispatcher
from anonreq.multimodal.json_analyzer import JsonAnalyzer
from anonreq.multimodal.multipart_analyzer import MultipartAnalyzer
from anonreq.multimodal.limits import PayloadLimits

dispatcher = ContentTypeDispatcher(
    json_analyzer=JsonAnalyzer(detection_engine, max_depth=50),
    multipart_analyzer=MultipartAnalyzer(json_analyzer, text_engine),
    text_analyzer=text_engine,
    limits=PayloadLimits(
        json_max_size_mb=5,
        multipart_max_size_mb=50,
        max_depth=50,
        max_parts=100,
    ),
)
```

## Security Considerations

- **Fail-secure**: Any error during analysis (malformed JSON, parse
  failure, timeout) returns an empty result. The caller must handle this
  by blocking the request — never forwarding unsanitized data.
- **No PII in audit logs**: Analyzer metadata contains counts and types
  only. Raw values are stored in the ephemeral cache, never written to
  logs.
- **Unknown content types never forwarded**: If the dispatcher cannot
  determine the content type, the payload is routed locally or blocked.
- **Controlled failure for oversized payloads**: Limits are enforced
  before analysis. Oversized payloads receive a clear error response
  (no silent truncation).
