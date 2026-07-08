---
phase: "02"
plan: "02-03"
subsystem: "core-engine"
tags: ["tokenization", "deduplication", "reverse-offset", "random-seed", "pii-replacement"]
requires: ["02-01", "02-02"]
provides: ["02-04", "02-05"]
affects: ["src/anonreq/tokenization/", "tests/test_tokenization.py"]
tech-stack:
  added: []
  patterns: ["TDD RED/GREEN for single task", "Standalone verification due to slow pytest imports", "Reverse-offset replacement (sort spans descending by start)"]
key-files:
  created:
    - "src/anonreq/tokenization/__init__.py"
    - "src/anonreq/tokenization/tokenizer.py"
  modified:
    - "tests/test_tokenization.py"
decisions:
  - "get_mapping() returns value→token copy (internal dedup direction), not token→value (output mapping direction)"
  - "Entity type truncated to 20 chars via simple [:20] slice — sufficient since Presidio types are all under 20 chars"
  - "Corrupted detection guard: skip spans with start < 0 or start >= end (T-02-03-05 mitigation)"
  - "Seed mask 0x3FFFFFFF ensures non-negative token indices within signed 32-bit range"
metrics:
  duration: ""
  completed_date: "2026-06-30"
status: complete
---

# Phase 2 Plan 3: Tokenization Engine — Summary

Implemented the Tokenization Engine that replaces detected PII spans with `[TYPE_N]` placeholders using reverse-offset replacement, session-scoped deduplication, and cryptographically random seed offsets. All TOKN-01 through TOKN-07 requirements are met.

## Tasks

### Task 1: Tokenizer with deduplication, reverse-offset, and random seed (RED `dfc5e26`, GREEN `75bc35e`)

**Package** (`src/anonreq/tokenization/__init__.py` — 16 lines):
- Exports `Tokenizer` and `TOKEN_PATTERN` from the tokenizer module

**Tokenizer** (`src/anonreq/tokenization/tokenizer.py` — 152 lines):
- `TOKEN_PATTERN = re.compile(r'\[([A-Z][A-Z_]{0,19})_(\d+)\]')` — regex matching `[TYPE_N]` per TOKN-01
- `Tokenizer` class with per-session state:
  - `_per_type_counters: dict[str, int]` — independent atomic counter per entity type
  - `_value_to_token: dict[str, str]` — deduplication map (value → token)
  - `_seed: int` — set via `initialize_session()` using `secrets.randbits(32)` per TOKN-05
- `initialize_session()` — resets all state, generates new cryptographic seed
- `tokenize(text, detections) -> tuple[str, dict[str, str]]`:
  - Empty detections → `(text, {})` fast path per TOKN-06/07
  - Sorts detections descending by `start` position for reverse-offset replacement per TOKN-04
  - Deduplication: same original value → same token per TOKN-02
  - Entity type truncated to 20 chars per TOKN-01
  - Token index = `(seed & 0x3FFFFFFF) + counter` per TOKN-05
  - Corrupted detection guard: skip spans with `start < 0` or `start >= end` (T-02-03-05)
- `get_mapping()` — returns shallow copy of `_value_to_token` to prevent external mutation

**Tests** (`tests/test_tokenization.py` — updated, 739+ lines, 24 test cases):
- TOKN-01 format: token matches regex, type uppercase, index ≥ 0
- TOKN-02 dedup: same email/phone twice → 1 mapping entry, token appears twice
- TOKN-03 distinct: different emails → 2 entries, different indices
- TOKN-04 reverse-offset: two spans → left token before middle text, right token after
- TOKN-05 random seed: two sessions → different tokens; session reset changes tokens; seed affects counter start
- TOKN-06/07 no entities: empty detections → original text, empty mapping
- Independent counters: EMAIL_0 and PHONE_0 with sequential per-type indices
- Entity type truncation: >20 chars truncated to 20; exactly 20 and short types preserved
- Round-trip: tokenize then manual restore → byte-for-byte match
- Session isolation: counters and dedup map reset on `initialize_session()`
- TOKEN_PATTERN: matches valid tokens, rejects invalid (lowercase, spaces, missing brackets)
- Large text: 1320+ chars with two identical emails → 1 mapping entry
- Edge cases: single char, empty string, whitespace, boundary spans, `get_mapping()` isolation
- Corrupted detection guard: negative start skipped, start≥end skipped

**Verification:** All 28+ checks passed in standalone script

