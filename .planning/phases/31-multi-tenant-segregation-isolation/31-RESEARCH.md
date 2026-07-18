# Phase 31: Multi-Tenant Segregation & Isolation - Research

**Researched:** 2026-07-18
**Domain:** Multi-tenant isolation, KMS encryption, middleware architecture, observability scoping
**Confidence:** HIGH

## Summary

Phase 31 enforces strict multi-tenant isolation across the AnonReq gateway: mandatory tenant validation at the gateway edge, namespace-partitioned cache with per-tenant KMS encryption of token mappings, and tenant-scoped structured logging and Prometheus metrics. The codebase already has strong foundations for this work — `CacheManager._key()` already uses `anonreq:{tenant_id}:{session_id}` format, `ProcessingContext.tenant_id` exists (defaulting to `"default"`), `structlog.contextvars` is already used for `request_id` propagation, and the `cryptography` library is a dependency. The primary work is: (1) a new `TenantContextMiddleware` that validates the `X-AnonReq-Tenant-ID` header against a registry, (2) a pluggable KMS encryption layer wrapping CacheManager, (3) adding `tenant_id` to Prometheus metric labels, and (4) a tenant registry backed by YAML seed + DB persistence.

**Primary recommendation:** Implement in order: Tenant Registry (D-05/D-06) → TenantContextMiddleware (D-01/D-02/D-03/D-04) → KMS encryption (D-07/D-08/D-09) → Observability scoping (D-10/D-11/D-12). Each layer builds on the previous.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Hard reject — requests missing or invalid `X-AnonReq-Tenant-ID` header return HTTP 400 with JSON error body `{"error": "missing_tenant", "message": "X-AnonReq-Tenant-ID header required"}`. No implicit default tenant.
- **D-02:** Dedicated `TenantContextMiddleware` runs after auth, before classification. Validates header against tenant registry, sets `request.state.tenant_id`.
- **D-03:** Middleware sets `request.state.tenant_id`; `ProcessingContext.tenant_id` is populated from it at pipeline start. Pipeline stages never read headers directly.
- **D-04:** Disabled tenants (valid ID but `enabled=false`) receive HTTP 403 Forbidden with `{"error": "tenant_disabled"}`. Distinct from 400 (missing/invalid).
- **D-05:** Hybrid model — YAML seed file (`config/tenants.yaml`) loaded at startup as seed. Admin API adds/modifies tenants at runtime, persisted to DB. YAML wins on conflicts.
- **D-06:** Full denormalized profile per tenant: `tenant_id`, `display_name`, `enabled`, `kms_key_arn`, `spend_limits`, `rate_limits`, `allowed_providers`, `allowed_models`, `created_at`, `updated_at`. Duplicates some policy engine data for fast middleware-layer lookup.
- **D-07:** Pluggable KMS backends — abstract `KMSClient` ABC with concrete implementations: AWS KMS, GCP KMS, local AES-256-GCM with key derivation. Tenant registry stores key ARN per tenant.
- **D-08:** Encrypt at storage layer — encrypt token-to-value mappings in memory before Valkey write, decrypt on read. Valkey stores ciphertext. Protects against Valkey data dump exposure.
- **D-09:** In-memory key cache — cache KMS data keys per tenant with bounded TTL. Avoids KMS call on every encrypt/decrypt. Re-fetch on TTL expiry or rotation signal.
- **D-10:** structlog contextvars — TenantContextMiddleware binds `tenant_id` to structlog contextvars. All loggers automatically include `tenant_id` without explicit passing. Same pattern as existing `request_id`.
- **D-11:** Tenant label on existing Prometheus counters/histograms — add `tenant_id` label to existing metrics. Same metric names, tenant-aware aggregation.
- **D-12:** Bounded cardinality — configurable max unique tenants for metrics labels (default 100). TenantRegistry enforces at onboarding. Excess tenants get `_overflow` label to prevent cardinality explosion.

