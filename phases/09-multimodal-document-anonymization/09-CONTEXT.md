# Phase 09: Multimodal Document Anonymization - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 9 extends the anonymization pipeline to handle all content types beyond plain text — tool call arguments (OpenAI, Anthropic, MCP), JSON payloads, and multipart form data with user-supplied metadata. It adds a Content-Type Dispatcher middleware that routes requests to the appropriate analyzer after PDP #1 and before PDP #2, then applies path-aware + streaming-aware token restoration.

</domain>

<decisions>
## Implementation Decisions

### Content Type Support
- **D-001:** Launch content types: text/plain, application/json, multipart/form-data
- **D-002:** Unknown content types → ROUTE_LOCAL (never FORWARD). Unknown payloads are exactly where leaks happen.

### Tool Call Formats
- **D-003:** Support all formats at launch: OpenAI tool_calls array, Anthropic tool_use content blocks, MCP protocol tool call/result payloads

### JSON Scanning
- **D-004:** Recursive scan with key-pattern awareness — detect sensitive keys (e.g., 'ssn', 'password', 'token') and apply context-aware detection to their values. Preserve JSON structural validity.

### Payload Limits
- **D-005:** Hard limits: json_max_size_mb = 5, multipart_max_size_mb = 50, max_depth = 50
- **D-006:** Exceeded limits → ROUTE_LOCAL or BLOCK depending on policy. Never silently truncate.

### Metadata Scope
- **D-007:** All user-supplied metadata, not limited to image_url descriptions and file names. Includes alt text, captions, file metadata blocks, context citations, attachments.

### Pipeline Integration
- **D-008:** Content-Type Dispatcher middleware sits after PDP #1, before PDP #2
- **D-009:** Architecture:
  PDP #1 → Content-Type Dispatcher (Text/JSON/Multipart Analyzers) → Unified Detection Result → Anonymization Engine (Phase 2) → PDP #2 → ForwardingGuard → Provider → Restore Engine (Path-aware + Streaming-aware) → Response

### Restoration
- **D-010:** Use both JSON-path-aware restoration (track anonymized JSON paths, restore tokens at original paths) AND streaming-aware restoration (Tail_Buffer for split tokens, Phase 3 pattern)

### Property Tests
- **D-011:** Invariants: restore(anonymize(x)) == x, json_structure_preserved == True, no_raw_pii_after_anonymize == True, token_collisions == False

### Deferred to Later Phases
- PDF parsing, OCR, DOCX extraction belong in later phases, not Phase 9
- MCP protocol deep integration details
- Additional content types beyond the three launch types

### the agent's Discretion
- Key-pattern list for JSON scanning (sensitive key names)
- Text/JSON/Multipart Analyzer implementation details
- Multipart form parsing library choice
- Exact Content-Type detection logic and header parsing
- Restore Engine integration with existing Phase 3 streaming restoration
- MCP protocol call/result extraction specifics

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Boundary & Requirements
- `.planning/ROADMAP.md` §Phase 9 — Goal and success criteria
- `.planning/REQUIREMENTS.md` §Req 23 — MULTI-01 through MULTI-06

### Architecture & Integration
- `.planning/phases/02-core-pipeline-classification-non-streaming/02-CONTEXT.md` — Detection pipeline, entity types, anonymization engine
- `.planning/phases/03-sse-streaming-multi-provider/03-CONTEXT.md` — Streaming restoration, Tail_Buffer approach
- `.planning/phases/08-Enterprise-Policy-Engine/08-CONTEXT.md` — PDP #1/#2, policy evaluation context
- `.planning/ARCHITECTURE_GUARDRAILS.md` — Pipeline integration patterns

### Provider Schemas
- OpenAI API schema: tool_calls array format
- Anthropic API schema: tool_use content blocks
- MCP protocol specification: tool call/result payloads

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 2 Anonymization Engine — core detection and replacement pipeline
- Phase 3 Restore Engine — streaming-aware token restoration, Tail_Buffer
- Phase 2 entity detection — Presidio-based NER and regex analyzers
- Phase 8 PDP infrastructure — decision gates before/after processing

### Established Patterns
- Content-type routing mirrors the provider adapter pattern from Phase 3
- JSON recursive scanning extends existing string-level detection
- Fail-secure: unsupported types → ROUTE_LOCAL, exceeded limits → ROUTE_LOCAL/BLOCK

### Integration Points
- Content-Type Dispatcher as new middleware before Phase 2 pipeline
- Restoration enhancement for path-aware token replacement
- Provider adapter extensions for MCP tool call/result handling
- PDP #2 receives classification result from the unified pipeline

</code_context>

<specifics>
## Specific Ideas

- Content-Type Dispatcher follows the same pattern as PDP gates — composable middleware
- Key-pattern awareness prevents "garbage in, garbage out" for structured data
- Streaming-aware restoration for tool calls mirrors Phase 3 SSE approach
- Path-aware restoration tracks JSONPointer or dot-notation paths for accurate token replacement

</specifics>

<deferred>
## Deferred Ideas

- PDF document parsing and anonymization (future phase)
- OCR for image-based content (future phase)
- DOCX extraction and anonymization (future phase)
- Additional content types beyond text/JSON/multipart (future phases)
- MCP protocol deep integration (future appliance phase)

</deferred>

---

*Phase: 09-multimodal-document-anonymization*
*Context gathered: 2026-06-20*
