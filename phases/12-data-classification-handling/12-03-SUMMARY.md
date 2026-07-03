# Plan 12-03 SUMMARY: Response Headers + Audit + Property Tests

## Completed

### Response Headers
- `X-AnonReq-Classification` — the final classification level name (e.g., `HIGHLY_RESTRICTED`)
- `X-AnonReq-Highest-Entity` — the entity type at the highest classification level (e.g., `API_KEY`)
- Set in `chat.py` route handler after classification runs

### Audit Metadata
- `classification_level` — highest classification level name (in every audit entry)
- `handling_action` — the per-level handling that was applied
- `highest_entity` — entity at the highest level
- `client_asserted_level` — only when client override was active
- `classification_flag` — set to `True` when handling is `anonymize_and_flag`
- All metadata recorded on `proc_ctx.audit_metadata`

### Hypothesis Property Tests (7 invariants)
1. **Classification level always set** — never `None`, never below `PUBLIC`
2. **Never drops below detected** — final classification ≥ detected level
3. **Deterministic** — same inputs → same output (50 re-runs)
4. **Handling action is known** — always one of the 3 values
5. **Highest entity matches level** — entity's mapped level equals `highest`
6. **Unknown entities don't crash** — graceful handling of unrecognized types
7. **Client override monotonic** — higher assertion increases, lower does nothing

### No-PII-in-Audit Verification
- Audit test confirms PII patterns are never present in classification audit metadata

### Test Results
- `test_classification_property.py`: 7 property tests (500 examples each)
- `test_classification_audit.py`: 6 audit verification tests

### Files Changed
- `tests/test_classification_property.py` — NEW
- `tests/test_classification_audit.py` — NEW
- `src/anonreq/routing/chat.py` — MODIFIED (response headers, audit metadata)
- `tests/test_classification_middleware.py` — included response header verification tests

## Full Test Suite
Total: **62 tests, all passing**