## Plan-Level Verification

All 13 verification groups passed:
1. Basic import and instantiation ✅
2. TOKN-01 token format ✅
3. TOKN-02 deduplication ✅
4. TOKN-03 distinct values ✅
5. TOKN-04 reverse-offset ✅
6. TOKN-05 random seed ✅
7. TOKN-06/07 no entities ✅
8. Per-type independent counters ✅
9. Entity type truncation ✅
10. Round-trip correctness ✅
11. Session isolation ✅
12. get_mapping isolation ✅
13. Corrupted detection guard ✅

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong span offsets in test file**
- **Found during:** Task 1 verification
- **Issue:** Multiple tests had hardcoded detection span offsets that didn't match actual text positions (e.g., email `end=22` for "user@example.com" which is 16 chars = `end=23`; dedup test had second email at `start=42, end=57` but text is only 53 chars). These caused dedup test failures and reverse-offset order test failures.
- **Fix:** Recalculated all offsets from actual text content using Python. Created comprehensive offset reference table and rewrote test file with verified positions.
- **Commit:** `75bc35e`

**2. [Rule 1 - Bug] Reverse-offset order assertion logic**
- **Found during:** Task 1 verification
- **Issue:** `tokens_in_result` was derived from the mapping dict which preserves insertion order (rightmost span first). The test assumed `tokens_in_result[0]` was the leftmost token, but it was actually the rightmost (inserted first by reverse-offset processing).
- **Fix:** Sorted tokens by their position in the result text before positional comparisons.
- **Commit:** `75bc35e`

## Environment Notes

- Same slow pytest import environment as 02-01 and 02-02 (redis-py ~68s import)
- Verification done with standalone Python scripts instead of pytest
- No new external dependencies — Tokenizer uses only stdlib (`re`, `secrets`, `typing`)

## Key Decisions

1. **get_mapping() returns value→token direction** — This is the internal dedup map direction (value → token), designed for CacheManager storage. The `tokenize()` output mapping provides token→value for restoration. The TokenizationStage can use either direction as needed.

2. **Seed mask 0x3FFFFFFF** — Masks the 32-bit seed to 30 bits (positive signed 32-bit range), ensuring `(seed & 0x3FFFFFFF) + counter` never overflows. With counters starting at 0, the base offset is always non-negative.

3. **Entity type truncation via [:20]** — Simple slice truncation is sufficient because Presidio entity types (EMAIL_ADDRESS, PHONE_NUMBER, PERSON, etc.) are all under 20 chars. Only custom enterprise patterns could exceed 20 chars.

4. **Corrupted detection guard** — Spans with `start < 0` or `start >= end` are silently skipped rather than raising exceptions, matching the fail-secure principle (T-02-03-05).

## Threat Surface Scan

No new threat surface beyond what was declared in the plan's threat model. Key mitigations verified:
- T-02-03-01: `secrets.randbits(32)` from stdlib `secrets` module — CSPRNG
- T-02-03-02: Reverse-offset sort (descending by start) prevents position drift
- T-02-03-03: Per-type independent counters prevent cross-type collisions
- T-02-03-05: Corrupted detection guard (skip invalid spans, O(1) per span)

## Self-Check: PASSED

| Check | Status |
|-------|--------|
| File exists: `src/anonreq/tokenization/__init__.py` | ✅ |
| File exists: `src/anonreq/tokenization/tokenizer.py` | ✅ |
| File exists: `tests/test_tokenization.py` | ✅ |
| Import works: `from anonreq.tokenization import Tokenizer, TOKEN_PATTERN` | ✅ |
| Token format matches `[TYPE_N]` regex | ✅ |
| Deduplication: same value → same token | ✅ |
| Distinct values → different tokens with different indices | ✅ |
| Reverse-offset prevents position drift | ✅ |
| Different sessions have different seeds | ✅ |
| No entities → original text, empty mapping | ✅ |
| Per-type independent counters | ✅ |
| Entity type >20 chars truncated | ✅ |
| Round-trip: tokenize → restore → original | ✅ |
| Session isolation: initialize_session() resets state | ✅ |
| get_mapping() returns isolated copy | ✅ |
| Corrupted detections skipped | ✅ |
| Commit: `dfc5e26 test(02-03): add failing tests...` | ✅ |
| Commit: `75bc35e feat(02-03): implement Tokenizer...` | ✅ |
| Verification: all 13 groups passed | ✅ |
