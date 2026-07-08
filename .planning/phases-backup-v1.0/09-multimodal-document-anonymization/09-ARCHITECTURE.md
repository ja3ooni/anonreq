# Phase 09 Architecture: Multimodal Document Anonymization

## Context

Adds content-type-aware anonymization to the existing detection pipeline. A Content-Type Dispatcher middleware routes requests to the appropriate analyzer, producing a unified detection result consumed by the Phase 2 Anonymization Engine.

## Flow

```
Incoming Request
      |
      v
PDP #1 (from Phase 8)
      |
      v
Content-Type Dispatcher
      |
      ├── Content-Type: text/plain
      │     └── Text Analyzer (existing Phase 2 pipeline)
      │
      ├── Content-Type: application/json
      │     └── JSON Analyzer (recursive key-pattern-aware scan)
      │
      └── Content-Type: multipart/form-data
            └── Multipart Analyzer (parse parts, scan each by type)
      |
      v
Unified Detection Result
(entities, risk_score, classification)
      |
      v
Anonymization Engine (Phase 2)
      |
      v
PDP #2 (from Phase 8)
      |
      v
ForwardingGuard
      |
      v
Provider Adapter
      |
      v
Restore Engine (Path-aware + Streaming-aware)
```

## Components

### Content-Type Dispatcher
- Middleware layer after PDP #1
- Inspects Content-Type header to route to correct analyzer
- Unknown Content-Type → ROUTE_LOCAL (never FORWARD)
- Validates payload limits before routing (json_max_size_mb: 5, multipart_max_size_mb: 50)

### JSON Analyzer
- Recursive tree walk of JSON payloads
- Detects sensitive key patterns at every level
- Applies Phase 2 detection pipeline to string-valued leaf nodes
- Respects max_depth: 50
- Preserves JSON structural validity after anonymization

### Multipart Analyzer
- Parses multipart form-data into named parts
- Routes each part through the appropriate analyzer based on its content type
- Detects file uploads and metadata fields
- Extracts user-supplied metadata for scanning

### Unified Detection Result
- Standardized structure: entities[], risk_score, classification
- Independent of source analyzer
- Consumed by Anonymization Engine and PDP #2

### Restore Engine Extensions
- Path-aware token restoration: tracks JSONPointer/dot-notation paths for accurate replacement
- Streaming-aware: Tail_Buffer from Phase 3 handles split tokens in streaming responses
- Supports OpenAI tool_calls, Anthropic tool_use, and MCP tool call/result payloads

## Payload Limits
- json_max_size_mb: 5 (exceeded → ROUTE_LOCAL or BLOCK)
- multipart_max_size_mb: 50 (exceeded → ROUTE_LOCAL or BLOCK)
- max_depth: 50 (exceeded → ROUTE_LOCAL or BLOCK)
