# Phase 28: High Availability Cache & Resilience - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** 8
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `pyproject.toml` | config | dependency resolution | existing runtime dependency declarations | exact |
| `uv.lock` | config | dependency resolution | existing generated lock entries | exact |
| `src/anonreq/cache/manager.py` | service | request-response | current `CacheManager` | exact |
| `src/anonreq/cache/health.py` | utility | request-response | current `check_cache_health` | exact |
| `src/anonreq/health.py` | route | request-response | current health/router helpers | exact |
| `src/anonreq/startup_checks.py` | service | request-response | current `_check_with_retry` / `run_startup_checks` | exact |
| `tests/test_cache.py` | test | request-response | existing fakeredis-backed manager tests | exact |
| `tests/test_health.py` / `tests/test_startup.py` | test | request-response | existing ASGI and async-mock probe tests | exact |

`tests/test_exceptions.py` is an existing contract dependency, not an expected Phase 28 edit: it already proves that `DependencyUnavailableError("valkey")` is rendered as the metadata-safe HTTP 503 envelope. Add a focused integration assertion only if cache retry exhaustion needs an end-to-end route proof beyond the cache-manager unit tests.

## Pattern Assignments

### `pyproject.toml` and `uv.lock` (config, dependency resolution)

**Analog:** `pyproject.toml:20-57`, `uv.lock:83-107`, `uv.lock:1960-1966`

Keep runtime dependencies in `[project].dependencies`, dev-only testing packages in the `dev` optional extra, and regenerate `uv.lock` rather than editing individual package records. `redis` is already a runtime dependency, so Phase 28 only needs to declare Tenacity at runtime.

```toml
# pyproject.toml:20-31
dependencies = [
    "fastapi>=0.138.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.14.2",
    "structlog>=26.1.0",
    "python-json-logger>=4.1.0",
    "redis>=8.0.0",
    "pyyaml>=6.0.3",
]
```

### `src/anonreq/cache/manager.py` (service, request-response)

**Analog:** current `src/anonreq/cache/manager.py:13-123`

This is the direct extension point. Keep one lifespan-scoped public manager and its `store_mapping`, `get_mapping`, `delete_mapping`, and `close` API; put URL validation/factory selection and the private retry execution helper here. Preserve the existing tenant/session key contract and reconstruct the write pipeline inside each retry attempt.

**Imports and construction pattern** (`manager.py:13-44`):

```python
from __future__ import annotations

import redis.asyncio as redis

class CacheManager:
    def __init__(self, redis_url: str, ttl: int = 300) -> None:
        self._redis = redis.from_url(
            redis_url,
            decode_responses=True,
            health_check_interval=5,
            socket_connect_timeout=3,
        )
        self._ttl = ttl
```

**Key isolation and atomic write pattern** (`manager.py:46-77`):

```python
def _key(self, tenant_id: str, session_id: str) -> str:
    return f"anonreq:{tenant_id}:{session_id}"

async def store_mapping(self, tenant_id: str, session_id: str, mapping: dict[str, str]) -> None:
    key = self._key(tenant_id, session_id)
    async with self._redis.pipeline(transaction=True) as pipe:
        await (
            pipe.hset(key, mapping=mapping)
            .expire(key, self._ttl)
            .execute()
        )
```

**Read/delete/lifecycle pattern** (`manager.py:79-123`):

```python
async def get_mapping(self, tenant_id: str, session_id: str) -> dict[str, str]:
    key = self._key(tenant_id, session_id)
    return await self._redis.hgetall(key)

async def delete_mapping(self, tenant_id: str, session_id: str) -> None:
    key = self._key(tenant_id, session_id)
    await self._redis.delete(key)

async def close(self) -> None:
    await self._redis.aclose()
```

**Error translation analog:** `src/anonreq/exceptions.py:104-124`. Catch the narrow, final transient Valkey exception outside the Tenacity boundary and raise `DependencyUnavailableError(dependency="valkey")`; do not let a `RetryError`, a redis exception, the custom URL, or exception text reach the route/log response path. Constructor parsing errors should remain immediate validation failures, not retried.

### `src/anonreq/cache/health.py` (utility, request-response)

**Analog:** current `src/anonreq/cache/health.py:18-59`

