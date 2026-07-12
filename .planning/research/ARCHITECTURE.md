# Architecture Integration Plan — AnonReq v2.0 Enterprise & Deployment Moat

**Domain:** Self-hosted AI security & anonymization gateway
**Researched:** 2026-07-12
**Project Phase:** v2.0 — Enterprise & Deployment Moat (SSO/RBAC, Tenancy, HA/Scaling, Secrets)

This document details the integration design for the new enterprise capabilities of Milestone v2.0. It maps the architectural boundaries, request flows, and technical patterns required to integrate SSO/RBAC, Multi-Tenant Isolation, HA/Scaling, and Cloud Secrets Management into the existing AnonReq gateway.

---

## 1. Recommended Architecture

The AnonReq v2.0 architecture expands the gateway by introducing centralized authentication validation, dynamic multi-tenant context propagation, failover-resilient connection pools, and file-based dynamic secrets loading.

```
                  ┌───────────────────────────────────────────────┐
                  │           Ingress Proxy (Envoy/Nginx)         │
                  │   - terminates external TLS / mTLS            │
                  │   - forwards client certificate headers       │
                  └───────────────────────┬───────────────────────┘
                                          │ mTLS info & headers
                                          ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Gateway (create_app)                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Middleware Stack                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │ set_request_ctx  │  │ SSOAuthMiddleware│  │ TenantIsolation  │  │Metrics / Policy│  │
│  │ (request_id, etc)│  │ (Authlib OIDC)   │  │ (Tenant Context) │  │(tenant-scoped) │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  └───────┬────────┘  │
│           │                     │                     │                    │           │
│           ▼                     ▼                     ▼                    ▼           │
│    [RequestContext]     [role_principal]      [app.current_tenant]  [Prometheus]       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Runtime / Service Adapters                                                            │
│  ┌──────────────────────────────────┐        ┌──────────────────────────────────────┐  │
│  │ CacheManager (Valkey)            │        │ SQLAlchemy Session                   │  │
│  │ - Key: `anonreq:tenant_x:sess_y`  │        │ - Execs `SET LOCAL app.tenant_id`    │  │
│  │ - Sentinel/Cluster pools         │        │ - Enforces PG Row-Level Security     │  │
│  └────────────────┬─────────────────┘        └──────────────────┬───────────────────┘  │
└───────────────────┼─────────────────────────────────────────────┼──────────────────────┘
                    │                                             │
                    ▼ (ephemeral)                                 ▼ (durable)
┌────────────────────────────────────────┐        ┌──────────────────────────────────────┐
│        Valkey Cluster / Sentinel       │        │       PostgreSQL Multi-Tenant        │
│ - HA Replication & Auto-Failover       │        │ - Row-Level Security (RLS) tables    │
└────────────────────────────────────────┘        └──────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Integrates With | Communication Protocol / Pattern |
|-----------|----------------|-----------------|----------------------------------|
| `SSOAuthenticationMiddleware` | Extracts & validates JWT from OIDC/SAML; caches JWKS keys locally. | `authlib`, `CacheManager` (Valkey) | JWT parsing + local Redis-backed JWKS cache lookup |
| `TenantContextMiddleware` | Resolves tenant ID from request (OIDC claims, hostname, or API keys); binds to thread/async context. | `RequestContext`, `structlog` | FastAPI HTTP request state injection |
| `CacheManager` (Updated) | Connects to Valkey Cluster or Sentinel based on connection URL scheme. Prefix keys with tenant ID. | `redis.asyncio` (Sentinel/Cluster client) | TCP Connection Pool with keep-alives and retries |
| SQLAlchemy Session Hook | Intercepts session creation, runs `SET LOCAL app.current_tenant_id` at transaction start. | PostgreSQL RLS Engine | Dynamic SQL execution on connection checkout |
| `VaultConfigProvider` (Fallback) | Direct HashiCorp Vault client using AppRole or Token to pull secrets directly at startup. | `hvac` | REST API (HTTPS) |
| Secrets File Watcher | Monitors file updates from External Secrets Operator (ESO) and reloads Pydantic Settings. | `watchdog`, Pydantic Settings | File system events (inotify) -> atomic in-memory reload |

---

## 2. Integration Points & Data Flows

### 2.1 SSO/RBAC Token Validation & Verification
```
Client Request
  │
  ▼  [Authorization: Bearer <JWT>]
