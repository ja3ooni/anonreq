# Pitfalls, Security Risks, and Warnings: Milestone v2.0 (Enterprise & Deployment Moat)

This document analyzes the common pitfalls, security vulnerabilities, and architectural warnings associated with implementing the enterprise features of Milestone v2.0 in the **AnonReq** gateway: **SSO/RBAC**, **Multi-Tenancy**, **High Availability (HA) & Scaling**, and **Secrets Management**.

---

## 1. Single Sign-On (SSO) & Role-Based Access Control (RBAC)

Implementing enterprise SSO and fine-grained authorization within a high-throughput, low-latency API gateway like AnonReq presents major security and performance risks.

### Pitfalls & Security Risks
1. **Identity vs. Authorization Conflation (Cross-Tenant Escalation)**
   * *Risk*: Relying solely on identity provider (IdP) groups or claims to determine resource access. In a multi-tenant environment, if Tenant A's user possesses an `administrator` role claim, a naive endpoint check (`if user.role == 'administrator'`) could grant them admin privileges over Tenant B's configuration if the tenant context is not strictly bound to the authorization check.
   * *Warning*: Never perform authorization checks without passing the current validated `tenant_id` context.
2. **Cryptographic Overhead and Unvalidated JWTs**
   * *Risk*: Validating JWT signatures on every inbound request requires fetching and parsing JWKS (JSON Web Key Sets) from the IdP. Doing this synchronously or per-request introduces massive latency and risks blocking the event loop. Conversely, failing to validate JWT signatures, expiration (`exp`), audience (`aud`), or issuer (`iss`) to "save performance" permits token-forgery attacks.
3. **Hardcoded Authorization Rules**
   * *Risk*: Embedding RBAC logic directly in route functions (e.g., `if role in ['admin', 'operator']`) makes compliance audits (such as ISO 42001 or DORA) extremely difficult, increases code fragility, and fails to handle dynamic governance requirements like Chinese Wall policies (Req 46).

### Opinionated Stack & Architecture Decisions
* **Use `PyJWT` (with `cryptography`) & LRU Cache for JWKS**: Do not use heavy all-in-one OIDC frameworks that introduce unnecessary middleware overhead. Parse JWTs using `PyJWT` and implement an in-memory, TTL-cached JWKS client with a background refresher thread (or async task) to avoid hitting the IdP on every request.
* **Use `OpenFGA` (via `openfga-sdk`) for Fine-Grained Authorization**: To implement complex relationship-based access controls (ReBAC) like business unit segregation (Req 46) and Chinese Wall policies, delegate authorization to an OpenFGA sidecar. This decouples policy rules from FastAPI code and satisfies the auditability requirements of ISO 42001 and DORA.
* **Use FastAPI Dependencies for Enforcement**: Enforce authentication and authorization using FastAPI’s dependency injection hierarchy. Define a `get_current_tenant_admin` dependency that resolves the tenant context and verifies the user's role before routing execution.

---

## 2. Multi-Tenancy

AnonReq requires strict data isolation between tenants, especially since it intercepts and tokenizes highly sensitive PII/PHI in financial and regulated sectors.

### Pitfalls & Security Risks
1. **Implicit Data Leakage in Shared Schemas**
   * *Risk*: When using a shared database with a `tenant_id` column, the omission of a `WHERE tenant_id = :tenant_id` clause in a single query results in catastrophic cross-tenant data leakage. Relying on developer vigilance to write this clause on every database operation is a known failure mode.
2. **Session Variable Contamination in Connection Pools**
   * *Risk*: In shared-database, separate-schema architectures, routing is typically achieved by setting a session-level parameter (e.g., `SET search_path TO tenant_schema`). If a connection is returned to the connection pool without resetting this parameter, the next tenant using that connection will execute queries against the previous tenant's schema.
3. **Connection Pool Exhaustion (Isolated DB Strategy)**
   * *Risk*: Maintaining an isolated database per tenant means the gateway must maintain a separate connection pool for every tenant. As the tenant count scales to hundreds or thousands, the gateway will exhaust the maximum connection limits of the database servers, leading to service degradation.
4. **Linear Migration Bottlenecks**
   * *Risk*: Running migrations sequentially across all tenant schemas during deployment blocks deployment pipelines, violates maintenance windows, and risks partial-failures where some tenants are migrated and others fail.

### Opinionated Stack & Architecture Decisions
* **Use PostgreSQL Schema-based Isolation via SQLAlchemy `execution_options`**: Implement a shared database with tenant-specific schemas. Use SQLAlchemy’s `schema_translate_map` or dynamic engine connection routing combined with FastAPI's `ContextVar`-based middleware to set the correct schema dynamically.
* **Enforce Row-Level Security (RLS) as a Fail-Safe**: Even if using separate schemas or tenant filters, configure PostgreSQL Row-Level Security (RLS) on all multi-tenant tables. This ensures the database itself rejects queries that violate tenant boundaries.
* **Mandate `pool_pre_ping=True` and Dynamic Connection Cleanups**: Configure SQLAlchemy engines to verify connection health and explicitly reset connection parameters (like `search_path` or active transactions) upon returning connections to the pool.
* **Implement Asynchronous, Parallelized Alembic Migrations**: Parallelize database schema migrations using a task runner or custom orchestration script that runs migrations across tenant schemas in chunks, ensuring idempotency and transaction safety.

---

## 3. High Availability (HA) & Scaling