Keep cache protocol health behind `check_cache_health(manager)`, accepting the manager rather than a URL. This is topology-neutral because it invokes commands on the client chosen by `CacheManager`.

```python
async def check_cache_health(manager: CacheManager) -> dict[str, Any]:
    try:
        ping = await manager._redis.ping()
        config_save = await manager._redis.config_get("save")
        save_value = config_save.get("save", "") if config_save else ""
        save_val_list = [save_value] if isinstance(save_value, str) else (save_value or [])
        persistence_disabled = not save_val_list or save_val_list == [""]
        return {
            "reachable": ping,
            "persistence_disabled": persistence_disabled,
            "healthy": ping and persistence_disabled,
        }
    except Exception as e:
        return {
            "reachable": False,
            "persistence_disabled": False,
            "healthy": False,
            "error": str(e),
        }
```

The existing exception-text `error` field conflicts with Phase 28's no-connection-details requirement. Preserve the stable boolean health contract but replace/suppress unsafe backend text rather than logging or returning URL/credential-bearing errors.

### `src/anonreq/health.py` (route, request-response)

**Analog:** current `src/anonreq/health.py:29-123`

Retain the router and response-body helper convention. Split policy at the endpoint layer: `/health` reports the running process and returns 200 without dependency probes; `/health/ready` calls the component checker and returns 503 on cache or Presidio failure. Readiness should consume the lifespan cache manager from `request.app.state`, allowing `check_cache_health` rather than the standalone-only raw TCP URL probe.

**Component aggregation pattern** (`health.py:29-50`):

```python
async def _check_components() -> tuple[dict[str, str], bool]:
    valkey_ok = await check_valkey(settings.VALKEY_URL)
    presidio_ok = await check_presidio(settings.PRESIDIO_URL)
    components = {
        "valkey": {"status": "healthy" if valkey_ok else "unhealthy"},
        "presidio": {"status": "healthy" if presidio_ok else "unhealthy"},
        "gateway": {"status": "healthy"},
    }
    all_healthy = all(comp["status"] == "healthy" for comp in components.values())
    return components, all_healthy
```

**Response and route status pattern** (`health.py:53-80`, `103-123`):

```python
def _build_health_response(components: dict[str, dict[str, str]], all_healthy: bool) -> dict:
    overall_status = "healthy" if all_healthy else "degraded"
    logger.info("health_check", component="health_check", status=overall_status)
    return {"status": overall_status, "version": __version__, "components": components}

components, all_healthy = await _check_components()
response.status_code = 200 if all_healthy else 503
return _build_health_response(components, all_healthy)
```

Do not log dependency exception details or raw cache health error fields. Preserve current metadata-only component labels.

### `src/anonreq/startup_checks.py` (service, request-response)

**Analog:** current `src/anonreq/startup_checks.py:109-181`, with client-backed health analog in `src/anonreq/main.py:218-246`

The existing `check_valkey(url)` performs one-host TCP probing and cannot represent comma-separated Sentinel/Cluster authorities. Change its call path to consume the constructed `CacheManager`/`check_cache_health` result (or otherwise inject a topology-aware check) while preserving the current ordered dependency validation, bounded startup retry helper, and `DependencyUnavailableError` translation. Avoid creating a second manager because main already owns the one lifespan client.

```python
async def _check_with_retry(name: str, check_fn: Callable[[], Awaitable[bool]], max_retries: int = 5, delay: float = 3.0) -> bool:
    for attempt in range(max_retries):
        ok = await check_fn()
        if ok:
            return True
        if attempt < max_retries - 1:
            logger.warning(
                "%s unreachable (attempt %d/%d), retrying in %.0fs",
                name, attempt + 1, max_retries, delay, component="startup_checks",
            )
            await asyncio.sleep(delay)
    return False

if not valkey_ok:
    raise DependencyUnavailableError(dependency="valkey")
```

### `tests/test_cache.py` (test, request-response)

**Analog:** `tests/test_cache.py:20-62`, `:65-213`

Continue using a fakeredis client injected into `CacheManager.__new__` for mapping semantics. Add focused factory/parser tests by patching the imported Redis/Sentinel/Cluster factories and use injected async mocks or a small fake client for transient operation failures; no live Sentinel/Cluster deployment is needed.