FastAPI Ingress
  │
  ▼
SSOAuthenticationMiddleware
  │
  ├── 1. Check local cache in Valkey for OIDC JWKS (24h TTL)
  │      ├── IF Cached: Retrieve public keys
  │      └── IF Missed: Fetch from IdP via HTTP (asynchronous) and cache
  │
  ├── 2. Validate JWT signature, expiry (exp), audience (aud), and issuer (iss)
  │
  ├── 3. Map JWT claims (e.g., 'roles' or 'groups') to `Role` enum via ANONREQ_ROLE_MAPPING
  │
  ▼
Inject `request.state.role_principal` -> [principal_id, role, tenant_id]
  │
  ▼
Route Handler (FastAPI Dependency: `Depends(require_role(minimum_role))`)
```

### 2.2 Multi-Tenant Database Row-Level Security (RLS)
```
SQLAlchemy Session Created
  │
  ▼
FastAPI Dependency `get_db_session`
  ├── Retrieves `tenant_id` from ContextVar (set by TenantContextMiddleware)
  ├── Executes `SET LOCAL app.current_tenant_id = :tenant_id` on the database connection
  │
  ▼
SQL Query Executed (e.g., `SELECT * FROM policies`)
  │
  ▼
PostgreSQL Engine
  ├── Intercepts query using RLS policy:
  │   `USING (tenant_id = current_setting('app.current_tenant_id'))`
  │
  ▼
Returns tenant-isolated records only
```

### 2.3 HA Cache Routing in CacheManager
```
Startup: Parse ANONREQ_VALKEY_URL
  │
  ├── Case 1: url starts with "redis+sentinel://"
  │     ├── Initialize `redis.sentinel.Sentinel` pool
  │     └── Obtain connection via `sentinel.master_for(service_name)`
  │
  ├── Case 2: url starts with "redis+cluster://"
  │     └── Initialize `redis.asyncio.cluster.RedisCluster` pool
  │
  └── Case 3: url starts with "redis://" or "rediss://"
        └── Initialize standard single-instance `redis.from_url` pool
```

### 2.4 Secrets Dynamic Loading & Hot-Reloading
```
Kubernetes External Secrets Operator (ESO)
  │  (syncs secrets from AWS/GCP KMS or Vault)
  ▼
Write secrets payload to `/vault/secrets/config.json` (shared memory volume)
  │
  ▼
watchdog FileSystemEventHandler (running in background task)
  │  (detects MODIFY event on secret config path)
  ▼
Trigger reload_settings()
  ├── Read new secrets from file
  ├── Instantiate new Settings model atomically
  └── Replace global `settings` object in memory (thread-safe swap)
