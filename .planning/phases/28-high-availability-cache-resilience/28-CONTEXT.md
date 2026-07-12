# Phase 28: High Availability Cache & Resilience - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers resilient, high-availability-aware Valkey connection caching logic that is fail-safe during reelection.

</domain>

<decisions>
## Implementation Decisions

### Connection Configuration
- **D-01:** Parse custom sub-schemes in `ANONREQ_VALKEY_URL` to configure the Valkey client mode:
  - Standalone: `redis://<host>:<port>` or `rediss://<host>:<port>`
  - Sentinel: `redis+sentinel://<sentinel_1>:<port>,<sentinel_2>:<port>/<service_name>` (e.g., `redis+sentinel://sentinel1:26379,sentinel2:26379/mymaster`)
  - Cluster: `redis+cluster://<node_1>:<port>,<node_2>:<port>`
- **D-02:** `CacheManager` parses the custom URL internally and instantiates the appropriate `redis.asyncio` client backend (`redis.from_url`, `Sentinel`, or `redis.cluster.RedisCluster`) without adding new environment configuration options.

### Retry Policy & Resiliency
- **D-03:** Use opinionated, self-healing retry defaults embedded in `CacheManager` for transient connection/read-only failovers. Do not expose new settings variables.
- **D-04:** Wrap all CacheManager read/write operations with a Tenacity retry policy to handle reelection failovers. The retry mechanism must:
  - Enforce a maximum timeout window of 30.0 seconds.
  - Implement exponential backoff with jitter starting at 0.1 seconds and capping at 2.0 seconds (`stop=stop_after_delay(30.0), wait=wait_exponential(multiplier=0.1, min=0.1, max=2.0)`).

### Fail-Closed Behavior & Health Reporting
- **D-05:** If Valkey remains offline after the 30-second retry timeout, operations must fail-closed, throwing a dependency exception that returns an `HTTP 503 Service Unavailable` response to clients.
- **D-06:** Implement clear separation of concerns between liveness and readiness:
  - `/health/ready` (Readiness): Return `HTTP 503 Service Unavailable` if Valkey is unreachable, removing the instance from the ingress routing pool.
  - `/health` (Liveness): Continue returning `HTTP 200 OK` as long as the FastAPI process is running to prevent orchestrator crash-looping during database reelection windows.

### the agent's Discretion
- The exact URL parsing utility implementation (e.g., custom string splitting vs urllib extension).
- Exact exception handling hooks to intercept `ConnectionError` and `ReadOnlyError` under the Tenacity retry decorator.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Roadmap & Requirements
- `.planning/ROADMAP.md` — Phase 28 definition, goal, and success criteria
- `.planning/PROJECT.md` — Core constraints (fail-secure, no PII in logs, ephemeral cache)

### v2.0 Research
- `.planning/research/ARCHITECTURE.md` §2.3 & §3.3 — Valkey Sentinel & Cluster connection factories and failover retry design
- `.planning/research/PITFALLS.md` §3 — Failover latency and thundering herd mitigations

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CacheManager` (`src/anonreq/cache/manager.py`) — Existing Valkey manager mapping cache operations.

### Established Patterns
- Pydantic Settings configuration using the `ANONREQ_` prefix.
- Lifespan-scoped singletons attached to `app.state`.

### Integration Points
- `src/anonreq/cache/manager.py` — Client initialization and connection routing.
- `src/anonreq/health.py` — Readiness probe implementation.
- `src/anonreq/startup_checks.py` — Connection validation checks during startup.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 28-high-availability-cache-resilience*
*Context gathered: 2026-07-12*
