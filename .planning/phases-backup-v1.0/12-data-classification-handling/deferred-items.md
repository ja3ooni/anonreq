# Deferred Issues — Phase 12, Plan 01

## Pre-existing test failure: `test_classification.py::TestClassificationRule::test_rule_matches_with_regex_condition`

**Discovered:** 2026-07-03 during 12-01 execution (Task 2 verification)
**Issue:** Test value "My password is secret123" doesn't match regex `(?i)password\s*[:=]\s*\S+` (colon/equals required but "is" provided instead — no `:` or `=` in the text).
**Root cause:** Pre-existing test bug, not related to Phase 12 changes.
**Deferred action:** Fix the test value to include `:` or `=` after "password" (e.g., "My password: secret123").
**Relevant file:** `tests/test_classification.py:242`