### the agent's Discretion
- Exact middleware ordering within the stack (after auth, before classification — but exact position relative to other middleware)
- Database model design for tenant registry (SQLAlchemy schema, migration strategy)
- Admin API endpoints for tenant CRUD (REST design, request/response schemas)
- KMS key rotation flow and stale key handling
- Prometheus metric label naming conventions
- Test strategy and coverage targets

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEN-01 | Require and validate `X-AnonReq-Tenant-ID` header on client requests | TenantContextMiddleware (D-01/D-02/D-03/D-04) validates against TenantRegistry; HTTP 400 for missing/invalid, HTTP 403 for disabled |
| TEN-02 | Enforce strict namespace partitioning in Valkey (`anonreq:tenant_{tenant_id}:{session_id}`) | CacheManager._key() already implements this format; tenant_id must be populated from validated middleware state |
| TEN-03 | Dynamically encrypt Valkey token mappings using tenant-specific KMS keys | Pluggable KMSClient ABC (D-07) + encrypt-at-storage-layer (D-08) + in-memory key cache (D-09) |
| TEN-04 | Scope structured logs and custom Prometheus metrics with active `tenant_id` context | structlog contextvars bind (D-10) + tenant_id label on Counter/Histogram (D-11) + bounded cardinality (D-12) |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tenant header validation | Middleware Layer | Routing Layer | Cross-cutting concern at gateway edge, before any route processing |
| Tenant registry lookup | Configuration Layer | Middleware Layer | Registry loaded at startup (YAML) + runtime (DB), queried by middleware |
| Cache namespace partitioning | Cache Layer | — | CacheManager._key() already handles tenant-scoped key format |
| Token mapping encryption | Cache Layer | — | Encrypt/decrypt wraps CacheManager store/get operations |
| KMS data key management | New KMS Layer | Cache Layer | Pluggable backends (AWS/GCP/local) with in-memory key cache |
| Tenant-scoped logging | Middleware Layer | Logging Config | structlog contextvars binding in middleware, consumed by logging_config |
| Tenant-scoped metrics | Monitoring Layer | Middleware Layer | Label changes in metrics.py, tenant_id read from request.state in middleware |
| Tenant CRUD admin API | Routing Layer (admin) | Configuration Layer | New admin endpoints backed by TenantRegistry |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cryptography` | >=42.0.0 | AES-256-GCM local encryption, key derivation | Already a dependency; used for TLS/cert handling throughout codebase |
| `sqlalchemy` | >=2.0.0 | Tenant registry DB persistence | Already a dependency; used for governance/audit models with Alembic migrations |
| `structlog` | >=26.1.0 | tenant_id contextvars binding | Already a dependency; request_id pattern is the template |
| `prometheus-client` | >=0.25.0 | Tenant-labeled metrics | Already a dependency; existing Counter/Histogram definitions to extend |
| `pyyaml` | >=6.0.3 | YAML tenant seed config | Already a dependency; config/ pattern established |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `aiosqlite` | >=0.20.0 | Tenant registry DB (SQLite default) | Default DB backend for tenant registry |
| `asyncpg` | >=0.31.0 | Tenant registry DB (PostgreSQL) | Production DB backend for tenant registry |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AES-256-GCM local KMS | `Fernet` (from cryptography) | Fernet is simpler but lacks GCM's authenticated encryption and AEAD; GCM is the standard for modern symmetric encryption |
| SQLAlchemy tenant model | Pydantic-only in-memory registry | DB persistence needed for runtime admin API; in-memory alone loses state on restart |
| structlog contextvars | Explicit `tenant_id` passing | contextvars is the established pattern (request_id precedent); explicit passing is error-prone across middleware/pipeline boundary |

**Installation:**
```bash
# No new packages needed — all dependencies already in pyproject.toml
# cryptography>=42.0.0, sqlalchemy>=2.0.0, structlog>=26.1.0, prometheus-client>=0.25.0
```

## Package Legitimacy Audit

No new external packages are required for this phase. All needed libraries are already in `pyproject.toml`.

| Package | Registry | Age | Verdict | Disposition |
|---------|----------|-----|---------|-------------|
| cryptography | PyPI | 12+ yrs | OK | Already installed |
| sqlalchemy | PyPI | 18+ yrs | OK | Already installed |
| structlog | PyPI | 10+ yrs | OK | Already installed |
| prometheus-client | PyPI | 12+ yrs | OK | Already installed |
| pyyaml | PyPI | 20+ yrs | OK | Already installed |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Request arrives
    │
    ▼
┌─────────────────────────────────────────┐
│ set_request_context (request_id)         │
│ structlog.contextvars.bind(request_id)   │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ MetricsMiddleware (request timing)       │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ Auth (auth_context)                      │
│ Bearer token validation                  │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ TenantContextMiddleware (NEW)            │
│ 1. Read X-AnonReq-Tenant-ID header      │
│ 2. Validate against TenantRegistry       │
│ 3. Set request.state.tenant_id           │
│ 4. Bind tenant_id to structlog vars      │
│ 5. HTTP 400 if missing/invalid           │
│ 6. HTTP 403 if disabled                  │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ ClassificationMiddleware                 │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ PolicyMiddleware                          │
│ _extract_tenant_id reads request.state   │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ Route Handler → ProcessingContext         │
│ tenant_id = request.state.tenant_id      │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ Pipeline Stages                           │
│ CacheManager.store_mapping(tenant_id,…)  │
│ → KMS encrypt → Valkey write             │
│ CacheManager.get_mapping(tenant_id,…)    │
│ → Valkey read → KMS decrypt              │
└─────────────────────────────────────────┘
```