```

---

## 3. Detailed Component Designs

### 3.1 SSO & RBAC Integration

To maintain a secure, low-latency authentication mechanism, SSO uses **Authlib** and integrates into the existing FastAPI dependency injection and middleware stack:

1. **Role enum and hierarchy:** The existing `Role` enum in `src/anonreq/middleware/rbac.py` is maintained:
   - `ADMINISTRATOR` (4)
   - `SECURITY_OFFICER` (3)
   - `OPERATOR` (2)
   - `READ_ONLY` (1)
2. **SSO token parsing & claims mapping:**
   - Configure a mapping dictionary in settings: `ANONREQ_ROLE_MAPPING: dict[str, str]` (e.g., `{"oidc_group_admins": "administrator", "oidc_group_ops": "operator"}`).
   - An OIDC middleware decrypts incoming JWT tokens and looks up the mapped roles.
3. **Local JWKS Caching:** OIDC token validation requires the Identity Provider's public keys. To prevent request blockages, keys are cached in Valkey:
   ```python
   # In src/anonreq/sso/jwks.py
   async def get_jwks(cache_manager: CacheManager, jwks_uri: str) -> dict:
       cache_key = "sso:jwks_keys"
       keys = await cache_manager.get_mapping("*", cache_key)
       if not keys:
           async with httpx.AsyncClient() as client:
               resp = await client.get(jwks_uri)
               keys = resp.json()
           # Cache keys with 24 hours TTL
           await cache_manager.store_mapping("*", cache_key, {"payload": json.dumps(keys)})
       else:
           keys = json.loads(keys["payload"])
       return keys
   ```
4. **mTLS Perimeter Termination:** In production, client X.509 cert validation is terminated by the Kubernetes Ingress proxy. The ingress forwards cert parameters:
   - `X-SSL-Client-Subject-DN` / `X-SSL-Client-CN`
   - The gateway's `mTLSAuthMiddleware` parses this header, matches it against a trusted configuration, and populates `request.state.role_principal`. To prevent header spoofing, this middleware must verify the source IP belongs to the trusted ingress CIDR list (`ANONREQ_TRUSTED_PROXIES`).

### 3.2 Multi-Tenant Isolation

AnonReq achieves multi-tenant isolation by dynamically capturing, isolating, and propagating the `tenant_id` across all layers:

1. **Context Resolution:** The `tenant_id` is resolved in `TenantContextMiddleware` based on Host subdomain, path param, or JWT claim (`tenant` or `org`). It stores `tenant_id` in a Python `contextvars.ContextVar`.
2. **Valkey Isolation:** Segment the Valkey database using keys matching the prefix `anonreq:tenant_{tenant_id}:{session_id}`. Since Redis/Valkey Cluster mode does not support separate logical database indices. Prefix namespacing is the only viable isolation strategy.
3. **Database RLS Integration:** 
   We configure SQLAlchemy's connection checkout listener to set the session context variables dynamically:
   ```python
   # In src/anonreq/database/session.py
   from contextvars import ContextVar
   from sqlalchemy import event
   from sqlalchemy.ext.asyncio import AsyncSession

   tenant_context: ContextVar[str] = ContextVar("tenant_id")

   @event.listens_for(AsyncSession, "after_transaction_create")
   def set_tenant_id_context(session, transaction):
       tenant_id = tenant_context.get(None)
       if tenant_id:
           # Execute on raw connection within current transaction
           session.execute(
               text("SET LOCAL app.current_tenant_id = :tenant_id"),
               {"tenant_id": tenant_id}
           )
   ```
   PostgreSQL tables are protected by an RLS Policy:
   ```sql
   ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
   CREATE POLICY tenant_isolation ON audit_logs 
     USING (tenant_id = current_setting('app.current_tenant_id'));
   ```

### 3.3 HA/Scaling & Disaster Recovery

The gateway must handle Sentinel failovers and Cluster slot re-routings transparently to prevent failing open or returning 5xx errors:

1. **Valkey Sentinel & Cluster Support in CacheManager:**
   Modify `CacheManager` to inspect connection schemes:
   ```python
   # In src/anonreq/cache/manager.py
   import redis.asyncio as redis
   from redis.asyncio.sentinel import Sentinel

   class CacheManager:
       def __init__(self, redis_url: str, ttl: int = 300) -> None:
           self._ttl = ttl
           if redis_url.startswith("redis+sentinel://") or redis_url.startswith("rediss+sentinel://"):
               # Format: redis+sentinel://sentinel1:26379,sentinel2:26379/service_name
               sentinel_hosts, service_name = parse_sentinel_url(redis_url)
               self._sentinel = Sentinel(sentinel_hosts, socket_timeout=3)
               self._redis = self._sentinel.master_for(service_name, decode_responses=True)
           elif redis_url.startswith("redis+cluster://") or redis_url.startswith("rediss+cluster://"):
               # Format: redis+cluster://node1:6379,node2:6379
               cluster_hosts = parse_cluster_url(redis_url)
               self._redis = redis.cluster.RedisCluster(
                   startup_nodes=cluster_hosts, 
                   decode_responses=True,
                   socket_timeout=3
               )
           else:
               self._redis = redis.from_url(
                   redis_url,
                   decode_responses=True,
                   health_check_interval=5,
                   socket_connect_timeout=3,
               )
   ```
2. **Exponential Backoff on Failover:**
   When Valkey experiences Sentinel master reelection, connections throw `ReadOnlyError` or `ConnectionError`. Wrap cache calls with retry policies:
   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential

   @retry(
       stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
       retry=retry_if_exception_type((redis.ConnectionError, redis.TimeoutError))
   )
   async def store_mapping_with_retry(self, ...):
       # method code
   ```
