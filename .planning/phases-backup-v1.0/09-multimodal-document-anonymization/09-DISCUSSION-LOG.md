# Phase 09: Multimodal Document Anonymization - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-20
**Phase:** 09-multimodal-document-anonymization
**Areas discussed:** Tool Call Formats, JSON Scanning, Metadata Scope, Pipeline Integration, Content Types, Restoration, Middleware Position, Payload Limits, Property Tests

---

## Tool Call Formats
| Option | Selected |
|--------|----------|
| OpenAI format only | |
| OpenAI + Anthropic | |
| All formats (OpenAI, Anthropic, MCP) | ✓ |

**User's choice:** All formats at launch.

## JSON Scanning
| Option | Selected |
|--------|----------|
| Recursive string-leaf only | |
| Recursive all values | |
| Recursive with key-pattern awareness | ✓ |

**User's choice:** Key-pattern awareness — detect sensitive keys and apply context-aware detection.

## Metadata Scope
| Option | Selected |
|--------|----------|
| image_url + file names only | |
| All user-supplied metadata | ✓ |
| As ROADMAP says | |

**User's choice:** All user-supplied metadata (alt text, captions, file metadata, citations, attachments).

## Pipeline Integration
| Option | Selected |
|--------|----------|
| New detection route before anonymization | |
| Extend existing detection pipeline | |
| Middleware layer | ✓ |

**User's choice:** Content-Type Dispatcher middleware.

## Content Types
| Option | Selected |
|--------|----------|
| text/plain, application/json, multipart/form-data | ✓ |
| text/plain, application/json only | |
| All detectable types | |

**User's choice:** text/plain, application/json, multipart/form-data.

## Restoration
| Option | Selected |
|--------|----------|
| JSON-path-aware restoration | ✓ |
| Inline token mapping in JSON | |
| Streaming-aware for tool calls | ✓ |

**User's choice:** Both path-aware + streaming-aware (Tail_Buffer).

## Middleware Position
| Option | Selected |
|--------|----------|
| Before any processing | |
| Inside existing pipeline | |
| After PDP #1, before PDP #2 | ✓ |

**User's choice:** After PDP #1, before PDP #2.

## Payload Limits
**User's choice:** json_max_size_mb: 5, multipart_max_size_mb: 50, max_depth: 50. Exceeded → ROUTE_LOCAL or BLOCK.

## Unknown Content Types
**User's choice:** default_action: ROUTE_LOCAL. Never FORWARD.

## Property Tests
**User's choice:** restore(anonymize(x)) == x, json_structure_preserved, no_raw_pii_after_anonymize, token_collisions == False.

## Deferred Ideas
- PDF parsing and anonymization
- OCR for image-based content
- DOCX extraction
- MCP protocol deep integration