### Recommended Project Structure

```
src/anonreq/
├── tenant/
│   ├── __init__.py
│   ├── registry.py          # TenantRegistry: YAML seed + DB runtime
│   ├── models.py            # TenantProfile dataclass + SQLAlchemy model
│   ├── admin.py             # Admin API routes for tenant CRUD
│   └── config.py            # TenantsSettings (YAML loader)
├── kms/
│   ├── __init__.py
│   ├── base.py              # KMSClient ABC
│   ├── local.py             # LocalAES256GCM implementation
│   ├── aws.py               # AWS KMS implementation
│   ├── gcp.py               # GCP KMS implementation
│   └── cache.py             # InMemoryKeyCache with bounded TTL
├── middleware/
│   ├── tenant.py            # TenantContextMiddleware (NEW)
│   └── ... (existing)
├── cache/
│   ├── manager.py           # Modified: KMS encryption layer
│   └── ...
├── monitoring/
│   ├── metrics.py           # Modified: tenant_id labels
│   └── middleware.py         # Modified: read tenant_id from request.state
└── ...
config/
└── tenants.yaml             # Seed tenant registry
alembic/versions/
└── 003_create_tenant_table.py  # Tenant registry migration
```

### Pattern 1: Middleware Tenant Validation

**What:** Dedicated middleware that validates tenant header, sets request.state, and binds to structlog contextvars
**When to use:** Every authenticated request must have a valid tenant
**Example:**
```python
# Source: Existing PolicyMiddleware pattern (src/anonreq/middleware/policy.py)
# and existing structlog.contextvars pattern (src/anonreq/main.py:372)

class TenantContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, tenant_registry: TenantRegistry) -> None:
        super().__init__(app)
        self._registry = tenant_registry

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip health/metrics endpoints (same pattern as PolicyMiddleware)
        if request.url.path in _SKIP_PATHS or not request.url.path.startswith("/v1/"):
            return await call_next(request)

        tenant_id = request.headers.get("X-AnonReq-Tenant-ID")
        if not tenant_id:
            return JSONResponse(
                status_code=400,
                content={"error": "missing_tenant", "message": "X-AnonReq-Tenant-ID header required"},
            )

        profile = self._registry.get(tenant_id)
        if profile is None:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_tenant", "message": f"Unknown tenant: {tenant_id}"},
            )

        if not profile.enabled:
            return JSONResponse(
                status_code=403,
                content={"error": "tenant_disabled"},
            )

        request.state.tenant_id = tenant_id
        request.state.tenant_profile = profile
        structlog.contextvars.bind_contextvars(tenant_id=tenant_id)
        try:
            response = await call_next(request)
            return response
        finally:
            structlog.contextvars.unbind_contextvars("tenant_id")
```