3. **Stateless Scale-Out:**
   All cluster pods remain stateless. Replicas are distributed evenly using pod anti-affinity in the Helm chart:
   ```yaml
   affinity:
     podAntiAffinity:
       requiredDuringSchedulingIgnoredDuringExecution:
         - labelSelector:
             matchExpressions:
               - key: app.kubernetes.io/name
                 operator: In
                 values:
                   - anonreq-gateway
           topologyKey: "kubernetes.io/hostname"
   ```

### 3.4 Secrets Management & Rotation

Secrets configuration relies on cloud-native separation of concerns, utilizing File Watcher reloads and Key version maps:

1. **Pydantic Settings with File Watcher:**
   The `watchdog` library monitors `/vault/secrets/config.json` and updates settings atomically in memory:
   ```python
   # In src/anonreq/core/config_watcher.py
   from watchdog.observers import Observer
   from watchdog.events import FileSystemEventHandler

   class ConfigReloadHandler(FileSystemEventHandler):
       def on_modified(self, event):
           if event.src_path == "/vault/secrets/config.json":
               logger.info("Secrets file modified on disk. Reloading settings.")
               settings.reload_from_file("/vault/secrets/config.json")
   ```
2. **Direct HashiCorp Vault Fallback:**
   For bare-metal and non-K8s environments, `hvac` is used directly:
   ```python
   # In src/anonreq/core/vault.py
   import hvac

   def load_vault_secrets(vault_addr: str, auth_token: str) -> dict:
       client = hvac.Client(url=vault_addr, token=auth_token)
       secret_version_response = client.secrets.kv.v2.read_secret_version(
           path='anonreq-secrets',
       )
       return secret_version_response['data']['data']
   ```
3. **Session Key Versioning & Rotation:**
   Instead of using a single seed, load a map of versions:
   - Config format: `ANONREQ_SESSION_SEEDS = '{"1": "key_seed_v1", "2": "key_seed_v2"}'`
   - Active version: `ANONREQ_ACTIVE_SEED_VERSION = "2"`
   - Encrypting: Gateway retrieves active version `"2"` and uses `"key_seed_v2"`. Stored mappings prefix payloads with key version: `v2:encrypted_payload`.
   - Decrypting: Parse version from prefix, retrieve correct key from `ANONREQ_SESSION_SEEDS`, and decrypt. This ensures zero session downtime when rotating keys.

---

## 4. Anti-Patterns to Avoid

* **Anti-Pattern: Conflating Identity with Tenant Authorization**
  * *Why bad*: Granting a Tenant A admin user access to admin APIs of Tenant B.
  * *Instead*: Ensure every RBAC check incorporates both role hierarchy verification and strict `tenant_id` context validation.
* **Anti-Pattern: Synchronous OIDC Public Key Fetches**
  * *Why bad*: Fetching the IdP's JWKS keys per-request synchronously blocks incoming user request streams, adding seconds of latency and locking the ASGI event loop.
  * *Instead*: Cache JWKS keys in Valkey with a 24h TTL, and fetch keys asynchronously in the background.
* **Anti-Pattern: Separate connection pools per Tenant**
  * *Why bad*: Direct database isolation (database-per-tenant) exhausts postgres connections.
  * *Instead*: Use shared PostgreSQL instance, isolated via dynamic Schema mapping and postgres Row-Level Security (RLS).
* **Anti-Pattern: Storing Cloud Provider SDKs in Core Gateway Code**
  * *Why bad*: Bloats docker images and complicates deployments in local air-gapped secure zones.
  * *Instead*: Offload secrets sync to Kubernetes External Secrets Operator (ESO) which mounts credentials as files or env variables.