```python
@pytest.fixture
def cache_manager():
    import fakeredis.aioredis
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    from anonreq.cache.manager import CacheManager
    manager = CacheManager.__new__(CacheManager)
    manager._redis = fake_redis
    manager._ttl = 300
    yield manager
```

**Existing assertion style** (`tests/test_cache.py:68-97`, `:102-155`): await the public method, then inspect the fake backend or assert the returned mapping. Extend this style for accepted standalone/Sentinel/Cluster URLs, malformed custom URLs, retry-then-success, retry exhaustion translating to `DependencyUnavailableError`, and `close()` across factory-created clients. Keep PII-like fixture strings only in cache behavior tests; never assert or capture URLs/credentials in logs.

### `tests/test_health.py` and `tests/test_startup.py` (test, request-response)

**Analogs:** `tests/test_health.py:19-31`, `:34-126`; `tests/test_startup.py:17-81`

Keep the minimal FastAPI router fixture and `httpx.ASGITransport` endpoint tests. Existing `unittest.mock.patch` targets imported module names and `return_value` produces awaitable async mocks for async checks.

```python
@pytest.fixture
def health_app():
    app = FastAPI()
    app.include_router(health_router)
    return app

@pytest.fixture
async def client(health_app: FastAPI):
    transport = ASGITransport(app=health_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@patch("anonreq.health.check_valkey", return_value=False)
@patch("anonreq.health.check_presidio", return_value=True)
async def test_health_503_when_valkey_unhealthy(...):
    response = await client.get("/health")
    assert response.status_code == 503
```

Replace the last test's expectation according to D-06: with Valkey unavailable, `/health` must be 200 and `/health/ready` must be 503. In startup tests, patch the new topology-aware health boundary and assert it receives the existing manager/client rather than a raw URL.

## Shared Patterns

### Lifespan-Owned Cache Singleton

**Source:** `src/anonreq/main.py:208-246`, `:649-675`

Create one `CacheManager` at lifespan startup, close it on every startup failure path, and store it at `app.state.cache_manager` only after preflight succeeds. Health and startup checks should reuse this instance; do not instantiate a second client per request/probe.

```python
cache_manager = CacheManager(settings.VALKEY_URL, ttl=settings.CACHE_TTL_SECONDS)
try:
    cache_health = await check_cache_health(cache_manager)
    if not cache_health.get("healthy", False):
        raise DependencyUnavailableError(dependency="cache")
except Exception:
    await cache_manager.close()
    raise

app.state.cache_manager = cache_manager
# shutdown
await cache_manager.close()
```

### Fail-Closed Error Envelope

**Source:** `src/anonreq/exceptions.py:104-124`, `:244-255`; tests in `tests/test_exceptions.py:111-127`

Use the existing dependency exception for terminal cache unavailability. Its global handler yields HTTP 503 with `service_unavailable` / `dependency_unavailable` and retains the request ID without exposing backend internals.

```python
class DependencyUnavailableError(AnonReqError):
    def __init__(self, dependency: str, request_id: str | None = None) -> None:
        self.dependency = dependency
        super().__init__(
            message=f"{dependency} unavailable",
            error_type="service_unavailable",
            status_code=503,
            code="dependency_unavailable",
            request_id=request_id,
        )
```

### Pipeline Propagation

**Source:** `src/anonreq/pipeline/tokenization.py:133-154`

Cache write failures not explicitly converted into a recoverable pipeline error propagate out of tokenization and prevent a provider call. Preserve that behavior: `DependencyUnavailableError` must not be caught as a permissive empty mapping/result. The broader FastAPI handler maps it to the safe 503 envelope.

```python
if all_mappings:
    store_result = self._cache_manager.store_mapping(
        ctx.tenant_id, ctx.context_id, all_mappings,
    )
    if inspect.isawaitable(store_result):
        await store_result
```

### Security and Logging

**Sources:** `AGENTS.md`; `src/anonreq/exceptions.py:277-298`; `src/anonreq/startup_checks.py:128-139`

Log component names, retry counts, and static status only. Do not log Valkey URLs, node lists, service names, raw mappings, or retry exception messages because they can disclose credentials or sensitive cache content. Keep retry predicates narrow so malformed configuration, programming errors, and cancellation fail immediately rather than delaying failure.