AnonReq must remain resilient and maintain high availability while processing streaming payloads (SSE) and managing ephemeral token mappings in-memory.

### Pitfalls & Security Risks
1. **Event Loop Blocking in NER Pipeline**
   * *Risk*: Microsoft Presidio Analyzer and local Regex matching engines perform heavy CPU-bound operations. If these operations are run directly in FastAPI's main async event loop, the loop will freeze, causing timeouts for all concurrent requests and breaching processing overhead SLOs (Req 24).
2. **SSE Connection and File Descriptor Exhaustion**
   * *Risk*: Server-Sent Events (SSE) keep HTTP connections open for the duration of the LLM stream. Naive server configurations will quickly exhaust OS file descriptors. Furthermore, standard reverse proxies (like Nginx) buffer responses by default, which breaks SSE streams by accumulating chunks instead of forwarding them immediately.
3. **Redis/Valkey Failover Latency & Connection Flooding**
   * *Risk*: If the primary Valkey node fails, a Sentinel failover takes time. During this failover window, a naive Redis client will throw connection errors, causing the gateway to fail closed and return 5xx errors to clients (Req 22). When Valkey recovers, a "thundering herd" of reconnecting FastAPI instances can overwhelm the database.

### Opinionated Stack & Architecture Decisions
* **Offload NER to Worker Pools (`asyncio.to_thread` or Process Pools)**: Execute Microsoft Presidio and Regex scanning inside a ProcessPoolExecutor or via `asyncio.to_thread` to ensure CPU-bound tokenization does not block FastAPI's ASGI event loop.
* **Use `redis.asyncio.sentinel.Sentinel` with Exponential Backoff and Jitter**: Connect to Valkey using a Sentinel-aware connection pool. Implement explicit retry logic with exponential backoff and randomized jitter to handle connection errors gracefully during failover, preventing a thundering herd on Valkey.
* **Disable Reverse Proxy Buffering for SSE Paths**: Configure Nginx/ingress rules specifically for the gateway streaming routes to use `proxy_buffering off;`, `proxy_cache off;`, and set high `proxy_read_timeout` thresholds.
* **Synchronize State via Valkey Pub/Sub**: To support features like the emergency kill-switch (Req 29) across horizontally scaled gateway instances, use Valkey Pub/Sub to broadcast state changes to all instances, avoiding in-memory state desynchronization.

---

## 4. Secrets Management

AnonReq handles highly sensitive API keys (OpenAI, Anthropic, Gemini) and tenant-specific database encryption keys. Compromise of these secrets violates DORA and compliance policies.

### Pitfalls & Security Risks
1. **Global Environment Variable Leakage**
   * *Risk*: Storing secrets in standard environment variables makes them globally accessible to any subprocess spawned by the Python process. If a third-party dependency is compromised (e.g., supply chain vulnerability), an attacker can easily read `os.environ` and exfiltrate all secrets.
2. **Accidental Logging of Configuration and Secret Objects**
   * *Risk*: Standard logging frameworks and crash reporters (like Sentry or local logs) print configuration objects or variables when exceptions occur. Raw API keys or connection strings can easily slip into structured logs.
3. **Static Secrets and Lack of Rotation**
   * *Risk*: Hardcoded secrets or configurations that require a service restart to rotate cause downtime and increase the window of opportunity for leaked credentials.

### Opinionated Stack & Architecture Decisions
* **Use HashiCorp Vault Agent Sidecar Pattern**: Do not implement complex Vault client code directly inside FastAPI. Deploy the Vault Agent as a sidecar container in Kubernetes. The agent authenticates, retrieves secrets, handles token renewal, and writes secrets to a shared, memory-backed volume (`emptyDir`).
* **Leverage `pydantic-settings` with File Watcher for Hot-Reloading**: Configure AnonReq to read secrets from the shared volume. Use a background file watcher (such as `watchdog`) to detect when the Vault Agent updates secret files and trigger an atomic, in-memory config reload (Req 11) without restarting the gateway.
* **Enforce Pydantic `SecretStr` for Sensitive Fields**: Declare all secrets, database credentials, and tokenization keys as `SecretStr` instead of plain `str` in configuration models. This automatically redacts the values (replacing them with `**********`) when serialized, printed, or logged.
* **Isolate Subprocesses**: Ensure any external processes (like Presidio Analyzer) run as isolated containers with their own least-privilege service accounts, preventing them from accessing the Gateway container's secrets.

---

## Summary Checklist for Milestone v2.0 Architecture

| Category | High-Risk Pitfall | Mitigation / Architecture Standard |
| :--- | :--- | :--- |
| **SSO/RBAC** | Cross-tenant admin privileges via fake claims | Enforce `tenant_id` context validation on every AuthZ check; offload fine-grained rules to `OpenFGA`. |
| **Multi-Tenancy** | Developer omission of tenant filters | Use PostgreSQL Schema isolation with SQLAlchemy routing; configure Row-Level Security (RLS) as a database-level safety net. |
| **HA/Scaling** | Presidio blocking the main ASGI thread | Offload CPU-bound PII analysis to worker threads or a dedicated process pool. |
| **HA/Scaling** | Interrupted SSE streams | Disable proxy buffering and configure Sentinel-aware Redis client with backoff retries. |
| **Secrets** | Leaked env vars in logs/subprocess memory | Use Vault Agent sidecar to mount secrets as files; bind settings to Pydantic `SecretStr` for auto-redaction. |