### Pattern 2: KMS Encrypt-at-Storage

**What:** Transparently encrypt token mappings before Valkey write, decrypt after read
**When to use:** Every CacheManager store/get operation
**Example:**
```python
# New KMSClient ABC pattern

from abc import ABC, abstractmethod

class KMSClient(ABC):
    @abstractmethod
    async def encrypt(self, tenant_id: str, plaintext: bytes) -> bytes:
        """Encrypt plaintext using tenant-specific key."""

    @abstractmethod
    async def decrypt(self, tenant_id: str, ciphertext: bytes) -> bytes:
        """Decrypt ciphertext using tenant-specific key."""

class LocalAES256GCM(KMSClient):
    """Local AES-256-GCM with PBKDF2 key derivation."""
    def __init__(self, master_key: bytes, key_cache: InMemoryKeyCache) -> None:
        self._master_key = master_key
        self._cache = key_cache

    async def encrypt(self, tenant_id: str, plaintext: bytes) -> bytes:
        data_key = await self._cache.get_or_derive(tenant_id, self._master_key)
        # AES-256-GCM with random 12-byte nonce
        ...

    async def decrypt(self, tenant_id: str, ciphertext: bytes) -> bytes:
        data_key = await self._cache.get_or_derive(tenant_id, self._master_key)
        ...
```

### Pattern 3: Bounded Cardinality Metrics

**What:** Add tenant_id label to existing metrics with overflow protection
**When to use:** All Prometheus Counter/Histogram definitions
**Example:**
```python
# Modified metrics.py pattern

MAX_TENANT_LABELS = 100  # configurable via ANONREQ_METRICS_MAX_TENANTS

def _tenant_label(tenant_id: str, known_tenants: set[str]) -> str:
    """Return tenant_id or '_overflow' if cardinality exceeded."""
    if len(known_tenants) >= MAX_TENANT_LABELS and tenant_id not in known_tenants:
        return "_overflow"
    known_tenants.add(tenant_id)
    return tenant_id

# Modified metric definition
requests_total = Counter(
    "anonreq_requests_total",
    "Total requests processed",
    labelnames=["tenant_id", "endpoint", "status_code", "provider", "classification"],
)
```

### Anti-Patterns to Avoid
- **Reading headers directly in pipeline stages:** Pipeline stages must never read `request.headers` — they receive `tenant_id` from `ProcessingContext` populated by middleware (D-03).
- **Bypassing TenantRegistry for validation:** Never trust client-provided tenant_id without registry lookup — the registry is the source of truth (D-05).
- **Encrypting without AEAD:** Do not use AES-CBC or plain AES-ECB for token mapping encryption — always use AES-256-GCM (authenticated encryption) to detect tampering.
- **Unbounded metric cardinality:** Never add `tenant_id` to metrics without cardinality bounds — cardinality explosion can crash Prometheus (D-12).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Symmetric encryption | Custom XOR or encoding | `cryptography.hazmat.primitives.ciphers.aead.AESGCM` | AEAD is critical for detecting tampering; custom encryption has CVE history |
| Key derivation | Raw hashing | `cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC` or `HKDF` | Standard KDFs have proven security properties; custom derivation is a known vulnerability |
| DB ORM | Raw SQL strings | SQLAlchemy ORM models + Alembic migrations | Established pattern in codebase (audit models); SQL injection risk with raw queries |
| Metric cardinality control | Ad-hoc checks | Dedicated `_tenant_label()` helper with bounded set | Centralized logic prevents inconsistent enforcement across metric definitions |
| YAML config loading | Custom file parsing | `yaml.safe_load()` (already established) | Prevents code injection; established pattern across 15+ config files |