* **Anti-Pattern: Using Redis DB Index SELECTs**
  * *Why bad*: Redis/Valkey Cluster mode does not support separate logical database indices.
  * *Instead*: Separate tenant data via key prefixes: `anonreq:tenant_{tenant_id}:session_{session_id}`.

---

## 5. Scalability Considerations

| Component | At 100 users | At 10,000 users | At 1,000,000 users |
|-----------|--------------|-----------------|--------------------|
| **SSO JWT Validation** | Direct CPU decoding. | Local JWKS cached in memory to reduce Valkey hits. | Offloaded to perimeter Ingress proxy; gateway decodes simple claims. |
| **Valkey Caching** | Single node Valkey. | Sentinel master-slave setup for failover support. | Valkey Cluster with partition slot routing across shards. |
| **Database Tenancy** | Shared database filters. | SQLAlchemy Schema-Translate mapped schemas. | PostgreSQL partitions + Row-Level Security (RLS) on write-heavy tables. |
| **Secrets Rotation** | Restart container to load new keys. | Background File Watcher reloads settings in-memory. | Vault transit engine key-rotation API integration. |

---

## 6. Integration Points Summary

| New Feature / Subsystem | Integrates With | Mechanism |
|-------------------------|-----------------|-----------|
| SSO auth (`authlib`) | FastAPI Middleware Stack | Intercepts HTTP Requests, validates tokens, injects `request.state.role_principal`. |
| Multi-Tenancy Isolation | `CacheManager` & SQLAlchemy | Prefixing Valkey keys; setting `app.current_tenant_id` local parameters on database connections. |
| Valkey Cluster/Sentinel | `CacheManager` initialization | Resolves URL scheme (`redis+cluster://` / `redis+sentinel://`) to load correct async connection pool class. |
| External Secrets (ESO) | `Settings` config loader | Mounts secrets to `/vault/secrets/config.json` monitored by file watcher. |

---

## 7. New vs Modified Files

### New Files
* `src/anonreq/sso/__init__.py` — SSO package exports.
* `src/anonreq/sso/jwks.py` — Local JWKS cache management.
* `src/anonreq/sso/saml.py` — SAML auth support.
* `src/anonreq/core/config_watcher.py` — File system watcher for secret reloading.
* `src/anonreq/core/vault.py` — Direct HashiCorp Vault hvac config client.
* `templates/deployment.yaml` — Helm gateway deployment template with pod anti-affinity.
* `templates/hpa.yaml` — Helm autoscaling configuration.
* `templates/secrets.yaml` — Helm External Secrets Operator configuration.

### Modified Files
* `src/anonreq/config/__init__.py` — Add new config parameters (`SSO_PROVIDER`, `ROLE_MAPPING`, `SESSION_SEEDS`, `VAULT_ENABLED`, etc.).
* `src/anonreq/dependencies.py` — Update `auth_context` to handle SSO token claims validation.
* `src/anonreq/cache/manager.py` — Implement Sentinel & Cluster URL routing and connection pools.
* `src/anonreq/database/session.py` — Add after_transaction connection listener for tenant injection.
* `src/anonreq/main.py` — Register SSO and Tenant isolation middlewares, spin up secrets watcher thread in lifespan.

---

## 8. Build Order

1. **Phase 1: HA Cache Foundation** — Implement Sentinel/Cluster parsing in `CacheManager`, add exponential retry decorators to prevent fail-open crashes.
2. **Phase 2: Secrets & Key Versioning** — Update Pydantic Settings for versioned keys and file watch reloader.
3. **Phase 3: SSO & RBAC** — Integrate Authlib, OIDC/SAML clients, JWKS local caching, and Role claims mapping.
4. **Phase 4: Multi-Tenant RLS** — Implement tenant resolution middleware and PostgreSQL RLS session hooks.

---

## 9. Sources
* `req/requirements_v2.md` — Requirement 43 (Operational Resilience & DORA), 46 (BU Segregation).
* `src/anonreq/cache/manager.py` — Key prefixing pattern.
* `src/anonreq/middleware/rbac.py` — Role hierarchy.
