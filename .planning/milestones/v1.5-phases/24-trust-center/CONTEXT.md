# Phase 24 — Trust Center: Context

## Phase Scope

Public-facing compliance evidence portal: `/v1/trust/status`, `/v1/trust/compliance`,
`/v1/trust/metrics`, `/v1/trust/security`. Config-gated (YAML toggle), rate-limited,
metadata-only. No authentication required.

## Decisions

### D1. Package Structure
**Decision:** `src/anonreq/trust_center/` with `__init__.py`, `router.py`, `schemas.py`, `service.py`, `config.py`.
**Rationale:** Matches SPEC §2.1. New module, not extending existing routes.

### D2. Config Gating Mechanism
**Decision:** Trust Center router is registered unconditionally in `main.py` (no auth context).
A startup-validate-and-gate dependency checks `app.state.trust_center_enabled` (bool, from
`config/trust_center.yaml`). When disabled, all routes return 404.
**Rationale:** No existing pattern for conditional `include_router` at create_app time. The routes
are lightweight; gating at runtime via a `Depends()` check is simpler and matches the SPEC
requirement that disabled returns 404.

### D3. Config File Loading
**Decision:** `TrustCenterSettings` (pydantic-settings subclass) loaded from
`config/trust_center.yaml` at app startup. `enabled: bool` field (default `false`). Written to
`app.state.trust_center_settings`.
**Rationale:** Follows existing YAML config pattern (policy.yaml, slo.yaml). Pydantic validation
for type safety. Single file, not env vars.

### D4. SLO Integration
**Decision:** Use existing `app.state.slo_engine.get_all_compliance(tenant_id)` pattern.
Trust Center calls `get_all_compliance("default")` (single-tenant aggregate). Compute summary:
total SLOs, compliant count, overall compliance percentage, last breach timestamp.
**Rationale:** AnonReq is single-tenant in v1.5. `tenant_id="default"` is the existing convention.
Returns aggregate metadata only — no raw SLO data.

### D5. Compliance Registry Integration
**Decision:** Use `app.state.preset_engine.list_presets()` to list supported frameworks.
Transform `PresetEngine.list_presets()` output (dict of `CompliancePreset` objects) into public
metadata: framework name, description, jurisdictions, entity type coverage.
**Rationale:** `list_presets()` is already aggregate — no tenant data. We strip internal fields
(entity types, thresholds) per metadata-only constraint.

### D6. Metrics Endpoint
**Decision:** Return select aggregate counters from `prometheus_client.REGISTRY`:
- `anonreq_requests_total` (total requests)
- `anonreq_entities_detected_total` (total entities detected)
- `anonreq_fail_secure_events_total` (total fail-secure events)
- `anonreq_processing_overhead_ms` (histogram — mean, p50, p99)
- Gateway uptime (computed from `anonreq_startup_timestamp` or app start time)
**Rationale:** Aggregate metadata only. No per-tenant or per-session breakdowns.
Use `REGISTRY.get_sample_value()` or scrape and aggregate from registered metrics.

### D7. Security Posture Endpoint
**Decision:** Return static metadata from `config/trust_center.yaml`:
- `display_name`, `contact_email`, `logo_url`
- `feature_summary` (which features are enabled/available)
- Security contact info
- Compliance certifications (from YAML)
**Rationale:** SPEC §2.3 defines the schema. No live security state data needed for MVP.

### D8. Rate Limiting
**Decision:** Add `TrustCenterRateLimiter` dependency using `CacheManager` with key
`trust_rate:{ip}:{window}` — 60 requests per IP per minute. Returns 429 on limit exceeded.
**Rationale:** SPEC §2.2: 60 RPM per IP. The existing `UsageLimiter` is tenant-scoped and tied
to the policy engine. A dedicated IP-based limiter for public routes is simpler and avoids
coupling Trust Center to enterprise policy. Uses existing `CacheManager` for Redis-backed
rate counting. Sliding window with 60s TTL.

### D9. Auth/Public Access
**Decision:** Trust Center router registered without `Depends(auth_context)` — same pattern as
`pac_router` and `/metrics`. No API key required.
**Rationale:** SPEC §2.2: "no auth required." Public compliance information portal.

### D10. CORS
**Decision:** No CORS middleware in the app. Document that reverse proxy should handle CORS for
public Trust Center endpoints.
**Rationale:** Adding CORS middleware affects all routes globally. The gateway is designed for
internal network deployment where reverse proxy handles CORS. For Trust Center, the reverse
proxy (nginx, Cloudflare) can set CORS headers.

### D11. Fail-Closed
**Decision:** If SLO engine or PresetEngine is unavailable at request time, return 503.
Checked at the service layer — catch exceptions from `slo_engine.get_all_compliance()` and
`preset_engine.list_presets()`, log, return 503 with `{"error": "service_unavailable"}`.
**Rationale:** SPEC §2.4: fail-closed. Aggregate data dependency failure → 503.

### D12. Response Schemas
**Decision:** Pydantic models in `schemas.py`:
- `TrustStatus`: `slo_count`, `compliant_count`, `overall_percentage`, `last_breach`, `period`
- `TrustCompliance`: `frameworks` (list of `FrameworkInfo`)
- `TrustMetrics`: `total_requests`, `total_entities`, `fail_secure_count`, `latency_p50_ms`,
  `latency_p99_ms`, `uptime_days`
- `TrustSecurity`: `display_name`, `contact_email`, `feature_summary`, `certifications`
**Rationale:** Standard Pydantic response models per FastAPI conventions.

### D13. Testing Approach
**Decision:** Unit tests for config parsing, schema validation, rate limiter, and fail-closed
behavior. Integration tests for full response format verification using `TestClient` with
mocked SLO engine and PresetEngine.
**Rationale:** SPEC §2.5. Use existing test patterns (pytest + TestClient + fakeredis).

## Gray Areas Resolved

| Gray Area | Resolution |
|---|---|
| Tenant scope for SLO | Single-tenant: `tenant_id="default"` |
| Rate limiting mechanism | IP-based with CacheManager (60 RPM) |
| Auth for public routes | No auth — same as /metrics and pac_router |
| Config gate mechanism | Runtime check in Depends(), not conditional import |
| CORS | Handled by reverse proxy, not in app |
| Metrics selection | 5 aggregate counters from REGISTRY |
| Config file format | YAML with pydantic-settings validation |
| Router registration | Always registered, enabled gate at request level |

## Dependencies

- **Depends on:** Phase 23 (for CI and code quality — no code dependency)
- **Depended by:** Phase 26 (licensing gates Trust Center routes)
- **Upstream artifacts:** `SLOEngine`, `PresetEngine`, `CacheManager`, `prometheus_client.REGISTRY`

## Risk Notes

- **Public exposure of metrics:** Even aggregate metrics can leak business intelligence
  (e.g., request volume trends). The rate limiter (60 RPM) limits scraping but does not prevent
  intentional data collection. Document this in Trust Center configuration guide.
- **Fail-closed → 503 storm:** If SLO engine is down, every Trust Center request returns 503.
  Consider short TTL caching of last-known-good aggregate data. For MVP, simple fail-closed is
  acceptable per SPEC.
- **No tenant isolation:** Current single-tenant design. If multi-tenant is added later, Trust
  Center must switch to cross-tenant aggregate (sum across all tenants).
