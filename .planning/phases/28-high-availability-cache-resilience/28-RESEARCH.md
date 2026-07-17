# Phase 28: High Availability Cache & Resilience - Research

**Researched:** 2026-07-12
**Domain:** Async Python Valkey Sentinel/Cluster connectivity and fail-closed cache failover handling
**Confidence:** MEDIUM

## User Constraints

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

### Deferred Ideas

None - discussion stayed within phase scope

## Project Constraints (from AGENTS.md)

- Preserve fail-secure behavior: dependency failures must block forwarding; never permit an unsanitized upstream request.
- Do not put PII in logs or telemetry; connection URLs, mappings, request bodies, and raw cache values are not safe log fields.
- Keep mappings ephemeral, session-scoped, TTL-bound, and deleted after cleanup.
- Retain existing OpenAI-compatible routes and current package/config patterns.
- Read relevant source and tests; keep changes narrow and add focused pytest coverage, including fail-secure invariants where behavior changes.
- `AGENTS.md` requires both `req/requirements.md` and `req/requirements_v2.md` to be consulted for architectural decisions. [VERIFIED: codebase files]

## Summary

Phase 28 should keep one `CacheManager` public API and move topology selection behind an internal, validated URL parser/factory. The existing `redis` dependency is already locked at 8.0.1 and exposes the required asyncio Sentinel and Cluster clients. redis-py Sentinel returns a primary client via `master_for()` and automatically re-resolves after failover; Cluster accepts startup nodes and initializes topology asynchronously. [CITED: https://redis.readthedocs.io/en/latest/examples/asyncio_examples.html] [CITED: https://redis.readthedocs.io/en/latest/connections.html]

Every mapping read/write/delete must execute through a fresh retryable attempt. Retry only transient topology/transport conditions (`redis.exceptions.ConnectionError`, `TimeoutError`, and `ReadOnlyError`; include a documented cluster transient error only when its current redis-py class is explicitly tested). On exhaustion, translate the final retryable error to the project's existing `DependencyUnavailableError(dependency="valkey")`, which already maps to a metadata-safe HTTP 503 envelope. Do not retry malformed URLs, command/data errors, programming errors, or cancellation. [VERIFIED: `src/anonreq/exceptions.py`] [CITED: https://github.com/jd/tenacity]

Valkey Sentinel deliberately disconnects normal clients when a primary is reconfigured, so a reconnecting client is expected to resolve the primary again. That expected failure interval is why a bounded backoff with jitter is appropriate; it must still end in a denial response rather than a permissive fallback. [CITED: https://valkey.io/topics/sentinel-clients/]

**Primary recommendation:** Add a tested `CacheManager` topology parser/factory and a single retry-to-503 execution helper, then make readiness use the actual cache client while liveness reports process health only.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Parse `ANONREQ_VALKEY_URL` custom schemes | `cache/manager.py` | `config/__init__.py` type remains `str` | D-02 assigns topology choice to `CacheManager`; no new setting is allowed. [VERIFIED: phase context; `src/anonreq/config/__init__.py`]
| Build standalone/Sentinel/Cluster client | `CacheManager` internal factory | redis-py asyncio clients | Keeps all client construction and shutdown ownership in one lifespan-scoped component. [VERIFIED: `src/anonreq/main.py`; CITED: https://redis.readthedocs.io/en/latest/connections.html]
| Retry transient mapping operations | `CacheManager` internal execution helper | Tenacity | One policy prevents store/get/delete drift and preserves the public API. [CITED: https://github.com/jd/tenacity]
| Map exhausted cache failure to HTTP 503 | `CacheManager` | `DependencyUnavailableError` / global exception handler | The established exception already provides a safe 503 response without backend details. [VERIFIED: `src/anonreq/exceptions.py`]
| Readiness probe | `health.py` using app-state cache manager | `cache/health.py` | A real client `PING` works for all supported topologies; raw `urlparse()` TCP probing cannot parse comma-separated custom schemes. [VERIFIED: `src/anonreq/health.py`; `src/anonreq/startup_checks.py`]
| Liveness probe | `health.py` | FastAPI router | D-06 requires process liveness, independent of dependency reelection. [VERIFIED: phase context]

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---|---:|---|---|
| `redis` | 8.0.1 locked (uploaded 2026-06-23) | Existing async Valkey protocol client; standalone, Sentinel, and Cluster factories | Already declared and locked by the repository; official docs cover the required asyncio clients. [VERIFIED: `pyproject.toml`; `uv.lock`; https://redis.readthedocs.io/en/latest/connections.html] |
| `tenacity` | 9.1.4 current on PyPI (2026-02-07) | Async bounded retry and retry predicates | Official project documents coroutine retry, `stop_after_delay`, exponential waits, predicates, and `reraise=True`. [CITED: https://pypi.org/project/tenacity/] [CITED: https://github.com/jd/tenacity] |

### Supporting
| Library | Version | Purpose | When to Use |
|---|---:|---|---|
| `fakeredis` | 2.36.2 locked | Existing async unit-test backend | Keep its use for normal mapping tests; use mocks for Sentinel/Cluster factories and injected transient errors. [VERIFIED: `uv.lock`; `tests/test_cache.py`] |
| `pytest` / `pytest-asyncio` | existing project tooling | Async unit and endpoint tests | Verify parser, retry, exception translation, and probe semantics without a live HA deployment. [VERIFIED: `pyproject.toml`; `tests/test_cache.py`] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|---|---|---|
| Tenacity operation wrapper | redis-py internal retry configuration | redis-py has retry configuration, but D-04 explicitly requires Tenacity around all `CacheManager` reads/writes with the stated 30-second policy. [VERIFIED: phase context] |
| Explicit startup-node construction | `RedisCluster.from_url()` after translating the scheme | Explicit parsed nodes directly validate D-01’s comma-separated custom URL and avoid relying on undocumented custom-scheme handling. [CITED: https://redis.readthedocs.io/en/latest/_modules/redis/asyncio/cluster.html] |
| Cache-client readiness probe | raw TCP `check_valkey(url)` | The existing raw probe handles one host only and verifies neither Sentinel service discovery nor command capability. [VERIFIED: `src/anonreq/startup_checks.py`]

**Installation:**
```bash
uv add tenacity
uv lock
```

**Version verification:** The repository locks `redis==8.0.1`; its lock entry records a 2026-06-23 upload. PyPI lists `tenacity==9.1.4`, released 2026-02-07. [VERIFIED: `uv.lock`] [CITED: https://pypi.org/project/tenacity/]

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---|---|---:|---|---|---|---|
| `tenacity` | PyPI | Established; release history begins before 2019 | Not verified in this session | `github.com/jd/tenacity` | SUS (seam returned unknown metadata) | Flagged - planner must add `checkpoint:human-verify` before install. [CITED: https://pypi.org/project/tenacity/] |

**Packages removed due to [SLOP] verdict:** none.

**Packages flagged as suspicious [SUS]:** `tenacity` - the legitimacy seam could not resolve registry metadata, despite PyPI's verified publisher and source provenance; require the mandated human checkpoint before dependency installation. [VERIFIED: `package-legitimacy` seam result]

## Architecture Patterns

### System Architecture Diagram
```text
ANONREQ_VALKEY_URL
        |
        v
CacheManager parser/factory
  | standalone ------> redis.asyncio.from_url()
  | sentinel --------> Sentinel(sentinel hosts).master_for(service)
  | cluster ---------> RedisCluster(startup_nodes)
        |
        v
store_mapping / get_mapping / delete_mapping
        |
        v
Tenacity retry predicate (transient Valkey errors only)
  | success ----------------------> caller / pipeline continues
  | retry <= 30 seconds ----------> recreate command attempt after jittered wait
  | exhausted --------------------> DependencyUnavailableError -> HTTP 503 -> no forwarding

GET /health ----------------------> process alive -> HTTP 200
GET /health/ready --> actual cache PING/config health
                         | healthy -> HTTP 200
                         ` unavailable -> HTTP 503 / remove from pool
```

### Recommended Project Structure
```text
src/anonreq/
|- cache/
|  |- manager.py       # URL parser/factories and retry-to-503 operation helper
|  `- health.py        # client-backed cache health probe
|- health.py            # liveness/readiness response policy
`- startup_checks.py    # reuse topology-aware cache health rather than raw URL TCP parsing
tests/
|- test_cache.py        # parser, factory, retry, exhaustion, lifecycle tests
|- test_health.py       # liveness/readiness split
`- test_startup.py      # topology-aware startup probe behavior
```

### Pattern 1: Validated topology factory
**What:** Parse only the three D-01 scheme families with `urllib.parse.urlsplit`, then create the corresponding redis-py asyncio client. Validate every comma-separated `host:port`, require a non-empty Sentinel service name, reject unsupported schemes/empty node lists before serving traffic, and never log the input URL because it may contain credentials.

**When to use:** Once during `CacheManager` construction in the FastAPI lifespan; reuse the constructed client for the application lifetime. [VERIFIED: `src/anonreq/main.py`]

**Example:**
```python
# Source: https://redis.readthedocs.io/en/latest/examples/asyncio_examples.html
if scheme == "redis+sentinel":
    sentinel = Sentinel(sentinel_hosts, decode_responses=True, socket_connect_timeout=3)
    client = sentinel.master_for(service_name, decode_responses=True)
elif scheme == "redis+cluster":
    client = RedisCluster(startup_nodes=cluster_nodes, decode_responses=True)
else:
    client = redis.from_url(redis_url, decode_responses=True)
```

### Pattern 2: Retry a command factory, then translate terminal transient failure
**What:** Keep the actual cache command in a small async callable/helper invoked anew by the retry mechanism. Use `reraise=True` so the final redis exception is available to catch and translate. Catch only the configured transient exception tuple outside the retry boundary, then raise `DependencyUnavailableError(dependency="valkey")` without chaining backend details into a response or log field.

**When to use:** `store_mapping`, `get_mapping`, and `delete_mapping`; include any cache-health command that must tolerate a brief reelection. Do not apply it to URL parsing, constructor validation, `close()`, or arbitrary service code.

**Example:**
```python
# Source: https://github.com/jd/tenacity
@retry(
    reraise=True,
    retry=retry_if_exception_type(TRANSIENT_VALKEY_ERRORS),
    stop=stop_after_delay(30.0),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=2.0),
)
async def _run_cache_operation(operation: Callable[[], Awaitable[T]]) -> T:
    return await operation()
```

Implement the D-04 jitter requirement explicitly: the locked wait expression supplies exponential backoff but no randomness by itself, so combine it with Tenacity's jitter-capable wait strategy while preserving the required 0.1-2.0 base range. [CITED: https://tenacity.readthedocs.io/en/stable/changelog.html]

### Pattern 3: Process liveness separate from dependency readiness
**What:** Make `/health` report the running FastAPI process as HTTP 200 without dependency probes. Make `/health/ready` perform the cache health probe (and retain the project’s other readiness dependencies as applicable), returning 503 when Valkey is unavailable.

**When to use:** Every Kubernetes/Docker probe call; startup validation stays fail-secure and should use the topology-aware cache client, not the standalone-only raw TCP parser.

### Anti-Patterns to Avoid
- **Using `redis.from_url()` for `redis+sentinel`/`redis+cluster`:** redis-py documents `redis://` and `rediss://` URL schemes, while D-01 custom schemes need internal parsing and explicit factories. [CITED: https://redis.readthedocs.io/en/latest/examples/asyncio_examples.html]
- **Retrying all exceptions:** It hides malformed configuration and programming errors, prolongs failures, and can violate the 30-second availability contract.
- **Returning an empty mapping or succeeding after retry exhaustion:** Missing restoration mappings can release unreplaced tokens or permit an unsafe pipeline path; terminal cache unavailability must be 503.
- **Leaving `/health` dependent on Valkey:** It causes restart loops during a normal Sentinel reelection and contradicts D-06. [VERIFIED: phase context]
- **Logging retry exception text or the URL:** connection strings can contain credentials; cache values are sensitive. [VERIFIED: `AGENTS.md`]
- **Reusing a consumed Redis pipeline across attempts:** construct the pipeline inside each retried attempt so every retry has a new command context. [ASSUMED]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Sentinel discovery/reconnection | Custom `SENTINEL get-master-addr-by-name` polling client | `redis.asyncio.sentinel.Sentinel.master_for()` | redis-py implements Sentinel connection pools and automatic failover detection/reconnection. [CITED: https://redis.readthedocs.io/en/latest/connections.html] |
| Cluster slot/topology routing | Custom node selection or MOVED/ASK parser | `redis.asyncio.cluster.RedisCluster` | Cluster client initializes node topology and handles command routing. [CITED: https://redis.readthedocs.io/en/latest/_modules/redis/asyncio/cluster.html] |
| Async retry scheduler | Ad hoc loop with `asyncio.sleep` | Tenacity | Provides async waits, stop policies, retry predicates, and terminal exception behavior required by D-04. [CITED: https://github.com/jd/tenacity] |
| HTTP error envelope | New cache-specific FastAPI response formatting | existing `DependencyUnavailableError` | Existing global handling returns the required safe 503 response. [VERIFIED: `src/anonreq/exceptions.py`] |

**Key insight:** The application owns policy and exception translation, while redis-py owns topology protocol behavior and Tenacity owns bounded retry timing.

## Common Pitfalls

### Pitfall 1: Treating a Sentinel/Cluster URL as a normal URL
**What goes wrong:** `urlparse()` exposes the comma-separated authority as one netloc, and the existing raw TCP checker can only select one hostname/port.

**Why it happens:** The required `redis+sentinel` and `redis+cluster` forms are application-level schemes, not the normal redis-py URL schemes.

**How to avoid:** Validate custom schemes in `CacheManager`, return structured internal configuration errors before startup, and probe through the constructed client.

**Warning signs:** tests only cover `redis://`; readiness probes fail before Sentinel discovery; client factory receives the full comma list as a host. [VERIFIED: `src/anonreq/startup_checks.py`; `tests/test_cache.py`]

### Pitfall 2: Wrong retry boundary or exception conversion
**What goes wrong:** A retry decorator either leaks a `RetryError`/redis exception as HTTP 500, or retries permanent cache errors for 30 seconds.

**Why it happens:** Tenacity defaults and exception tuples are broader than the security contract.

**How to avoid:** Use `reraise=True`, a narrow transient redis exception predicate, the locked 30-second stop budget, and one outer terminal translation to `DependencyUnavailableError`.

**Warning signs:** test sees 500 rather than 503 after exhaustion; parser errors sleep/retry; cancellation is swallowed. [CITED: https://github.com/jd/tenacity]

### Pitfall 3: Pipeline retry correctness
**What goes wrong:** `HSET + EXPIRE` is retried after a network failure that occurred after the server applied it, or a stale pipeline object is reused.

**Why it happens:** Transport errors do not prove whether the server executed the command.

**How to avoid:** Preserve the existing atomic `HSET + EXPIRE` pipeline, create it per attempt, and test the eventual stored mapping/TTL. Treat mapping writes as idempotent for the same session/mapping; do not invent a permissive fallback. [VERIFIED: `src/anonreq/cache/manager.py`] [ASSUMED]

### Pitfall 4: Readiness/liveness regression
**What goes wrong:** Either `/health` keeps returning 503 during election, causing a restart loop, or `/health/ready` becomes a process-only probe and routes traffic to a cache-broken instance.

**Why it happens:** The current endpoints share `_check_components()` and have identical status policy.

**How to avoid:** Split endpoint policy and add explicit tests for both failure modes.

**Warning signs:** `/health` and `/health/ready` return the same code with Valkey mocked unavailable. [VERIFIED: `src/anonreq/health.py`; `tests/test_health.py`]

## Code Examples

Verified patterns from official sources:

### Sentinel primary client
```python
# Source: https://redis.readthedocs.io/en/latest/examples/asyncio_examples.html
from redis.asyncio.sentinel import Sentinel

sentinel = Sentinel([("sentinel1", 26379), ("sentinel2", 26379)])
client = sentinel.master_for("mymaster", decode_responses=True)
await client.ping()
```

### Cluster startup nodes
```python
# Source: https://redis.readthedocs.io/en/latest/_modules/redis/asyncio/cluster.html
from redis.asyncio.cluster import ClusterNode, RedisCluster

client = RedisCluster(
    startup_nodes=[ClusterNode("node1", 6379), ClusterNode("node2", 6379)],
    decode_responses=True,
)
await client.initialize()
```

### Async terminal exception preservation
```python
# Source: https://github.com/jd/tenacity
@retry(
    reraise=True,
    retry=retry_if_exception_type((ConnectionError, TimeoutError, ReadOnlyError)),
    stop=stop_after_delay(30.0),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=2.0),
)
async def operation() -> None:
    await client.ping()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| One `redis.from_url()` client and raw host TCP health probe | topology-aware asyncio redis-py clients with client-backed readiness | Phase 28 | Supports Sentinel/Cluster and accurately reflects cache usability. [VERIFIED: current code; phase context] |
| Identical dependency-aware `/health` and `/health/ready` | process liveness plus dependency readiness | Phase 28 | Prevents reelection crash loops while withholding traffic from unready instances. [VERIFIED: phase context] |

**Deprecated/outdated:**
- Raw `check_valkey(url)` as the authoritative readiness/startup mechanism: it cannot represent D-01 custom multi-node URLs and does not issue a Valkey command. [VERIFIED: `src/anonreq/startup_checks.py`]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | A Redis pipeline must be recreated for every retry attempt. | Anti-Patterns / Pitfall 3 | A stale context could make retries fail incorrectly or leak resources. |
| A2 | Repeating the same session mapping write is acceptable under ambiguous transport completion. | Pitfall 3 | A different write semantic could require an idempotency guard. |

## Open Questions (RESOLVED)

1. **Exact jitter composition with the locked wait expression**
   - **Resolution:** Preserve D-04's required `wait_exponential(multiplier=0.1, min=0.1, max=2.0)` base curve and compose bounded jitter with it. The effective delay for every retry must remain within the inclusive 0.1-2.0 second range; jitter must never lower a delay below 0.1 seconds or raise it above 2.0 seconds.
   - **Planning consequence:** Implement the composed wait strategy in the single CacheManager retry helper and unit-test deterministic or mocked jitter outcomes at the lower and upper bounds. [CITED: https://tenacity.readthedocs.io/en/stable/changelog.html]

2. **Health treatment of Presidio during liveness**
   - **Resolution:** Presidio remains a readiness dependency. `/health/ready` must continue to report it alongside Valkey and return 503 when either required dependency is unavailable, while `/health` is process-only and returns 200 whenever the FastAPI process is running.
   - **Planning consequence:** Split only liveness from dependency probes; retain Presidio in the readiness component check and add endpoint tests covering both Presidio-unready and Valkey-unready states. [VERIFIED: phase context; `src/anonreq/health.py`]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| `redis` | all connection factories | Yes | 8.0.1 | none; already project dependency. [VERIFIED: `uv.lock`] |
| `tenacity` | D-04 retry policy | No | PyPI current 9.1.4 | none; install after required human legitimacy checkpoint. [VERIFIED: local import; CITED: https://pypi.org/project/tenacity/] |
| `fakeredis` | focused cache tests | Yes | 2.36.2 | mocks for topology-specific behavior. [VERIFIED: `uv.lock`] |

**Missing dependencies with no fallback:** `tenacity` for the explicitly required retry implementation.

**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|---|---|
| Framework | pytest with pytest-asyncio and fakeredis |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_cache.py tests/test_health.py tests/test_startup.py -q` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| HA-01 | Parse each supported scheme and instantiate standalone/Sentinel/Cluster factory with expected nodes/service | unit with patched factories | `uv run pytest tests/test_cache.py -q` | Exists; cases are Wave 0 additions |
| HA-01 | Reject malformed custom URL without attempting a client connection or logging credentials | unit | `uv run pytest tests/test_cache.py -q` | Exists; cases are Wave 0 additions |
| HA-03 | Transient `ConnectionError`/`ReadOnlyError` is retried and mapping operation eventually succeeds | async unit with injected operation failures | `uv run pytest tests/test_cache.py -q` | Exists; cases are Wave 0 additions |
| HA-03 | Retry exhaustion becomes `DependencyUnavailableError`/HTTP 503 and no forwarding path succeeds | unit plus route/integration boundary test | `uv run pytest tests/test_cache.py tests/test_exceptions.py -q` | Exists; focused cases are Wave 0 additions |
| HA-03 | `/health` is 200 while Valkey is unavailable, `/health/ready` is 503 | endpoint unit | `uv run pytest tests/test_health.py -q` | Exists; cases are Wave 0 additions |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_cache.py tests/test_health.py tests/test_startup.py -q`
- **Per wave merge:** `uv run pytest tests/test_cache.py tests/test_health.py tests/test_startup.py tests/test_exceptions.py -q`
- **Phase gate:** `uv run pytest`

### Wave 0 Gaps
- [ ] Extend `tests/test_cache.py` for parser/factory contracts, retries, terminal exception translation, and `close()` for all client types.
- [ ] Extend `tests/test_health.py` for the required liveness/readiness split.
- [ ] Extend `tests/test_startup.py` for topology-aware Valkey health checking.
- [ ] Add/confirm an integration assertion that cache retry exhaustion prevents upstream forwarding and yields the existing HTTP 503 envelope.

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | No | Phase does not add identity handling. |
| V3 Session Management | Yes | Preserve TTL-bound session mapping and fail closed when it cannot be read/written. [VERIFIED: `AGENTS.md`] |
| V4 Access Control | No | Tenant controls are Phase 31; do not broaden scope. [VERIFIED: roadmap] |
| V5 Input Validation | Yes | Strictly validate deployment-controlled custom Valkey URLs before client construction; never log credentials. |
| V6 Cryptography | No | TLS is conveyed by `rediss` but Phase 28 does not introduce cryptographic primitives. |

### Known Threat Patterns for async Valkey failover
| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Cache outage permits unsanitized forwarding | Elevation of Privilege / Information Disclosure | Convert exhausted transient cache failure to `DependencyUnavailableError` and abort pipeline before provider forwarding. [VERIFIED: `AGENTS.md`; `src/anonreq/exceptions.py`] |
| Credential disclosure through connection diagnostics | Information Disclosure | Do not log URL/exception text; use component-only structured metadata. [VERIFIED: `AGENTS.md`] |
| Retry storm during primary election | Denial of Service | Bounded exponential backoff with jitter and a fixed 30-second deadline. [VERIFIED: phase context; CITED: https://valkey.io/topics/sentinel-clients/] |
| Malformed topology string drives unintended connection | Tampering | Allowlist D-01 schemes and validate each host/port/service segment before factory creation. |

## Sources

### Primary (HIGH confidence)
- Project source and tests: `src/anonreq/cache/manager.py`, `src/anonreq/cache/health.py`, `src/anonreq/health.py`, `src/anonreq/startup_checks.py`, `src/anonreq/exceptions.py`, `tests/test_cache.py`, `tests/test_health.py`, `tests/test_startup.py` - current implementation, public contracts, and tests. [VERIFIED: codebase]
- `.planning/research/ARCHITECTURE.md` section 2.3 and 3.3; `.planning/research/PITFALLS.md` section 3 - canonical phase guidance. [VERIFIED: codebase]

### Secondary (MEDIUM confidence)
- [redis-py asyncio examples](https://redis.readthedocs.io/en/latest/examples/asyncio_examples.html) - asyncio Sentinel `master_for()` and supported normal URL schemes.
- [redis-py connections](https://redis.readthedocs.io/en/latest/connections.html) - Sentinel behavior and async `RedisCluster` constructor.
- [redis-py async cluster source docs](https://redis.readthedocs.io/en/latest/_modules/redis/asyncio/cluster.html) - startup node initialization and `from_url()` capabilities.
- [Valkey Sentinel client spec](https://valkey.io/topics/sentinel-clients/) - reconnection requirements during primary reconfiguration.
- [Tenacity project documentation](https://github.com/jd/tenacity) and [PyPI release metadata](https://pypi.org/project/tenacity/) - async retries, stopping, predicates, provenance, and current release.

### Tertiary (LOW confidence)
- None beyond the two explicitly marked implementation assumptions.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH for redis-py/current lock; MEDIUM for Tenacity version and behavior because official docs were retrieved through WebSearch after Context7 CLI was unavailable.
- Architecture: HIGH for code integration points and locked phase decisions; MEDIUM for library topology behavior from official documentation.
- Pitfalls: MEDIUM; Valkey/redis-py document failover behavior, while pipeline idempotency details require implementation validation.

**Research date:** 2026-07-12
**Valid until:** 2026-08-11