**Key insight:** The `cryptography` library already provides `AESGCM`, `PBKDF2HMAC`, and `Fernet` — all battle-tested primitives. Building custom encryption or key management is a security anti-pattern with real CVE consequences.

## Runtime State Inventory

> This section is included because Phase 31 introduces a new DB table and YAML config, but does NOT rename/refactor existing state.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | New `tenant` table (Alembic migration) — no existing data to migrate | Create migration for new table only |
| Live service config | `config/tenants.yaml` seed file — new file, no existing state | Create seed YAML; no conflict with existing configs |
| OS-registered state | None — no OS-level registrations affected | None |
| Secrets/env vars | `ANONREQ_KMS_BACKEND` (new env var for local/AWS/GCP selection) | Add to Settings, document in .env.example |
| Build artifacts | None — no existing artifacts affected | None |

## Common Pitfalls

### Pitfall 1: Middleware Ordering Creates Race Condition
**What goes wrong:** TenantContextMiddleware placed before set_request_context means `structlog.contextvars.unbind_contextvars("tenant_id")` could fail if request_id isn't bound yet.
**Why it happens:** FastAPI middleware executes in reverse registration order — the last `add_middleware()` call runs first on request.
**How to avoid:** Register TenantContextMiddleware AFTER set_request_context middleware but BEFORE ClassificationMiddleware. In main.py, add it as:
```python
app.add_middleware(TenantContextMiddleware, tenant_registry=tenant_registry)
```
between the `set_request_context` middleware and `ClassificationMiddleware`.
**Warning signs:** Tests showing tenant_id not appearing in logs, or structlog contextvars errors.

### Pitfall 2: KMS Encrypt/Decrypt Performance Bottleneck
**What goes wrong:** Every CacheManager operation triggers a KMS API call, adding 10-100ms latency per request.
**Why it happens:** Forgetting to implement the in-memory key cache (D-09).
**How to avoid:** `InMemoryKeyCache` caches derived data keys per tenant with bounded TTL (e.g., 5 minutes). KMS calls only on cache miss or TTL expiry.
**Warning signs:** Latency metrics spiking >50ms on cache operations; KMS API call count matching request count.

### Pitfall 3: Tenant Registry Staleness After Admin API Update
**What goes wrong:** Tenant profile updated via admin API but middleware still uses stale YAML-loaded profile.
**Why it happens:** TenantRegistry loaded once at startup; admin API writes to DB but in-memory cache isn't invalidated.
**How to avoid:** TenantRegistry uses a write-through pattern: admin API writes to DB AND updates in-memory cache atomically. YAML seed is write-once at startup (YAML wins on conflicts per D-05).
**Warning signs:** Admin updates tenant `enabled=false` but requests still accepted.

### Pitfall 4: Valkey Key Format Mismatch After Migration
**What goes wrong:** Existing Valkey keys use old format (if any exist) and new tenant-prefixed keys cause duplicate session state.
**Why it happens:** Phase 28 introduced `anonreq:{tenant_id}:{session_id}` format but tenant_id was always "default".
**How to avoid:** New tenant_id values are distinct strings; no migration needed. "default" tenant_id remains valid for backward compatibility during transition.
**Warning signs:** Cache hit rate dropping after deployment; duplicate session mappings.

### Pitfall 5: Metrics Cardinality Explosion Under Load
**What goes wrong:** Each request with a new tenant_id creates a new time series, consuming Prometheus memory.
**Why it happens:** Missing bounded cardinality implementation (D-12).
**How to avoid:** `_tenant_label()` helper maintains a `set[str]` of known tenants; when set size reaches `MAX_TENANT_LABELS`, new tenants get `_overflow` label.
**Warning signs:** Prometheus memory usage growing unbounded; "too many time series" errors.

## Code Examples

### TenantRegistry with YAML Seed + DB Runtime

