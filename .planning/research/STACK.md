# Stack Research — AnonReq v2.0 Enterprise & Deployment Moat

**Domain:** Self-hosted AI security & anonymization gateway
**Researched:** 2026-07-12
**Confidence:** HIGH

## Recommended Stack

AnonReq v2.0 introduces target features for SSO/RBAC, multi-tenant isolation, high availability, and secure cloud secrets management. The stack is carefully expanded to support these enterprise capabilities while maintaining the core gateway properties (fail-secure, no-PII-in-logs, ephemeral caching).

### Core Technologies & v2.0 Additions

| Technology / Library | Version | Purpose | Why |
|----------------------|---------|---------|-----|
| **authlib** | 1.3+ | OIDC, OAuth 2.0, & SAML 2.0 client auth | Comprehensive, RFC-compliant security library. Replaces PyJWT and python3-saml, avoiding XML parsing vulnerabilities and cryptographic redundancy. |
| **redis / redis.asyncio** | 5.0+ | Valkey Cluster / Sentinel support | The official python redis client natively handles Cluster topology updates and Sentinel master discovery for HA scaling. |
| **SQLAlchemy** | 2.0+ | Database-level multi-tenancy & RLS | Already a dependency; supports dynamic tenant context injection, PostgreSQL Row-Level Security (RLS), and scoped connection pools. |
| **hvac** | 2.1+ | Local HashiCorp Vault client | Optional runtime Vault integration library for non-Kubernetes environments. Decoupled from core dependencies. |
| **Kubernetes Helm** | v3.x | Deployment orchestrator templates | Helm v3 templates (`templates/deployment.yaml`, `templates/service.yaml`, etc.) for managing pod replicas, anti-affinity, and HPA. |

### Infrastructure & Deployment Stack

| Technology | Purpose | Notes / Rationale |
|------------|---------|-------------------|
| **PostgreSQL** | Persistent config & audit database | Supports Row-Level Security (RLS) and schema namespacing for strict multi-tenant database isolation. |
| **Valkey Cluster** | HA caching & rate-limiting | Multi-master clustering with sentinel replication failover for high reliability. |
| **Kubernetes Ingress (Nginx / Envoy)** | TLS/mTLS termination | Offloads heavy CPU-bound TLS validation and certificate processing to the cluster perimeter. |
| **External Secrets Operator (ESO)** | Secret synchronization | Decouples python code from AWS/GCP/Vault SDKs, keeping container cloud-agnostic. |

---

## Technical Decisions & Rationale

### 1. SSO & RBAC (Target: SSO-01, SSO-02, SSO-03)
* **OpenID Connect & SAML 2.0 Client**: Use **authlib** because it handles OpenID Connect JWT verification, JWKS caching, and SAML 2.0 assertions in a single, well-audited library. This prevents dependency bloat (e.g. combining `python-jose` with `python3-saml`) and mitigates XML vulnerabilities (XXE) common in standalone SAML parsers.
* **OIDC JWKS Caching**: OIDC provider JSON Web Key Sets (JWKS) are cached locally in Valkey using the `CacheManager` with a 24-hour TTL. This avoids blocking incoming API traffic on remote HTTP handshakes to the identity provider.
* **mTLS Perimeter Termination**: Offload mTLS authentication to the Kubernetes Ingress Controller (Nginx, Envoy, or Traefik). The ingress proxy validates client X.509 certificates and forwards certificate attributes (like `X-SSL-Client-Subject-DN`) as HTTP headers to FastAPI. This prevents CPU bottlenecks in Python's async event loop and shields the core container from TLS stack exploits.
* **Hierarchical RBAC mapping**: Map OIDC token claim arrays (e.g. `groups` or `roles`) directly to the existing `Role` enum in `src/anonreq/middleware/rbac.py` via a configuration map in `Settings` (e.g., `ANONREQ_ROLE_MAPPING`).

### 2. Multi-Tenant Isolation (Target: TEN-01, TEN-02)
* **PostgreSQL Row-Level Security (RLS)**: Enforce multi-tenancy at the database layer using PostgreSQL RLS policies. Dynamic tenant filters are injected into SQLAlchemy sessions via context-local variables, preventing developer omission errors (e.g., forgetting a `where tenant_id = X` clause).
* **Valkey Key Prefixing**: Segment the Valkey cache using tenant-specific key namespaces (`anonreq:tenant_{tenant_id}:{session_id}`). This enables multi-tenant ACL access control and remains compatible with Valkey Cluster (as separate Valkey logical databases are not supported in cluster mode).
* **Observability Scoping**: Custom Prometheus metrics include a `tenant_id` label for billing and resource tracking. `tenant_id` is bound to `structlog` context variables, enabling unified logging to stdout, where log routing agents (Fluent-Bit, Logstash) route logs to tenant-scoped S3/MinIO buckets.

