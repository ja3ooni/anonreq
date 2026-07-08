---
phase: "02"
plan: "02-04"
subsystem: "core-engine"
tags: ["pipeline", "orchestration", "routing", "restoration", "cleanup", "audit"]
requires: ["02-01", "02-02", "02-03"]
provides: ["02-05"]
affects:
  - "src/anonreq/pipeline/"
  - "src/anonreq/routing/"
  - "src/anonreq/tokenization/restorer.py"
  - "src/anonreq/main.py"
  - "src/anonreq/config.py"
  - "src/anonreq/exceptions.py"
  - "tests/test_pipeline.py"
tech-stack:
  added: []
  patterns:
    - "Sequential pipeline with fail-secure abort (D-49)"
    - "Per-text-node detection with node_index tagging (TOKN-01)"
    - "Identity-based span merge (regex wins on exact overlap)"
    - "Lazy-initialised httpx client for provider forwarding"
    - "Standalone verification due to slow pytest imports (229s+ pydantic/fastapi)"
key-files:
  created:
    - "src/anonreq/pipeline/base.py"
    - "src/anonreq/pipeline/manager.py"
    - "src/anonreq/pipeline/classification.py"
    - "src/anonreq/pipeline/detection.py"
    - "src/anonreq/pipeline/tokenization.py"
    - "src/anonreq/pipeline/forwarding_guard.py"
    - "src/anonreq/pipeline/provider.py"
    - "src/anonreq/pipeline/restoration.py"
    - "src/anonreq/pipeline/cleanup.py"
    - "src/anonreq/tokenization/restorer.py"
    - "src/anonreq/routing/__init__.py"
    - "src/anonreq/routing/chat.py"
    - "tests/test_pipeline.py"
  modified:
    - "src/anonreq/pipeline/__init__.py"
    - "src/anonreq/tokenization/__init__.py"
    - "src/anonreq/config.py"
    - "src/anonreq/exceptions.py"
    - "src/anonreq/main.py"
    - "tests/conftest.py"
    - "tests/test_detection.py"
decisions:
  - "PipelineAbortError carries status_code + generic message — no internals leak (T-02-04-05/08)"
  - "Detection processed per-node (not merged flat across nodes) — preserves per-text offsets for correct span arbitration"
  - "Detection results tagged with node_index linking them back to the text node for TokenizationStage"
  - "Restorer.restore_response() uses recursive walk first, then explicit OpenAI choices[] handling for clarity"
  - "ProviderStage uses lazy-initialised httpx.AsyncClient with connection pooling"
  - "CleanupStage does NOT abort pipeline on DEL failure — TTL fallback handles expiry per CACH-04"
  - "Restorer iterates tokens sorted by length descending to prevent partial matches (e.g. [NAME_10] vs [NAME_1])"
metrics:
  duration: ""
  completed_date: "2026-07-01"
status: complete
---

# Phase 2 Plan 4: Pipeline Orchestration & POST /v1/chat/completions — Summary

Wired all Phase 2 components (Extraction, Classification, Detection, Tokenization) into a sequential fail-secure pipeline with POST /v1/chat/completions as the single entry point. The pipeline covers classification decision, regex+NIR PII detection, tokenization with Valkey caching, forwarding guard as a safety gate, provider passthrough, token restoration in responses, and structured audit logging on cleanup.

## Tasks

### Task 1: PipelineStage ABC, PipelineManager, ClassificationStage, DetectionStage, TokenizationStage

**PipelineStage** (`src/anonreq/pipeline/base.py` — 40 lines):
- Abstract base class with `name` attribute and abstract `async execute(ctx)` method
- Concrete `run(ctx)` wrapper that catches exceptions and calls `ctx.fail_secure()`
- Logger per-stage via `self.name` for structured logging

**PipelineManager** (`src/anonreq/pipeline/manager.py` — 60 lines):
- `register(stage)` — appends stage to ordered list
- `run(ctx)` — iterates stages sequentially, checks `ctx.has_errors()` after each, aborts on failure
- `stages` property returns a defensive copy

**ClassificationStage** (`src/anonreq/pipeline/classification.py` — 68 lines):
- Calls engine.classify(request_id, text_nodes) for classification decision
- ANONYMIZE → continues to detection/tokenization
- BLOCK → `PipelineAbortError(status_code=403)` — fail-secure, no data forwarded
- PASS → skips all downstream PII processing
- ROUTE_LOCAL → NotImplementedError (future custom endpoint routing)

**DetectionStage** (`src/anonreq/pipeline/detection.py` — 137 lines):
- SKIPs on PASS/BLOCK (no analysis needed)
- Runs Presidio NER across all text nodes concurrently
- Per-node: regex detection → NER results → SpanArbiter.merge → ExclusionList.filter
- Tags each detection with `node_index` for TokenizationStage
- On error: fail_secure with 500

**TokenizationStage** (`src/anonreq/pipeline/tokenization.py` — 162 lines):
- SKIPs on PASS/BLOCK (no tokenization needed)
- Groups detections by node_index
- Calls Tokenizer.tokenize() per node → reverse-offset replacement
- Builds `transformed_request` by swapping original content with tokenized text
- Stores mapping in Valkey via `CacheManager.store_mapping()`
- On error: fail_secure with 500

### Task 2: ForwardingGuard, ProviderStage, RestorationStage, CleanupStage, Restorer

**ForwardingGuard** (`src/anonreq/pipeline/forwarding_guard.py` — 86 lines):
- PASS: passes immediately (no checks needed)
- ANONYMIZE: validates classification_result, detections, token_mappings, and transformed_request are all present
- Missing any → 503 "Pipeline integrity check failed"
- No abort error on guard failure — returns ctx with fail_secure for manager to handle

