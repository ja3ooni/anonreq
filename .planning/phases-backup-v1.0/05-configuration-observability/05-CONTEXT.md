# Phase 5: Configuration & Observability - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Operational monitoring with Prometheus metrics, P95 latency validation under load (k6), post-restoration token verification scan (warn-only), and custom detection rules hot-reload via Admin API.

Two plans: 05-01 (Prometheus metrics + k6 load test), 05-02 (Post-restoration token verification scan + custom rules Admin API).

Metrics are low-cardinality only. Post-restoration verification is observability, not enforcement (warn-only). Custom rules hot-reload via Admin API with atomic swap — invalid config never replaces active config.
</domain>

<decisions>
## Implementation Decisions

### Architectural Guardrails
- **AG-15:** Metrics PII-Free — no PII, request content, or entity values in metric labels or metric values
- **AG-16:** Last Known Good Config — invalid config never replaces the active configuration
- **AG-17:** Verification Is Observability — post-restoration token verification is monitoring, not enforcement. Warn-only in MVP.
- **AG-18:** Observability Survives Fail-Secure — metrics and audit logging continue to function during fail-secure events. Fail-secure is observable.

### Prometheus Metrics Design
- **D-138:** Low-cardinality metric labels only. Avoid labels that vary per-request (tenant_id, request_id, session_id).
- **D-139:** Required metrics:
  - `anonreq_requests_total` — counter, labels: [endpoint, status_code, provider, classification]
  - `anonreq_detection_latency_ms` — histogram, buckets: [5, 10, 25, 50, 100, 250, 500, 1000]
  - `anonreq_entities_detected_total` — counter, labels: [entity_type, locale]
  - `anonreq_unrestored_tokens_total` — counter, labels: [endpoint]
  - `anonreq_fail_secure_events_total` — counter, labels: [failure_type]
  - `anonreq_audit_failures_total` — counter
  - `anonreq_processing_overhead_ms` — histogram, same buckets as detection_latency
  - `anonreq_active_config_version` — gauge (informational)
- **D-140:** Unrestored tokens counted as a per-response counter, not a gauge. Streaming: accumulated over the stream session.
- **D-141:** Metrics endpoint at `GET /metrics` (standard Prometheus format via `prometheus_client`).
- **D-142:** Default Presidio model for load testing: `en_core_web_sm` (small — fastest inference, adequate for latency benchmarks).

### Post-Restoration Token Verification
- **D-143:** Warn-only in MVP — scan completed response body for residual `\[[A-Z]+_\d+\]` patterns, increment `anonreq_unrestored_tokens_total` counter, log warning with count. Never block or retry the response.
- **D-144:** Non-streaming: scan after full RestorationStage completes, before response is sent.
- **D-145:** Streaming: scan on full assembled text after stream FINISH, before final restoration step. Warn-logged, never blocks emission.
- **D-146:** No configurable threshold in MVP — any residual token increments counter and logs. Future: configurable alert threshold.

### Custom Detection Rules Hot-Reload
- **D-147:** Admin API endpoint: `POST /v1/admin/config/rules` — accepts YAML with custom recognizer patterns and exclusion list entries.
- **D-148:** Validation flow: parse → validate schema → test against sample text patterns → if all pass → atomically swap active config. Atomic swap via pointer exchange on the recognizer registry.
- **D-149:** Invalid config never replaces active config (AG-16). Return HTTP 422 with structured validation errors (line number, field, issue).
- **D-150:** `GET /v1/config/rules` returns current active custom recognizers with metadata (id, entity_type, pattern_count, enabled, version).
- **D-151:** Admin API requires authentication via `ANONREQ_ADMIN_API_KEY` env var (separate from `ANONREQ_API_KEY`). If unset → admin endpoints return 401.

### Hot-Reload Scope Boundaries
- **D-152:** Hot-reloadable (DET-06 scope): custom recognizer patterns, confidence thresholds, exclusion list entries.
- **D-153:** Restart-required (never hot-reload): compliance presets, locale bundles, model aliases, provider configs, pipeline stage configuration, classification rules.
- **D-154:** Hot-reload is stateful and versioned — each successful reload bumps internal config version gauge (`anonreq_active_config_version`). No rollback variant in MVP (reload previous valid config to undo).

