# Phase 28-02 Summary

Implemented the fail-closed retry and readiness wiring for Valkey reelection handling.

What changed:
- `CacheManager` public mapping operations now share one bounded Tenacity retry boundary.
- Transient cache failures retry with jittered exponential waits capped to the 0.1s-2.0s range and a 30s stop window.
- Exhausted retryable cache failures translate to `DependencyUnavailableError(dependency="valkey")`.
- `/health` now reports process liveness only.
- `/health/ready` now checks the lifespan-owned `CacheManager` plus Presidio readiness.
- Startup checks now reuse the lifespan-created `CacheManager` instead of probing Valkey via raw TCP.
- Tokenization preserves terminal cache dependency failures so the pipeline fails closed before `ProviderStage`.
- The fail-secure property coverage now proves a cache-write dependency failure returns HTTP 503 and does not reach the provider.

Verification:
- `uv run pytest tests/test_cache.py tests/test_health.py tests/test_startup.py tests/property/test_fail_secure.py::test_cache_dependency_unavailable_returns_503_before_provider -q`
- `uv run pytest tests/property/test_fail_secure.py -q`
- `uv run pytest -q`

Notes:
- The integration runtime wiring test now seeds `app.state.cache_manager` explicitly for `/health/ready`.
- No cache-health response leaks backend exception text, URLs, or mapping values.
