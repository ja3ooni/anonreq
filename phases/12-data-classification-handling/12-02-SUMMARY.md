# Plan 12-02 SUMMARY: Pipeline Integration

## Completed

### ClassificationService (`src/anonreq/services/classification.py`)
- Wraps `ClassificationEngine` with client header parsing and per-level handling
- `parse_client_header(header_value)` — parses `X-AnonReq-Classification` to `ClassificationLevel` (returns `None` for missing/invalid)
- `classify(entity_types, client_level)` — runs engine, applies client override (increase-only), sets handling action
- `determine_handling(level)` — static policy: ≤CONFIDENTIAL → `allow_and_anonymize`, RESTRICTED → `anonymize_and_flag`, HIGHLY_RESTRICTED → `block`
- Tracks `highest_entity` — the label at the highest classification level

### ClassificationMiddleware (`src/anonreq/middleware/classification.py`)
- Parses `X-AnonReq-Classification` header, stores `ClassificationLevel` on `request.state.client_classification`
- Blocks HIGHLY_RESTRICTED client assertion immediately with HTTP 451
- Skips health/metric paths
- Registered in `main.py` after MetricsMiddleware, before PolicyMiddleware (PDP #2)

### Route Handler Integration (`src/anonreq/routing/chat.py`)
- After pipeline completes, collects entity types from `proc_ctx.detections`
- Runs `ClassificationService.classify()` with client level from request state
- Applies per-level handling: `block` → HTTP 451, `anonymize_and_flag` → audit flag

### Test Results
- `test_classification_engine.py`: 39 tests (28 existing + 11 new for ClassificationService)
- `test_classification_middleware.py`: 10 tests (header parsing, blocking, response headers)

### Files Changed
- `src/anonreq/services/classification.py` — NEW
- `src/anonreq/middleware/classification.py` — NEW
- `src/anonreq/models/classification.py` — MODIFIED (added `handling_action`, `highest_entity` to ClassificationResult)
- `src/anonreq/main.py` — MODIFIED (registered ClassificationMiddleware)
- `src/anonreq/routing/chat.py` — MODIFIED (integrated classification after pipeline)
- `tests/test_classification_engine.py` — MODIFIED (added ClassificationService tests)
- `tests/test_classification_middleware.py` — NEW
