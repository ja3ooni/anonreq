---
phase: 21-endpoint-visibility-sovereign-control
plan: TEST
subsystem: test-coverage
tags: [dispatcher, tls, voice, spectral-analysis, phase-21]
requires:
  - phase: 21
    plan: 01
    provides: transparent proxy and deployment topology primitives
  - phase: 21
    plan: 03
    provides: voice pipeline and audio sanitization
  - phase: 21
    plan: 04
    provides: agent tool governance and result sanitization
  - phase: 21
    plan: 05
    provides: content-type dispatcher, TLS interception
  - phase: 21
    plan: 06
    provides: property-based tests for voice, agent, firewall
provides:
  - Content-Type Dispatcher backward compatibility tests (13 tests covering 6 content-type categories)
  - TLS downgrade prevention security tests (6 tests: version, ciphers, pinning, hostname)
  - Voice audio spectral analysis property-based tests (2 tests: mute cross-correlation, beep FFT)
affects: [phase-21, tests, dispatcher, tls, voice]
tech-stack:
  added: []
  patterns: [hypothesis-spectral-analysis, dispatcher-compat-regression, tls-downgrade-assertions]
key-files:
  created:
    - tests/test_dispatcher_backward_compat.py
    - tests/test_tls_security.py
  modified:
    - tests/test_voice_pbt.py
key-decisions:
  - "Content-Type Dispatcher backward compat tests (13) cover JSON, multipart, text, voice_stream (pcm/wav/opus), agent_tool_call/result, MCP message, and unknown/empty type handling."
  - "TLS security tests (6) cover TLS 1.3 version enforcement, AEAD-only cipher suites, certificate pinning detection, and upstream context hostname verification directly against the tls_interceptor and tls modules."
  - "Audio spectral PBTs (2) verify muted audio has zero cross-correlation with original and beeped audio has FFT power spectrum differing from original — supplementing existing sample-level integrity tests."
  - "Categories A (transparent proxy unit tests) and E (AI firewall) from 21-TEST-PLAN.md were already fully covered by prior plans — no additional tests needed."
requirements-completed:
  - TEST-01
  - TEST-02
  - TEST-03
duration: ~30 min
completed: 2026-07-06
status: complete
---

# Phase 21 Plan TEST: Missing Test Coverage Summary

**21 new tests added covering Content-Type Dispatcher backward compatibility, TLS downgrade prevention, and audio spectral analysis — closing the test gaps identified in the 21-TEST-PLAN.md specification**

## Performance

- **Tasks:** 1
- **Files created/modified:** 3
- **New tests:** 21 passed
- **Full Phase 21 test suite:** 520+ passed (0 regressions)

## Accomplishments

- **Content-Type Dispatcher backward compat (B):** 13 tests verifying that existing content types (application/json, multipart/form-data, text/plain) continue to route correctly through the dispatcher's integration with LocalRouter, while new Phase 21 types (voice_stream via audio/*, agent_tool_call, agent_tool_result, MCP message) dispatch to their correct ContentType enum values. Also covers unknown content types, empty/invalid Accept headers, and raw-type metadata recording.

- **TLS downgrade prevention (C.5):** 6 security-focused tests verifying:
  - MIN_TLS_VERSION is set to TLS 1.3 in `tls_interceptor.py`
  - Outbound TLS contexts from `src/anonreq/proxy/tls.py` use secure protocol versions
  - Upstream context matches the configured minimum TLS version
  - AEAD-only secure cipher suites reject weak ciphers (CBC, RC4, DES, etc.)
  - Certificate pinning detection flags short RSA keys (< 2048 bits)
  - `check_hostname` is enabled on upstream TLS contexts

- **Audio spectral analysis (D.2):** 2 Hypothesis property-based tests supplementing the existing sample-level integrity tests:
  - `test_muted_audio_contains_no_original_data_spectral`: verifies that muted audio frames have zero cross-correlation with the original audio segment using FFT-based spectral analysis
  - `test_beeped_audio_spectral_content_differs_from_original`: verifies that beep-replaced audio segments have a substantially different FFT power spectrum from the original, confirming speech data is masked

- **Verified pre-existing coverage:** Categories A (transparent proxy: dynamic TLS certs, enterprise CA loading, cert pinning detection, non-AI classification, protocol header preservation), E (AI Firewall: jailbreak DB matching, injection scoring, override detection, monotonicity, fail-closed behavior), voice pipeline unit tests (format detection, streaming, muting, beeping, STT parsing), and agent governance tests (tool_calls, tool_use, MCP, schema validation) were all already covered by prior plan test suites — no new tests needed for those categories.

## Files Created/Modified

- `tests/test_dispatcher_backward_compat.py` (166 lines) — Content-Type Dispatcher backward compatibility and new content-type routing
- `tests/test_tls_security.py` (91 lines) — TLS downgrade prevention, certificate pinning detection, cipher suite verification
- `tests/test_voice_pbt.py` (modified) — Added 2 spectral analysis property-based tests, plus fixes for `nan` guard and `large_base_example` health check

## Deviations from Plan

### Pre-existing Coverage (No Action Needed)