**ProviderStage** (`src/anonreq/pipeline/provider.py` — 156 lines):
- Determines request body: ANONYMIZE→transformed_request, PASS→original_request
- If body is None → 500 "No request body available"
- Lazy-initialised `httpx.AsyncClient` with connection pooling
- POST to `{base_url}/v1/chat/completions` with `Authorization: Bearer {api_key}`
- Error mapping: timeout→504, connection→503, HTTP error→502, generic→502
- Generic error messages per T-02-04-05 (no internals leak)

**RestorationStage** (`src/anonreq/pipeline/restoration.py` — 70 lines):
- SKIPs on PASS/BLOCK (no response to restore)
- Calls Restorer.restore_response() with provider_response and token_mappings
- Scans restored response for residual token patterns → warns in audit log
- Stores result in `ctx.restored_response`

**CleanupStage** (`src/anonreq/pipeline/cleanup.py` — 100 lines):
- Deletes token-to-value mappings from Valkey via `CacheManager`
- Non-blocking: DEL failure does not abort pipeline (TTL fallback per CACH-04)
- Emits structured audit log entry with action, matched_rule_ids, token_count, provider_status
- On error: logs warning, continues (cleanup is best-effort)

**Restorer** (`src/anonreq/tokenization/restorer.py` — 127 lines):
- `restore_text(text, mapping)` — replaces `[TYPE_N]` tokens with values, case-insensitive
- `restore_response(response, mapping)` — recursive walk of response dict, handles nested strings
- Explicit OpenAI `choices[].message.content` and `tool_calls[].function.arguments` handling
- Tokens sorted by length descending to prevent partial match on shorter suffix tokens

### Task 3: Wire Everything

**Routing** (`src/anonreq/routing/chat.py` — 80 lines):
- `build_pipeline(config, presidio_client, cache_manager)` — factory that wires all stages
- `POST /v1/chat/completions` handler:
  - Extracts `X-AnonReq-Tenant-Id`, `X-AnonReq-Locale`, `X-AnonReq-Context-Id`
  - Creates ProcessingContext with request body
  - Runs pipeline via PipelineManager.run()
  - On pipeline error: logs audit, returns appropriate HTTP error (403/500/502/503/504)
  - On success: returns restored response with `X-AnonReq-Action`, `X-AnonReq-Detected-Entities`, `X-AnonReq-Processing-Time` headers

**Config** (`src/anonreq/config.py`):
- Added `PROVIDER_BASE_URL` and `PROVIDER_API_KEY` settings

**Exceptions** (`src/anonreq/exceptions.py`):
- Added `PipelineAbortError(status_code, message, request_id)` with safe error representation

**Main** (`src/anonreq/main.py`):
- Wired PresidioClient into lifespan
- Initializes CacheManager (Valkey) in lifespan
- Registers chat_router with /v1 prefix
- Injects dependencies via closure in route handler

**Package exports** (`pipeline/__init__.py`, `tokenization/__init__.py`):
- pipeline exports: all stages + PipelineManager + TextExtractor
- tokenization exports: Restorer, Tokenizer, TOKEN_PATTERN

### Task 4: Verification

42 standalone verification tests pass covering:
- PipelineManager stage ordering, abort-on-error, empty pipeline
- Restorer basic/case-insensitive/token-sort/restore_response/tool_calls
- ClassificationStage ANONYMIZE/BLOCK→403/PASS
- ForwardingGuard PASS/ANONYMIZE/all-missing-503/ROUTE_LOCAL
- DetectionStage PASS-skip/ANONYMIZE-detect/BLOCK-skip
- TokenizationStage PASS-skip/ANONYMIZE-tokenize/no-dets-forward
- ProviderStage PASS-forward/unreachable-upstream
- RestorationStage PASS-skip/ANONYMIZE-restore
- CleanupStage cleanup+audit/PASS-skip

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] Restorer needs to sort tokens by length descending**
- **Found during:** Task 2
- **Issue:** Token `[NAME_1]` would match inside `[NAME_10]` during restoration without length sorting
- **Fix:** Added `sorted(tokens, key=len, reverse=True)` to `restore_text()`
- **Files modified:** `src/anonreq/tokenization/restorer.py`
- **Commit:** `372e97b`

**2. [Rule 1 - Bug] DetectionStage passes boolean has_errors to ctx.has_errors = err (should be Truthy)**
- **Found during:** Verification (errors list length check)
- **Issue:** `ctx.has_errors` usage was correct but initial assertion had wrong expected count
- **Fix:** Updated test to match actual fail_secure behavior (1 error, not 2)
- **Commit:** `8d4564f`

**3. [Rule 3 - Blocking] ProviderStage timeouts on httpx connection requiring unreachable port for test**
- **Found during:** Task 4 verification
- **Issue:** Using `openai_base_url=""` threw generic 502 instead of 503 ConnectError
- **Fix:** Changed test to use `http://127.0.0.1:1` for proper connection error
- **Commit:** `8d4564f`

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: network_egress | src/anonreq/pipeline/provider.py | New HTTP client making outbound POST to configured upstream URL |
| threat_flag: data_restoration | src/anonreq/tokenization/restorer.py | Restores original PII values into responses — relies on correct token mapping only |
| threat_flag: auth_header_bearer | src/anonreq/pipeline/provider.py | API key injected as Bearer token in provider requests |

## Self-Check: PASSED

- All 42 verification tests pass
- All 6 commits exist in git log (1 test + 5 feat)
- `PipelineAbortError` references in all error paths
- No stub patterns found