### 3. HA/Scaling & Disaster Recovery (Target: HA-01, HA-02)
* **Valkey Cluster & Sentinel**: Modify the existing `CacheManager` to inspect the connection URL scheme. If `redis+sentinel://` or `redis+cluster://` is detected, it switches connection factories to `redis.sentinel.Sentinel` or `redis.cluster.RedisCluster` respectively.
* **Kubernetes Orchestration**: Build Helm v3 charts with pod anti-affinity rules (`kubernetes.io/hostname`) to distribute gateway pods across physical nodes, ensuring service survival during node failures.

### 4. Secrets Management & Key Rotation (Target: SEC-01, SEC-02)
* **Kubernetes External Secrets Operator (ESO)**: Use ESO to sync secrets from AWS Secrets Manager, Google Cloud Secret Manager, or HashiCorp Vault into native Kubernetes secrets. Decouples Python code from cloud SDKs, keeping container images lightweight and compatible with air-gapped deployments.
* **hvac fallback**: Maintain direct HashiCorp Vault integration using `hvac` for environments running bare-metal or single-node Docker Compose deployments.
* **Session Key Versioning**: Implement a versioned key map (`ANONREQ_SESSION_SEEDS` JSON string) in Pydantic Settings. The gateway encrypts new sessions with the latest version, but preserves read-support for active older keys within the Valkey TTL window (e.g. 1 hour).

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **authlib** | `python-jose` + `python3-saml` | Use if SAML support is completely out of scope, but `authlib` is still preferred as it supports both standard OIDC and SAML without adding dual crypto engines. |
| **mTLS at Ingress** | mTLS in-process in Python/FastAPI | Use only in single-node bare-metal deployments without an API gateway or ingress proxy. Increases container CPU usage and attack surface. |
| **PostgreSQL RLS** | Separate Database-per-Tenant | Use when strict regulatory requirements mandate physical data separation on disk. Highly expensive and complex to migrate schemas. |
| **External Secrets Operator** | AWS/GCP Cloud SDKs in python (`boto3`) | Use if Kubernetes is not the deployment target. Adds runtime weight and slows down container startup due to API handshake latency. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **PyJWT** | Flagged in v1.5 as an unnecessary dependency with security history. | `authlib` built-in cryptokey handlers. |
| **Numerical Redis DBs (`SELECT`)** | Not supported in Redis/Valkey Cluster mode; breaks scaling topology. | Prefix namespaces (`anonreq:tenant_{id}:{session}`). |
| **Direct Cloud SDKs in Core App** | Runtime bloat (`boto3` is 40MB+), introduces network failure modes during startup. | Kubernetes External Secrets Operator (ESO). |
| **XML parsers in custom SAML** | Standard python `xml.etree` is vulnerable to XXE. | `authlib` or OneLogin's verified wrappers. |

---

## Stack Patterns by Variant

**If the customer requires air-gapped deployment without external KMS:**
* Use local software-based KMS keys defined in environment secrets (`ANONREQ_SESSION_SEEDS`).
* Generate certificates locally using standard Vault instances deployed inside the secure perimeter.

**If the deployment target is AWS / GCP specific:**
* Leverage AWS EKS with AWS Secrets Manager (synced via ESO) and RDS PostgreSQL for multi-tenant storage.

---

## Version Compatibility

| Package / Tool | Version | Purpose |
|----------------|---------|---------|
| **authlib** | `==1.3.*` | OAuth/OIDC/SAML token processing |
| **redis** | `>=5.0.0` | Valkey Sentinel and Cluster support |
| **hvac** | `>=2.1.0` | Direct HashiCorp Vault client library |
| **SQLAlchemy** | `>=2.0.0` | RLS session interceptors and multi-tenant mapping |
| **Helm** | `v3.x` | Kubernetes packaging |

---

## Sources

* `req/requirements_v2.md` — Requirement 46 (Business Unit Segregation)
* `src/anonreq/cache/manager.py` — Existing Valkey key-prefixing pattern
* `src/anonreq/middleware/rbac.py` — Existing role-hierarchy dependency implementation
* `src/anonreq/core/config.py` — Core configuration settings management
* Vault transit engine docs & Kubernetes external secrets reference.

---
*Stack research for: AnonReq v2.0 Enterprise & Deployment Moat*
*Researched: 2026-07-12*
