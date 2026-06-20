# Phase 6: Advanced Property-Based Tests - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete the generative Hypothesis test suite for edge cases not covered in Phases 2–5. This is the security proof phase — every security invariant must be demonstrated under fault injection, not merely unit tested.

No production code changes. Pure verification. All tests must pass before Phase 7 begins.
</domain>

<decisions>
## Implementation Decisions

### Architectural Guardrails
- **AG-19:** Security Invariants Must Be Proven Under Fault — Hypothesis must demonstrate, not just unit tests assert. Every failure mode is injected. Every invariant is statistically proven.
- **AG-20:** Metrics Are Part of the Contract — every fail-secure property test must verify metric counters are incremented correctly. Metrics cannot be trusted if untested.

### TEST-04: Fail-Secure Property Tests
- **D-162:** Inject all 5 failure modes: detection failure, Valkey/cache failure, ForwardingGuard failure, provider timeout, circuit breaker open.
- **D-163:** For each failure mode, verify:
  - `forwarded_bytes == 0` — mock spy on ProviderStage confirms zero calls
  - `cleanup_called == True` — SessionCleanup._cleaned flag observed
  - `fail_secure_counter_incremented == 1` — `anonreq_fail_secure_events_total` incremented
  - `audit_log_written == True` — fail-secure audit entry present
- **D-164:** Test both non-streaming and streaming paths for every failure mode.
- **D-165:** Also verify metric counters: `anonreq_fail_secure_events_total`, `anonreq_requests_total` (status=500), `anonreq_processing_overhead_ms` (recorded even on failure).
- **D-166:** Circuit breaker test: N successive failures → circuit opens, next request immediately fails (no Presidio call), counter incremented.
- **D-167:** Streaming path fail-secure: inject failure mid-stream → stream terminates with error, cleanup_session() called, metrics emitted, 0 forwarded bytes after failure point.

### TEST-06: No-PII-in-Logs Property Tests
- **D-168:** PII substring definition: any original entity value present in request payload or provider response. Examples: `john@company.com`, `John Smith`, `+49123456789`, `DE123456789` must never appear in any log sink.
- **D-169:** Log pathways tested: application logs (stdout), structured JSON logs, audit logs, exception logs (stderr), tracebacks, metrics labels, access logs (if any).
- **D-170:** Property: given `original_text` with `detected_entities`, when request succeeds or fails, then no log sink contains any entity value.
- **D-171:** Hypothesis generates synthetic PII across all entity types (EMAIL, PHONE, CREDIT_CARD, PERSON, NAME, IBAN, etc.) and all pipeline paths (non-streaming success, streaming success, fail-secure, timeout, block classification).
- **D-172:** Log output captured per-test via structured logging handler test fixture. Each fixture redirects to an in-memory buffer. Buffer scanned for entity substrings. False positives (matched entity-type prefix like "PERSON" in non-PII context) must be suppressed.

### TEST-08: Cross-Request Randomization Property Test
- **D-173:** Same entity value across different requests must produce different tokens. Example: Request A `john@corp.com` → `[EMAIL_7f3a]`, Request B `john@corp.com` → `[EMAIL_9c2d]`.
- **D-174:** Hypothesis test generates 1000+ session pairs with same entity values. Token format: `[TYPE_<random_suffix>]` where suffix derives from UUIDv7 or 128-bit cryptographically random seed.
- **D-175:** Verify collision rate: `P(two sessions produce same token for same value) ≤ 2⁻³²`. Probability bound chosen per birthday problem: with 1000 sessions and 2³² possible tokens, expected collisions ≈ 0.00012.
- **D-176:** Mechanism: session-scoped random seed (UUIDv7) → token index derived from `SHAKE_128(seed + entity_value + entity_type, 4 bytes)` → mapped to `[TYPE_{N}]` where N is a per-type counter offset by the random value.

### Streaming Disconnect Property Tests (Phase 6 Close)
- **D-177:** Close all disconnect tests in Phase 6. Phase 3 proved disconnect handling correctness; Phase 6 proves disconnect handling under adversarial conditions.
- **D-178:** TEST-07E: Disconnect during tokenization — client drops connection while TokenizationStage is writing to Valkey. Verify cleanup_session() executed, 0 orphaned mappings.
- **D-179:** TEST-07F: Disconnect during restoration — client drops while RestorationStage is replacing tokens in response. Verify partial restoration never emitted to client.
- **D-180:** TEST-07G: Disconnect during provider stream — client drops mid-stream while ProviderAdapter.stream_events() is yielding. Verify upstream HTTPX connection cancelled, no further processing.
- **D-181:** TEST-07H: Disconnect + provider timeout race — both disconnect signal and provider timeout fire near-simultaneously. Verify exactly one terminal state (first wins), cleanup_session() idempotent (called once).
- **D-182:** Invariant for all disconnect tests: cleanup executed exactly once, 0 orphaned mappings, 0 forwarded bytes after disconnect.

### Metrics Verification in Property Tests
- **D-183:** Every fail-secure property test verifies metric state. Test fixture exposes a metrics snapshot function (reads in-process Prometheus counter values before/after).
- **D-184:** Fail-secure tests verify: `anonreq_fail_secure_events_total` increased by 1 for the specific failure_type label, `anonreq_requests_total{status="500"}` increased by 1, `anonreq_forwarded_bytes_total` unchanged (if such a metric exists) or ProviderStage spy confirms 0 calls.

