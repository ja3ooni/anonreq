# Phase 29 Pattern Map

## File Roles

| File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/anonreq/main.py` | lifespan/bootstrap | request-response | existing app state wiring | exact |
| `src/anonreq/config/__init__.py` | config baseline | startup | env-backed settings singleton | exact |
| `src/anonreq/providers/registry.py` | credential resolution | request startup | provider registry / env key resolution | exact |
| `src/anonreq/logging_config.py` | structured logging | request-response | allowlist processor chain | exact |
| `src/anonreq/proxy/ca_manager.py` | hot reload | background file watch | watchdog observer pattern | exact |
| `src/anonreq/streaming/restoration.py` | in-memory stream state | streaming session | session-local mapping cache | close |
| `tests/test_logging.py` | log behavior | unit | structured logging assertions | exact |
| `tests/unit/streaming/test_restoration.py` | stream state | unit | session-local buffer tests | exact |

## Pattern Assignments

### Secret Bootstrap

Treat secret retrieval as startup-owned infrastructure, not as per-request state. The cleanest shape is:

- a narrow secret source abstraction
- an in-memory secret store populated during lifespan startup
- provider resolution reading from that store before any fallback path

The code should avoid writing secret payloads into `Settings`, `.env` files, or disk caches.

### Hot Reload

Use the existing watchdog model from `proxy/ca_manager.py`:

- start an observer on the mounted secret/config directory
- debounce repeated writes
- reload into a fresh in-memory snapshot
- swap the snapshot atomically

This keeps the service running while secrets rotate.

### Log Redaction

Extend the structlog processor chain instead of replacing it. Add a processor that redacts suspicious secret substrings in string values before `JSONRenderer` runs. The current allowlist should remain in place to drop unexpected top-level fields.

### Rotation Buffer

Use a read-only snapshot model similar to `StreamingRestorationStage`:

- the active stream gets a snapshot when it starts
- the previous snapshot remains available until the stream closes
- new streams read the latest snapshot only

That keeps active SSE output stable during rotation.

