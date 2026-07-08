# Phase 09 Task Breakdown: Multimodal Document Anonymization

## Epics
1. Content-Type Dispatcher middleware
2. JSON recursive analyzer with key-pattern awareness
3. Multipart form-data analyzer
4. Tool call argument extraction (OpenAI, Anthropic, MCP)
5. Restore Engine extensions (path-aware + streaming-aware)
6. Property-based tests

## Stories
- As a developer integrating with OpenAI, tool call arguments are anonymized before forwarding and restored in responses
- As a developer integrating with Anthropic, tool_use content blocks are anonymized and restored
- As a developer using MCP, tool call and result payloads are handled
- As a platform operator, JSON payloads are recursively scanned with sensitive key detection
- As a platform operator, multipart form submissions have all user-supplied metadata scanned
- As a security officer, unsupported content types are routed locally, never forwarded
- As a QA engineer, property tests verify round-trip correctness for all content types

## Tasks
- Implement Content-Type Dispatcher middleware (reads Content-Type header, routes to analyzer)
- Implement JSON Analyzer (recursive tree walk, key-pattern detection, string-leaf scanning)
- Implement Multipart Analyzer (parse parts, scan per-part, handle file metadata)
- Implement Unified Detection Result structure
- Implement tool call extraction for OpenAI format
- Implement tool call extraction for Anthropic format
- Implement tool call extraction for MCP format
- Extend Restore Engine with path-aware token tracking
- Implement payload limit validation (json_max_size_mb, multipart_max_size_mb, max_depth)
- Add property-based tests for all content types
- Add integration tests for each analyzer
- Update OpenAPI schema with new supported content types
- Update documentation

## Estimates
- Content-Type Dispatcher: 2 days
- JSON Analyzer: 4 days
- Multipart Analyzer: 4 days
- Tool call extraction (3 formats): 5 days
- Restore Engine extensions: 4 days
- Property-based tests: 3 days
- Integration tests + docs: 3 days

## Dependencies
- Phase 2 Anonymization Engine and entity detection
- Phase 3 Restore Engine and streaming infrastructure
- Phase 8 PDP #1/#2 middleware pattern
