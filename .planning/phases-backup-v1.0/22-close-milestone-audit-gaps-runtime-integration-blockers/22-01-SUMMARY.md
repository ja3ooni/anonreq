# 22-01: Runtime Integration — Content-Type Middleware, Discovery Router, SOC Fan-Out

## What was implemented

### 1. `src/anonreq/main.py` — wired three Phase 22 components:

**a) ContentTypeMiddleware** (ASGI-level)
- Created `ContentTypeDispatcher` at `create_app()` scope (before middleware registration) using `JSONAnalyzer` + `MultipartAnalyzer`
- Registered `app.add_middleware(ContentTypeMiddleware, dispatcher=...)` between `ClassificationResponseMiddleware` and the `/metrics` endpoint
- Stored `app.state.content_type_dispatcher` in lifespan for runtime access

**b) Discovery Inventory Admin Router**
- Added `from anonreq.discovery.admin_router import router as discovery_admin_router`
- Added `app.include_router(discovery_admin_router, dependencies=[Depends(auth_context)])` in the route registration section
- Initialized `app.state.inventory_service = AssetInventory()` in lifespan after detection setup

**c) SOC Normalizer → SinkRouter Fan-Out**
- After SIEM sinks init, registers `sink_router.fan_out` as a named callback on `soc_normalizer`
- Guarded with `hasattr` checks for graceful degradation

### 2. `src/anonreq/discovery/inventory.py` — bugfix
- Made `export_csv()` accept optional `filters` parameter and async signature to match the admin_router call site (`await inventory.export_csv(filters=filters)`)

### 3. `tests/integration/test_app_runtime_wiring.py` — 6 tests
- `test_unsupported_content_type_returns_415`: `application/xml` → 415
- `test_unsupported_content_type_body_has_error`: 415 body contains error envelope
- `test_supported_json_content_type_passes`: JSON content type not rejected
- `test_inventory_route_responds_with_seeded_data`: Route registered, returns 200 with records
- `test_inventory_json_with_records`: Full JSON response with correct records
- `test_inventory_csv_format`: CSV response with `text/csv` content type
- `test_inventory_no_pii_in_response`: No PII leakage in inventory responses

### 4. `tests/test_soc_runtime_wiring.py` — 5 tests
- `test_normalizer_has_sink_router_registered`: Callback registered by name
- `test_raw_event_delivered_to_fake_sink`: End-to-end delivery via normalizer → sink_router → fake sink
- `test_multiple_events_sequentially`: Two events processed in sequence
- `test_normalized_event_no_raw_content_fields`: Metadata-only fields, no `content`/`prompt`/`response`/etc.
- `test_event_with_content_fields_is_dropped`: Events with `content` key are dropped before fan-out

## Verification results

```
uv run pytest tests/integration/test_app_runtime_wiring.py tests/test_soc_runtime_wiring.py -q
```
**12 passed, 1 warning** (warning is pre-existing deprecation in admin_router.py `regex` → `pattern`)

## Key design decisions

- **ContentTypeDispatcher created at module scope** (not inside lifespan) so it's available when `add_middleware` is called, which happens before lifespan runs. The same instance is also stored on `app.state` for runtime access.
- **SOC normalizer fan-out is guarded** with `hasattr` checks since the SIEM sinks block is already wrapped in try/except.
- **Inventory service is initialized unconditionally** (not wrapped in try/except) — lightweight in-memory service with no network dependencies.
- **Discovery admin router uses `auth_context`** already on the APIRouter definition; the `include_router` also adds `Depends(auth_context)` for consistency with other admin routers (FastAPI deduplicates).