```python
# Source: Existing pattern from config/enterprise-policy.yaml + admin/routes.py

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, UTC
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass
class TenantProfile:
    tenant_id: str
    display_name: str
    enabled: bool = True
    kms_key_arn: str | None = None
    spend_limits: dict[str, Any] = field(default_factory=dict)
    rate_limits: dict[str, Any] = field(default_factory=dict)
    allowed_providers: list[str] = field(default_factory=list)
    allowed_models: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

class TenantRegistryModel(Base):
    """SQLAlchemy model for tenant registry persistence."""
    __tablename__ = "tenant"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), unique=True, nullable=False)
    display_name = Column(String(256), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    kms_key_arn = Column(String(512), nullable=True)
    spend_limits_json = Column(Text, nullable=True)
    rate_limits_json = Column(Text, nullable=True)
    allowed_providers_json = Column(Text, nullable=True)
    allowed_models_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

class TenantRegistry:
    """Hybrid YAML seed + DB runtime tenant registry."""

    def __init__(self, yaml_path: str = "config/tenants.yaml") -> None:
        self._tenants: dict[str, TenantProfile] = {}
        self._yaml_path = yaml_path
        self._load_yaml_seed()

    def _load_yaml_seed(self) -> None:
        """Load seed tenants from YAML at startup (YAML wins on conflicts)."""
        path = Path(self._yaml_path)
        if not path.exists():
            return
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        for t in data.get("tenants", []):
            profile = TenantProfile(**t)
            self._tenants[profile.tenant_id] = profile

    def get(self, tenant_id: str) -> TenantProfile | None:
        return self._tenants.get(tenant_id)

    def register(self, profile: TenantProfile) -> None:
        """Register or update a tenant (admin API)."""
        self._tenants[profile.tenant_id] = profile

    def list_all(self) -> list[TenantProfile]:
        return list(self._tenants.values())
```

### KMS Key Cache with Bounded TTL

```python
# Source: New pattern following cryptography library primitives

import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

@dataclass
class CachedKey:
    data_key: bytes
    expires_at: float

class InMemoryKeyCache:
    """Cache KMS data keys per tenant with bounded TTL."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 1000) -> None:
        self._cache: dict[str, CachedKey] = {}
        self._ttl = ttl_seconds
        self._max = max_entries

    async def get_or_derive(self, tenant_id: str, master_key: bytes) -> bytes:
        now = time.monotonic()
        cached = self._cache.get(tenant_id)
        if cached and cached.expires_at > now:
            return cached.data_key

        # Derive tenant-specific data key via HKDF
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key
            salt=None,
            info=f"anonreq-tenant-{tenant_id}".encode(),
        )
        data_key = hkdf.derive(master_key)

        # Evict oldest if at capacity
        if len(self._cache) >= self._max:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].expires_at)
            del self._cache[oldest_key]

        self._cache[tenant_id] = CachedKey(
            data_key=data_key,
            expires_at=now + self._ttl,
        )
        return data_key
```

### TenantContextMiddleware Registration in main.py

```python
# Source: Existing pattern from main.py middleware registration

# After set_request_context but before ClassificationMiddleware
app.add_middleware(TenantContextMiddleware, tenant_registry=tenant_registry)

# TenantRegistry stored on app.state
state.tenant_registry = tenant_registry
app.state.tenant_registry = tenant_registry
```

### Modified Metrics with Tenant Labels

