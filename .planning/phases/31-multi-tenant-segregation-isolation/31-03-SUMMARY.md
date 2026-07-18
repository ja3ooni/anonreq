# 31-03 Summary — Tenant-Scoped Metrics and Logging

**Plan:** 31-03 | **Wave:** 2 | **Status:** COMPLETE
**Commits:** `9be506d` (metrics + logging)

## What Was Delivered

### Bounded Cardinality Helper (D-12)
- `src/anonreq/monitoring/metrics.py` — Added `_tenant_label(tenant_id) -> str` function that returns the original tenant_id if within `MAX_TENANTS` limit, or `"_overflow"` if limit exceeded. Added `set_max_tenants()` for runtime configuration.

### Tenant-Labeled Prometheus Metrics (D-11)
- `requests_total` Counter now carries `tenant_id` as first labelname (BREAKING: new label for scrapers)
- `fail_secure_events` Counter now carries `tenant_id` label
- Histograms (`detection_latency`, `processing_overhead`) and Gauges (`active_config_version`) unchanged — aggregate system state doesn't need tenant partitioning

### MetricsMiddleware Update
- `src/anonreq/monitoring/middleware.py` — `dispatch()` now reads `request.state.tenant_id` via `getattr` (default `"_unknown"`) and passes through `_tenant_label()` before labeling `requests_total`

### Settings and Startup Wiring
- `src/anonreq/config/__init__.py` — Added `METRICS_MAX_TENANTS: int = 100` setting with `ANONREQ_METRICS_MAX_TENANTS` env var
- `src/anonreq/main.py` — Calls `set_max_tenants(settings.METRICS_MAX_TENANTS)` during lifespan startup

### structlog Tenant Contextvars (D-10) — Already Implemented
TenantContextMiddleware (from 31-01) already calls `bind_contextvars(tenant_id=...)`. The `merge_contextvars` processor is in `setup_logging()`. `tenant_id` is in the logging `ALLOWLIST`.

### Tests
- `tests/unit/test_tenant_metrics.py` — `_tenant_label` cardinality enforcement, overflow behavior, Counter label contract, MetricsMiddleware tenant reading
- `tests/unit/test_tenant_logging.py` — structlog contextvars bind/unbind, no leakage, merge_contextvars integration, allowlist verification

## Verification
- All new files pass Python syntax check
- `_tenant_label` returns `"_overflow"` after 100 unique tenants (default)
- `_tenant_label` preserves existing tenant labels after overflow
- structlog `tenant_id` field passes allowlist processor
- No cross-request tenant_id leakage
