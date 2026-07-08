# Phase 5 Discussion Log

**Gathered:** 2026-06-20

## Areas Discussed

### Prometheus Metrics Design
- **Decision:** Low-cardinality metrics only. No per-request labels (tenant_id, request_id, session_id).
- **Required metrics (8 total):** requests_total, detection_latency_ms, entities_detected_total, unrestored_tokens_total, fail_secure_events_total, audit_failures_total, processing_overhead_ms, active_config_version.

### Post-Restoration Token Verification
- **Decision:** Warn-only in MVP. Scan for residual `\[[A-Z]+_\d+\]`, increment counter, log warning. Never block or retry.
- **Non-streaming:** scan after RestorationStage, before response send.
- **Streaming:** scan on full assembled text after stream FINISH.

### Custom Detection Rules Hot-Reload
- **Decision:** Admin API endpoint `POST /v1/admin/config/rules`.
- **Validation flow:** parse → validate schema → regex compile test → atomic swap pointer.
- **Invalid config:** never replaces active config (AG-16). Return HTTP 422 with structured errors.
- **Separate admin API key:** `ANONREQ_ADMIN_API_KEY` env var.

### Load Testing
- **Decision:** k6 for load testing. Measure gateway overhead (not provider latency).
- **Target:** P95 ≤ 100ms at 50 concurrent, 1000-word prompts, 60s sustained.
- **Non-streaming only** in MVP — streaming deferred for separate characterization.

### Hot-Reload Scope Boundaries
- **Hot-reloadable:** custom recognizer patterns, confidence thresholds, exclusion lists.
- **Restart-required:** compliance presets, locale bundles, model aliases, provider configs, pipeline stage config, classification rules.

## Architectural Guardrails Added

- **AG-15:** Metrics PII-Free
- **AG-16:** Last Known Good Config
- **AG-17:** Verification Is Observability
- **AG-18:** Observability Survives Fail-Secure

## Documents Generated

- `05-CONTEXT.md` — All decisions (D-138 through D-161)
- `05-ARCHITECTURE.md` — Architecture document with pipeline instrumentation, metrics namespace, admin API
- `05-TASK-BREAKDOWN.md` — 2 plans, file manifest
- `05-TEST-PLAN.md` — 3-tier test strategy with 7 invariants

## Deferred Ideas

- Streaming load test — Phase 6+
- CI gate for load test thresholds — Phase 7+
- Configurable alert threshold for unrestored tokens — Phase 14+
- Hot-reload for presets, bundles, aliases — Phase 8+
- Hot-reload rollback variant — Phase 6+
- Metrics dashboards (Grafana) — Phase 7+
- SLO breach alerting webhook — Phase 11+
