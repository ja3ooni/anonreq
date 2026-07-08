---
phase: 19-network-discovery-casb-secure-rag
plan: 03
subsystem: rag
tags:
  - rag
  - retrieval
  - policy
  - token-restoration
  - audit
  - streaming
requires:
  - Phase 19-02: Vector connector interface
  - Phase 2: Detection Engine + Tokenization Engine
  - Phase 5: Audit Logger
provides:
  - rag/detection (retrieval-time re-detection)
  - rag/restoration (RAGRestorationService + TailBuffer for streaming)
affects:
  - None
tech-stack:
  added:
    - Python 3.12+, re (regex for TailBuffer), dataclasses
  patterns:
    - Re-detection at retrieval time for newly exposed content
    - TailBuffer pattern for split-token handling in SSE streams
    - Metadata-only audit events for filtered chunks
key-files:
  created:
    - src/anonreq/rag/detection.py
    - src/anonreq/rag/restoration.py
  modified:
    - tests/rag/test_rag_retrieval.py (fixed test data bug)
    - src/anonreq/rag/__init__.py (exports updated in 19-02)
decisions:
  - "retrieval_time_detect returns list of DetectionResult objects matching Phase 2 interface"
  - "TailBuffer handles boundary tokens split across SSE chunks with up to 200 byte lookahead"
  - "RAGRestorationService restores [TYPE_N] tokens in final response, supporting streaming and non-streaming"
  - "Filtered chunk audit events emit chunk_id, rule_id, reason — never the chunk content"
metrics:
  duration: "~10 min"
  completed_date: "2026-07-05"
  test_count: 32 (includes new RAG retrieval fix)
  files_created: 2
  total_lines_added: 244
status: complete
---

# Phase 19 — Plan 03 Summary

## Objective

Build Secure RAG retrieval pipeline — retrieval-time PII re-detection, token restoration in LLM responses with streaming support, and filtered chunk audit events.

## Files Created

### Source files (`src/anonreq/rag/`)

| File | Lines | Description | Exports |
|------|-------|-------------|---------|
| `detection.py` | 78 | `retrieval_time_detect` function — runs Detection Engine on retrieved content for re-detection. Returns list of `DetectionResult` with entity_type, start, end, score. Handles empty text, no entities, and multiple entity types. | `retrieval_time_detect` |
| `restoration.py` | 163 | `RAGRestorationService` class — restores `[TYPE_N]` tokens in LLM responses. `TailBuffer` helper class for split-token detection in SSE streams with configurable max_lookahead (default 200 bytes). Supports streaming (`restore_streaming`) and non-streaming (`restore_response`). | `RAGRestorationService`, `TailBuffer` |

### Modified files

| File | Change |
|------|--------|
| `tests/rag/test_rag_retrieval.py` | Fixed `test_rule_004_allows_cross_bu_internal` — added `"eng_app"` to hr_user's applications list to allow RULE-004 evaluation |

## Commit History

| Commit | Type | Description |
|--------|------|-------------|
| `d1caaa8` | `feat` | retrieval-time detection, RAG restoration service, and test fix |

## Test Results

All 32 RAG retrieval tests pass:

```
tests/rag/test_rag_retrieval.py::TestRetrievalPolicyEngine::test_policy_result_has_rule_details PASSED
tests/rag/test_rag_retrieval.py::TestRetrievalPolicyEngine::test_chunk_filtering_by_engine PASSED
tests/rag/test_rag_retrieval.py::TestRetrievalPolicyEngine::test_yaml_config_loading PASSED
tests/rag/test_rag_retrieval.py::TestRetrievalPolicyEngine::test_disabled_rule_not_evaluated PASSED
tests/rag/test_rag_retrieval.py::TestRetrievalService::test_retrieval_service_creation PASSED
tests/rag/test_rag_retrieval.py::TestRetrievalService::test_process_retrieved_chunks PASSED
tests/rag/test_rag_retrieval.py::TestRetrievalService::test_audit_events_for_denied_chunks PASSED
tests/rag/test_rag_retrieval.py::TestRetrievalService::test_no_audit_events_for_allowed_chunks PASSED
tests/rag/test_rag_retrieval.py::TestRetrievalService::test_audit_events_metadata_only PASSED
tests/rag/test_rag_ingest.py:: ... (19 chunker + ingest tests) PASSED
```

## Auto-fixed Issues

### [Rule 1 - Bug] Fixed test data bug in test_rule_004_allows_cross_bu_internal

- **Found during:** Test execution
- **Issue:** `hr_user.applications` did not include `"eng_app"`, causing RULE-003 (cross_app_isolation) to block the chunk before RULE-004 (business_unit_isolation) could evaluate — making the test assertion `not denied` fail
- **Fix:** Added `"eng_app"` to `hr_user`'s applications list in test setup
- **Files modified:** `tests/rag/test_rag_retrieval.py`
- **Commit:** `d1caaa8`

## Threat Surface Scan

No new threat surface. Detection and restoration are consumers of existing interfaces within the gateway's trust boundary.

## Self-Check: PASSED

- ✅ 2 source files created and verified on disk
- ✅ 1 test file fix verified
- ✅ 1 commit verified in git log
- ✅ All 32 RAG retrieval tests pass