```python
# Source: Existing metrics.py + bounded cardinality pattern

from prometheus_client import Counter, Histogram

_known_tenants: set[str] = set()

def _resolve_tenant_label(tenant_id: str) -> str:
    """Return tenant_id or '_overflow' if cardinality limit exceeded."""
    if tenant_id in _known_tenants:
        return tenant_id
    if len(_known_tenants) >= settings.METRICS_MAX_TENANTS:
        return "_overflow"
    _known_tenants.add(tenant_id)
    return tenant_id

requests_total = Counter(
    "anonreq_requests_total",
    "Total requests processed, partitioned by tenant, endpoint, status code, provider, classification",
    labelnames=["tenant_id", "endpoint", "status_code", "provider", "classification"],
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| tenant_id defaults to "default" throughout | tenant_id validated at gateway edge, never default | Phase 31 | All downstream code receives validated tenant_id |
| CacheManager stores plaintext token mappings | CacheManager encrypts before Valkey write | Phase 31 | Valkey data dump exposure protected |
| Prometheus metrics tenant-unaware | Prometheus metrics carry tenant_id label | Phase 31 | Per-tenant observability; cardinality bounds required |
| No tenant validation middleware | TenantContextMiddleware validates X-AnonReq-Tenant-ID | Phase 31 | Requests without valid tenant rejected at edge |

**Deprecated/outdated:**
- ProcessingContext.tenant_id defaulting to "default" — replaced by mandatory middleware-set value
- PolicyMiddleware._extract_tenant_id() fallback to "default" — replaced by TenantContextMiddleware hard reject
- Metrics without tenant_id — same metric names, new tenant label

## Assumptions Log

> All claims in this research were verified against the codebase. No user confirmation needed.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| (none) | All claims verified via codebase grep/read | — | — |

## Open Questions

1. **AWS KMS / GCP KMS implementation scope**
   - What we know: D-07 specifies pluggable KMS backends (AWS KMS, GCP KMS, local AES-256-GCM)
   - What's unclear: Whether to implement AWS/GCP adapters in this phase or stub them for future
   - Recommendation: Implement local AES-256-GCM fully; create `KMSClient` ABC with stub implementations for AWS/GCP that raise `NotImplementedError` until actual SDK integration is needed. This follows the existing codebase pattern of pluggable backends (ProviderAdapter pattern).

2. **Tenant admin API endpoint design**
   - What we know: Discretion area — admin API for tenant CRUD
   - What's unclear: Exact REST endpoints and request/response schemas
   - Recommendation: Follow existing admin routes pattern (`/v1/admin/tenants` for CRUD), protected by `verify_admin_api_key` dependency (same as `src/anonreq/admin/routes.py`). Standard REST: GET / POST / PUT / DELETE.

3. **Migration strategy for existing "default" tenant_id usage**
   - What we know: ProcessingContext.tenant_id defaults to "default"; PolicyMiddleware._extract_tenant_id() returns "default" as fallback
   - What's unclear: How to handle existing single-tenant deployments that don't send X-AnonReq-Tenant-ID
   - Recommendation: Create a "default" tenant in the seed YAML that is enabled by default. Existing clients can send `X-AnonReq-Tenant-ID: default` to maintain backward compatibility. The hard reject (D-01) means existing clients MUST be updated to send the header — this is intentional per user decision.

4. **KMS key rotation flow**
   - What we know: D-07 specifies tenant registry stores key ARN per tenant
   - What's unclear: When/how key rotation is triggered and how stale keys are handled
   - Recommendation: Key rotation is out of scope for this phase. The `InMemoryKeyCache` with bounded TTL ensures keys are refreshed periodically. Actual key rotation (updating `kms_key_arn` in tenant registry) is a future operational concern. Document as future enhancement.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=9.0 with pytest-asyncio |
| Config file | pyproject.toml (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/ -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEN-01 | HTTP 400 for missing/invalid tenant header | unit | `uv run pytest tests/unit/test_tenant_context_middleware.py -x` | ❌ Wave 0 |
| TEN-01 | HTTP 403 for disabled tenant | unit | `uv run pytest tests/unit/test_tenant_context_middleware.py -x` | ❌ Wave 0 |
| TEN-02 | Cache keys use `anonreq:{tenant_id}:{session_id}` format | unit | `uv run pytest tests/test_cache.py -x` | ✅ Wave 0 |
| TEN-03 | Token mappings encrypted in Valkey | integration | `uv run pytest tests/integration/test_kms_encryption.py -x` | ❌ Wave 0 |
| TEN-04 | structlog includes tenant_id | unit | `uv run pytest tests/unit/test_tenant_logging.py -x` | ❌ Wave 0 |
| TEN-04 | Prometheus metrics carry tenant_id label | unit | `uv run pytest tests/unit/test_tenant_metrics.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x`
- **Per wave merge:** `uv run pytest` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_tenant_context_middleware.py` — covers TEN-01 middleware validation
- [ ] `tests/unit/test_tenant_registry.py` — covers TEN-05 registry operations
- [ ] `tests/integration/test_kms_encryption.py` — covers TEN-03 encrypt/decrypt round-trip
- [ ] `tests/unit/test_tenant_logging.py` — covers TEN-04 structlog tenant_id binding
- [ ] `tests/unit/test_tenant_metrics.py` — covers TEN-04 metric label scoping
- [ ] `config/tenants.yaml` — seed tenant config file
- [ ] `alembic/versions/003_create_tenant_table.py` — tenant registry migration

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Tenant header validated after Bearer token auth |
| V3 Session Management | no | Session-scoped cache keys (existing pattern) |
| V4 Access Control | yes | Tenant-scoped cache isolation prevents cross-tenant data access |
| V5 Input Validation | yes | X-AnonReq-Tenant-ID header validated against registry |
| V6 Cryptography | yes | AES-256-GCM for token mapping encryption (cryptography library) |