### Load Testing Approach
- **D-155:** k6 for load testing (JavaScript scripting, Prometheus metrics output, CI-friendly).
- **D-156:** Measure gateway overhead (total latency minus provider latency), not total end-to-end latency. Overhead = time from request receipt to provider call dispatch.
- **D-157:** Target P95 ≤ 100ms overhead at 50 concurrent users, 1,000-word prompts, 60s sustained. Default Presidio model: `en_core_web_sm`.
- **D-158:** Load test scenarios: non-streaming only in MVP (streaming load test deferred — streaming adds TailBuffer FSM overhead that needs separate characterization).
- **D-159:** Load test result logged as build artifact — not a CI gate in MVP.

### Metrics Integration with Audit Log
- **D-160:** Metrics counters are independent of audit log entries — not one-to-one. Audit log entries are a separate concern (structured JSON to stdout).
- **D-161:** Audit log gains optional `overhead_ms` field populated at response time for processing overhead visibility.

### From Prior Phases (carried forward)
- D-01 to D-53 from Phases 1 and 2 apply fully
- D-54 to D-109 from Phase 3 apply fully
- D-110 to D-137 from Phase 4 apply fully (locale bundles, compliance presets)
- AG-01 to AG-14 from Phases 3 and 4 apply fully
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — METR-01 to METR-03, PIPE-06, DET-06
- `.planning/ROADMAP.md` § Phase 5 — Success criteria, 2 plans (05-01, 05-02)

### Prior Phase Decisions
- `.planning/phases/01-foundation-fail-secure-auth/01-CONTEXT.md` — D-01 to D-21
- `.planning/phases/02-core-pipeline-classification-non-streaming/02-CONTEXT.md` — D-22 to D-53
- `.planning/phases/03-sse-streaming-multi-provider/03-CONTEXT.md` — D-54 to D-109, AG-01 to AG-12
- `.planning/phases/04-multi-locale-detection-compliance-presets/04-CONTEXT.md` — D-110 to D-137, AG-13, AG-14

### Project Decisions
- `.planning/PROJECT.md` — Python 3.12 + FastAPI, Presidio sidecar, Valkey, Docker Compose, Apache 2.0, fail-secure mandate
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 1: Config (Pydantic Settings + YAML), structured logging, error handling, auth middleware, Docker scaffold
- Phase 2: Pipeline orchestration (ProcessingContext), TextExtractor, DetectionProvider, recognizer registry, Valkey cache manager, ForwardingGuard
- Phase 3: ProviderAdapter interface, model alias routing, StreamEvent model, TailBuffer FSM, SSE restoration
- Phase 4: LocaleRegistry, RecognizerMerger, CompliancePresetEngine, ChecksumValidator

### Established Patterns
- YAML-based config for business/policy logic (D-07, D-22, D-36) — custom rules follow the same schema
- ProcessingContext-based stage pipeline — post-restoration scan fits as optional post-processing stage
- Atomic pointer swap for hot-reload — same pattern used by ProviderRegistry startup

### Integration Points
- Metrics: FastAPI middleware for request counting and latency collection
- Metrics: RestorationStage emission point for unrestored token counter
- Custom rules: DetectionProvider recognizer registry — hot-reload swaps the recognizer set
- Admin API authentication: separate `ANONREQ_ADMIN_API_KEY` env var, middleware
</code_context>

<specifics>
## Specific Ideas

- Low-cardinality metric labels only — no request_id, tenant_id, session_id labels
- `anonreq_processing_overhead_ms` measured at ForwardingGuard (pre-provider) vs restoration-complete
- Hot-reload validation: parse YAML → validate against recognizer schema → test pattern against sample text → atomic swap pointer
- `GET /v1/config/rules` returns: id, entity_type, pattern_count, enabled, version, created_at
- k6 script in `tests/load/benchmark.js` — configurable concurrency, prompt size, duration
- Admin API key: `ANONREQ_ADMIN_API_KEY` — separate from gateway API key
</specifics>

<deferred>
## Deferred Ideas

- Streaming load test — Phase 6+ (TailBuffer FSM overhead needs separate characterization)
- CI gate for load test thresholds — Phase 7+ (DevEx automation)
- Configurable alert threshold for unrestored tokens — Phase 14+ (governance)
- Hot-reload for compliance presets, locale bundles, aliases — Phase 8+ (enterprise)
- Hot-reload rollback variant — Phase 6+ (operational safety)
- Metrics dashboards (Grafana) — Phase 7+ (DevEx)
- SLO breach alerting webhook — Phase 11+ (Observability)
</deferred>

---

*Phase: 5-Configuration & Observability*
*Context gathered: 2026-06-20*