### Fail-Secure Audit Path Verification
- **D-185:** Every fail-secure property test verifies audit log entry: AUDT-04 format (timestamp, session_id, failure_type, http_status). Entry written before or at response time.
- **D-186:** Audit log fixture captures in-memory. Test asserts entry presence, correct failure_type, http_status matching the injected failure.

### Test Organization
- **D-187:** All property tests live in `tests/property/`. New files for Phase 6:
  - `tests/property/test_fail_secure.py` — TEST-04 + metrics/audit verification
  - `tests/property/test_no_pii_in_logs.py` — TEST-06
  - `tests/property/test_cross_request_randomization.py` — TEST-08
  - `tests/property/test_disconnect.py` — TEST-07E through TEST-07H (extends Phase 3 file if exists)
- **D-188:** Each test file targets one requirement. Hypothesis strategies shared via `tests/property/strategies.py`.

### Security Acceptance Gate
- **D-189:** Formal Security Acceptance Gate after all Phase 6 tests pass. Documented in `07-SECURITY-ACCEPTANCE.md`. Gates:
  - No PII leaks (TEST-06 pass)
  - No fail-open paths (TEST-04 pass all failure modes)
  - No orphaned mappings (TEST-07E–07H pass)
  - 100% cleanup coverage (all TEST-04 variants verify cleanup)
  - Cross-request token reuse forbidden (TEST-08 pass)
  - Disconnect tests 100% pass
  - Metrics validation pass
  - P95 latency within target
  - Streaming invariants pass

### From Prior Phases (carried forward)
- D-01 to D-53 from Phases 1 and 2 apply fully
- D-54 to D-109 from Phase 3 apply fully (including TEST-07A to TEST-07D, STREAM-07A to STREAM-07D)
- D-110 to D-137 from Phase 4 apply fully (locale bundles, checksum validation — TEST-05 builds on this)
- D-138 to D-161 from Phase 5 apply fully (metrics, verification — TEST-04 builds on this)
- AG-01 to AG-18 from Phases 3–5 apply fully
</decisions>

<canonical_refs>
## Canonical References

### Requirements
- `.planning/REQUIREMENTS.md` — TEST-04 to TEST-06, TEST-08
- `.planning/ROADMAP.md` § Phase 6 — Success criteria, 3 plans (06-01 to 06-03)

### Prior Phase Decisions
- `.planning/phases/01-foundation-fail-secure-auth/01-CONTEXT.md` — D-01 to D-21
- `.planning/phases/02-core-pipeline-classification-non-streaming/02-CONTEXT.md` — D-22 to D-53 (10 invariants)
- `.planning/phases/03-sse-streaming-multi-provider/03-CONTEXT.md` — D-54 to D-109, AG-01 to AG-12, TEST-07A–07D, STREAM-07A–07D
- `.planning/phases/04-multi-locale-detection-compliance-presets/04-CONTEXT.md` — D-110 to D-137, AG-13–14
- `.planning/phases/05-configuration-observability/05-CONTEXT.md` — D-138 to D-161, AG-15–18

### Project Decisions
- `.planning/PROJECT.md` — Python 3.12 + FastAPI, Presidio sidecar, Valkey, Docker Compose, Apache 2.0, fail-secure mandate
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 1: Config, logging, error handling, auth, Docker scaffold
- Phase 2: Pipeline orchestration (ProcessingContext), TextExtractor, DetectionProvider, TokenizationEngine, Valkey cache, ForwardingGuard
- Phase 3: ProviderAdapter interface, TailBuffer FSM, StreamEvent model, SSEEmitter, SessionCleanup
- Phase 4: LocaleRegistry, ChecksumValidator framework, CompliancePresetEngine
- Phase 5: Prometheus metrics, ResponseScanner, AtomicConfigRegistry, admin API

### Established Patterns
- Hypothesis strategies in `tests/property/strategies.py` for shared generators
- ProcessingContext captures full pipeline state for post-hoc verification
- Metrics snapshot before/after test for counter verification
- Structured log capture via handler fixture

### Integration Points
- ProviderStage spy: intercept `execute()` and `stream_events()` calls
- SessionCleanup._cleaned flag: observable for cleanup verification
- Metrics registry: snapshot `anonreq_fail_secure_events_total._value._value` per test
- Audit log fixture: capture AUDT-04 entries
</code_context>

<specifics>
## Specific Ideas

- Fail-secure test fixture: `inject_failure(failure_mode, pipeline_path)` — configure mock to raise on call
- Metrics snapshot: `{name: registry.get_sample_value(name) for name in METRIC_NAMES}` before and after
- Audit capture: replace stdout handler with `io.StringIO` buffer, parse JSON lines
- No-PII test: generate synthetic PII via Hypothesis `emails()`, `credit_card_numbers()`, `names()` strategies
- Cross-request test: create N session contexts, run same text through each, verify all tokens differ
- Circuit breaker test: configure low threshold (2 failures), fire 2 failures, 3rd request should fail-fast
</specifics>

<deferred>
## Deferred Ideas

- Performance regression test under Hypothesis — Phase 7+ (DevEx)
- Fuzz testing beyond property tests — Phase 8+ (enterprise)
- Differential testing (compare detection output across Presidio versions) — Phase 11+
- Adversarial PII reconstruction attempt from tokens — Phase 14+ (governance)
</deferred>

---

*Phase: 6-Advanced Property-Based Tests*
*Context gathered: 2026-06-20*