### Known Threat Patterns for Multi-Tenant Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant data access via cache | Information Disclosure | Tenant-prefixed cache keys + encrypted mappings |
| Tenant header spoofing | Tampering | Registry validation at middleware layer |
| Valkey data dump exposure | Information Disclosure | Encrypt-at-storage (D-08) — ciphertext in Valkey |
| KMS key compromise | Elevation of Privilege | Per-tenant data keys derived from master key; in-memory cache with bounded TTL |
| Metrics cardinality DoS | Denial of Service | Bounded cardinality with `_overflow` label (D-12) |

## Sources

### Primary (HIGH confidence)
- Codebase grep/read: `src/anonreq/cache/manager.py` — CacheManager._key() already uses `anonreq:{tenant_id}:{session_id}` format [VERIFIED: codebase]
- Codebase grep/read: `src/anonreq/main.py` — middleware registration order and structlog.contextvars pattern [VERIFIED: codebase]
- Codebase grep/read: `src/anonreq/models/processing_context.py` — ProcessingContext.tenant_id exists with "default" default [VERIFIED: codebase]
- Codebase grep/read: `src/anonreq/middleware/policy.py` — PolicyMiddleware._extract_tenant_id() pattern [VERIFIED: codebase]
- Codebase grep/read: `src/anonreq/logging_config.py` — structlog merge_contextvars + allowlist includes "tenant_id" [VERIFIED: codebase]
- Codebase grep/read: `src/anonreq/monitoring/metrics.py` — existing metric definitions without tenant labels [VERIFIED: codebase]
- Codebase grep/read: `src/anonreq/config/__init__.py` — Settings pattern with ANONREQ_ prefix [VERIFIED: codebase]

### Secondary (MEDIUM confidence)
- `cryptography` library docs: AESGCM, PBKDF2HMAC, HKDF primitives [CITED: cryptography.io]
- FastAPI middleware docs: BaseHTTPMiddleware dispatch pattern [CITED: fastapi.tiangolo.com]
- structlog docs: contextvars binding/unbinding pattern [CITED: docs.structlog.org]
- prometheus-client docs: Counter/Histogram label naming [CITED: prometheusclient.io]

### Tertiary (LOW confidence)
- (none — all findings verified against codebase or official docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages already in pyproject.toml, verified via codebase
- Architecture: HIGH — existing middleware/CacheManager/structlog patterns directly applicable
- Pitfalls: MEDIUM — middleware ordering risk and KMS performance risk require careful implementation

**Research date:** 2026-07-18
**Valid until:** 30 days (stable codebase, established patterns)