**1. [Rule 2 Note] Category A (Transparent Proxy) tests already exist**
- **Category:** A.1–A.5 (Dynamic TLS cert generation, Enterprise CA loading, Cert pinning detection, Non-AI traffic classification, Protocol header preservation)
- **Status:** Full pre-existing coverage in `tests/test_proxy_tls.py`, `tests/test_proxy_modes.py`, `tests/test_proxy_topology.py`, `tests/test_proxy_integration.py`, `tests/test_ca_manager.py`, `tests/test_mitm.py`, `tests/test_tls.py`, `tests/test_hostname_matcher.py`, `tests/test_pac.py` (130+ tests)
- **Decision:** No new tests needed

**2. [Rule 2 Note] Category C (TLS Interception) components already tested**
- **Sub-category:** C.1–C.4 (TLS cert generation, CA loading, cert pinning detection, non-AI classification)
- **Status:** Pre-existing coverage in `tests/test_proxy_tls.py` and related proxy test files
- **Decision:** No new tests needed; only C.5 (High-Volume Anomaly Detection / TLS downgrade prevention) required new tests

**3. [Rule 2 Note] Category E (AI Firewall) fully covered**
- **Sub-categories:** E.1 (Jailbreak matching) → `tests/test_firewall_jailbreak.py`, E.2 (Injection scoring) → `tests/test_firewall_injection.py`, E.3 (Override detection) → `tests/test_firewall_classifier.py`, E.4 (Pipeline integration) → `tests/test_firewall_pipeline.py`, E.5 (Fail-closed) → `tests/test_fail_closed_integration.py`
- **Status:** 281+ tests pre-existing in `tests/firewall/` and `tests/test_firewall_*.py`
- **Decision:** No new tests needed

### Auto-fixed Issues

**1. [Rule 1 - Bug] Spectral correlation test failed due to zero-variance NaN in corrcoef**
- **Found during:** Test creation — `test_beeped_audio_spectral_content_differs_from_original`
- **Issue:** When input audio had near-zero variance (very quiet region), `np.corrcoef` returned `nan` causing assertion failure against `1.0`
- **Fix:** Added guard `if np.std(orig_fft) > 1e-10 and np.std(sanit_fft) > 1e-10` before computing correlation. Added `suppress_health_check=[HealthCheck.large_base_example]` to handle the large minimum example size
- **Files modified:** `tests/test_voice_pbt.py`

**2. [Rule 1 - Bug] Dispatcher backward compat tests failed on synthetic content-type behavior**
- **Found during:** Initial test creation — `test_dispatcher_handles_json_for_chat_completion_rag` and `test_dispatcher_handles_multipart_for_multimodal`
- **Issue:** Test mocks returned raw `AsyncMock()` instances instead of `UnifiedDetectionResult` objects with the proper `content_type` attribute. The dispatcher's `_detect_content_type` method accesses `result.content_type` on the analyzer return value.
- **Fix:** Configured fixture mocks to return proper `UnifiedDetectionResult` instances with `ContentType.APPLICATION_JSON` and `ContentType.MULTIPART_FORM_DATA` respectively, plus `analyzer_metadata` containing the raw MIME type
- **Files modified:** `tests/test_dispatcher_backward_compat.py`

## Verification

- `pytest tests/test_dispatcher_backward_compat.py tests/test_tls_security.py -v` → 20 passed
- `pytest tests/test_voice_pbt.py -v` → 6 passed (4 existing + 2 new spectral)
- `pytest tests/test_proxy_integration.py tests/test_proxy_modes.py tests/test_proxy_topology.py tests/test_proxy_tls.py tests/test_mitm.py tests/test_ca_manager.py tests/test_tls.py tests/test_hostname_matcher.py tests/test_pac.py tests/test_dispatcher_backward_compat.py tests/test_tls_security.py -q` → 131 passed
- `pytest tests/test_voice_pipeline.py tests/test_voice_sanitizer.py tests/test_voice_stt.py tests/test_voice_connectors.py tests/test_voice_detector.py tests/test_voice_transcript.py tests/test_voice_pbt.py -q` → 44 passed
- `pytest tests/test_agent_tool_inspector.py tests/test_agent_result_sanitizer.py tests/test_agent_mcp.py tests/test_mcp_inspector.py tests/test_mcp_parser.py tests/test_tool_inspector.py tests/test_tool_policy_parser.py tests/test_agent_pbt.py -q` → 97 passed
- `pytest tests/test_firewall_classifier.py tests/test_firewall_injection.py tests/test_firewall_jailbreak.py tests/test_firewall_pipeline.py tests/test_firewall_pbt.py tests/firewall/ tests/test_fail_closed_integration.py tests/test_metrics_registration.py tests/endpoint/ -q` → 281 passed

## Task Commits

- `3f3c157`: test(21-TEST): add missing test coverage for Content-Type dispatcher, TLS security, and audio spectral analysis

## Known Stubs

None — all tests use real dispatcher/TLS/voice modules with properly configured mocks and fakes.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/21-endpoint-visibility-sovereign-control/21-TEST-SUMMARY.md`.
- `tests/test_dispatcher_backward_compat.py` exists — 166 lines, 13 tests passing.
- `tests/test_tls_security.py` exists — 91 lines, 6 tests passing.
- `tests/test_voice_pbt.py` modified — 217 lines, 6 tests (4 existing + 2 new) passing.
- All 520+ Phase 21 tests pass with 0 regressions.
- Git commit `3f3c157` verified.
