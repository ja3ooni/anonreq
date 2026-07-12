# Project Research Summary

**Project:** AnonReq
**Domain:** Self-hosted AI security & anonymization gateway
**Researched:** 2026-07-12
**Confidence:** HIGH

## Executive Summary

AnonReq is a self-hosted AI security and anonymization gateway designed to sit between enterprise applications and external or local LLM APIs. Its primary mission is to detect, redact, and tokenise sensitive data (PII, PHI, financial data) before it leaves the customer’s secure boundary, and restore it on the response path. While version 1.0/1.5 established the core high-performance in-memory anonymization pipeline and engineering hygiene, Milestone v2.0 establishes the commercial enterprise moat. This is achieved by introducing enterprise-grade Single Sign-On (SSO) and Role-Based Access Control (RBAC), robust multi-tenant isolation, high availability (HA) scaling, and cloud-native secrets management.

The recommended approach for v2.0 focuses on integrating standard compliance libraries and offloading heavy network/cryptographic concerns to the perimeter infrastructure, keeping the core gateway lightweight and fast. Key stacks include `authlib` for OIDC/SAML token processing, PostgreSQL Row-Level Security (RLS) for schema-based data isolation, and `redis.asyncio` Sentinel/Cluster integration for caching failover. High-throughput stream processing is handled entirely in-memory to prevent local disk writes.

The primary architectural risk is cross-tenant data/privilege leaks and performance degradation during CPU-heavy PII analysis or synchronous network calls. These are mitigated by enforcing dynamic `tenant_id` context propagation at every layer, offloading CPU-bound NLP tasks to dedicated worker pools, caching JWKS public keys in Valkey, and terminating mTLS/TLS verification at the Ingress controller.

## Key Findings

### Recommended Stack

The v2.0 stack expands AnonReq's capabilities to include enterprise authentication, multi-tenant isolation, and Kubernetes orchestration while maintaining fail-secure, ephemeral, and zero-PII logging principles. The stack avoids custom cryptographic implementations and standardizes on well-audited, industry-accepted libraries. Cloud SDK dependencies are minimized within the core application to ensure lightweight, cloud-agnostic, and air-gapped compatibility.

**Core technologies:**
- **authlib (v1.3+):** Standard OIDC, OAuth 2.0, and SAML 2.0 client authentication. It replaces PyJWT and python3-saml to prevent XML parsing vulnerabilities and cryptographic redundancy.
- **redis / redis.asyncio (v5.0+):** Natively supports Valkey Cluster topology updates and Sentinel master discovery for HA cache scaling.
- **SQLAlchemy (v2.0+):** Manages dynamic tenant context injection, PostgreSQL Row-Level Security (RLS) policies, and scoped connection pools.
- **Kubernetes Helm (v3.x):** Provides standard orchestrator templates (Deployment, Service, HPA) to manage pod replicas, anti-affinity, and scaling.
- **hvac (v2.1+):** Serves as a local HashiCorp Vault client fallback for non-Kubernetes or bare-metal environments.

### Expected Features

Milestone v2.0 structures features into three layers to balance standard enterprise compliance with advanced commercial differentiators, while steering clear of bloated, non-scalable implementations.

**Must have (table stakes):**
- **OIDC JWT Verification & mTLS Auth:** Secure SSO integration and machine-to-machine admin client authentication.
- **Tenant Context Scoping & Valkey Isolation:** Identifying tenants via headers, prefixing Valkey keys, and isolating caches.
- **Stateless Gateway Tier & Valkey HA:** Zero-affinity design behind L4/L7 load balancers; support for Valkey Sentinel/Cluster.
- **Enterprise KMS Integration:** Retrieving secrets at startup (Vault, AWS Secrets Manager) and caching them in-memory only.

**Should have (competitive):**
- **Dynamic Role Mapping & Just-In-Time (JIT) Provisioning:** Dynamic claims-to-role mappings from IdP tokens.
- **Resource Limits & Spend Controls:** Tenant-level rate limiting (RPM/TPM) and budget tracking with fallback routing.
- **Adaptive Failover Recovery:** Sentinel failovers in under 30 seconds with client retries.
- **Secrets Hot-Reloading & Graceful Key Rotation:** Watcher detecting secret files changes to reload configurations atomically in-memory; keeping old keys active for a 300s grace window.

**Defer (v2+):**
- **Direct SAML 2.0 XML Parsing:** Mandate external identity proxies to avoid security debt.
- **Combined Raw Logs:** Raw log payloads must never be combined across tenants.
- **Gateway-Level Billing Integration:** Out of scope for the core gateway layer.

### Architecture Approach

The architecture uses a FastAPI-based middleware stack to establish request contexts (IDs, tenant contexts, and authenticated principals) before routing to handlers. It offloads TLS/mTLS termination to Ingress proxies, translates tenant contexts into database session connection settings (PostgreSQL RLS) and Valkey key prefixes (`anonreq:tenant_{id}:{session}`), and handles secrets via external orchestrators (ESO) that write to files watched for hot-reloads.

**Major components:**
1. **SSOAuthMiddleware & TenantContextMiddleware:** Validate tokens, resolve role permissions, and bind `tenant_id` to async ContextVars.
2. **CacheManager:** Automatically routes requests to standard, Cluster, or Sentinel Valkey pools, applying tenant prefixes and exponential backoff retry wrappers.
3. **SQLAlchemy Connection Interceptor:** Runs `SET LOCAL app.current_tenant_id` at transaction start to trigger PostgreSQL Row-Level Security.
4. **watchdog Configuration Watcher:** Monitors shared volumes for secret updates to reload Pydantic Settings atomically in-memory.

### Critical Pitfalls

1. **Identity vs. Tenant Authorization Conflation (Cross-Tenant Escalation):** Checking role flags (e.g., `user.role == 'administrator'`) without incorporating the `tenant_id` context lets users escalate access across tenants. Enforce tenant-context boundaries on all authorization checks and offload fine-grained rules to `OpenFGA`.
2. **Synchronous JWKS Public Key Fetches:** Querying the IdP's JWKS endpoint during every user request introduces network blocks that crash FastAPI's event loop. Mitigate this by caching JWKS public keys in Valkey with a 24-hour TTL and updating them asynchronously.
3. **Implicit Data Leakage in Shared Schemas:** Relying on developers to remember `WHERE tenant_id = X` clauses is highly error-prone. Use schema-based isolation or PostgreSQL Row-Level Security (RLS) policies as an automated database-level safety net.
4. **Event Loop Blocking in CPU-bound NLP/NER Pipeline:** Running Microsoft Presidio and Regex scanning directly in FastAPI's main async event loop blocks concurrent network requests, degrading latency. Offload these tasks to process/thread pools using `asyncio.to_thread`.
5. **Connection Pool Exhaustion:** Spinning up separate connection pools per tenant under an isolated database strategy quickly exhausts database limits. Instead, share connection pools and dynamically switch schemas or apply RLS.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: High Availability Cache & Resilience
**Rationale:** Establishing a resilient, HA-aware connection pool prevents gateway downtime and ensures caching logic (which underlies all state/token mappings) is fail-safe.
**Delivers:** Sentinel & Cluster integration in `CacheManager` with exponential retry wrappers.
**Addresses:** Stateless Gateway Tier, Valkey HA, and Adaptive Failover features.
**Avoids:** Gateway failures or bypassed anonymization during Valkey reelection.

### Phase 2: Secure Configuration & Secrets Management
**Rationale:** Configuring settings to load from secure volumes allows subsequent phases (SSO/Tenancy) to ingest credentials safely without service restarts.
**Delivers:** Versioned key decryption maps, `watchdog`-based hot-reloading configurations, and Pydantic `SecretStr` integration.
**Uses:** `watchdog`, `pydantic-settings`, and optionally `hvac` fallback.
**Implements:** Secrets File Watcher and Vault Configuration Provider.

### Phase 3: Enterprise Authentication & RBAC
**Rationale:** Securing the administrative plane with SSO/RBAC establishes access control boundaries before multi-tenant data structures are exposed.
**Delivers:** `authlib`-based OIDC/SAML integration, JWKS cache management, and mTLS subject DN parsing.
**Uses:** `authlib` client, local JWKS caching in Valkey.
**Implements:** `SSOAuthenticationMiddleware` and role-based route decorators.

### Phase 4: Multi-Tenant Schema & RLS Isolation
**Rationale:** Enforces strict data segregation at both the database and cache layers using the authenticated tenant contexts established in Phase 3.
**Delivers:** `TenantContextMiddleware`, tenant-prefixed Valkey caches, SQLAlchemy checkout hooks, and PostgreSQL RLS migration scripts.
**Uses:** SQLAlchemy `after_transaction_create` hooks, PostgreSQL RLS.
**Implements:** Tenant Isolation Middleware and Database RLS interceptors.

### Phase Ordering Rationale

- **Infrastructure First:** Establishing the HA cache (Valkey) and secrets loading foundation ensures the runtime is stable, secure, and ready to ingest credentials before authentication logic is added.
- **Authentication Before Authorization:** SSO and mTLS verify *who* is accessing the gateway and *which* tenant they represent, which is required to filter data scopes (Multi-Tenancy) in the final phase.
- **Fail-Secure Architecture:** Grouping the Sentinel/Cluster connection logic with exponential retries prevents downstream security bypasses, directly mitigating the "fail-open" pitfall.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (Multi-Tenant Schema & RLS Isolation):** Migrations across dynamic tenant schemas via Alembic require parallelized transaction handling to prevent locks and performance degradation.
- **Phase 3 (Enterprise Authentication & RBAC):** Mapping complex corporate OIDC groups to hierarchical roles under Chinese Wall policies requires defining robust claim-parsing rules.

Phases with standard patterns (skip research-phase):
- **Phase 1 (High Availability Cache & Resilience):** `redis.asyncio` provides native support for Sentinel and Cluster pools, meaning integration follows standard, well-documented patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | The choices of `authlib`, `redis.asyncio`, SQLAlchemy RLS, and ESO sidecars align with industry best practices and are highly documented. |
| Features | HIGH | Table stakes, differentiators, and out-of-scope features are explicitly aligned with the requirements. |
| Architecture | HIGH | Request flows, middlewares, and database interceptor hooks map cleanly to FastAPI and SQLAlchemy APIs. |
| Pitfalls | HIGH | Specific execution pitfalls (like event loop blocking and pool exhaustion) are identified with concrete code-level mitigations. |

**Overall confidence:** HIGH

### Gaps to Address

- **OpenFGA Sidecar Integration:** While identified as a mitigation for complex ReBAC/Chinese Wall rules, the exact deployment structure and authorization schemas require detailed validation in Phase 3.
- **Parallelized Alembic Migrations:** Standard Alembic operates sequentially; orchestration scripts for parallel migrations across dynamic tenant schemas need to be prototyped to ensure idempotency.

## Sources

### Primary (HIGH confidence)
- `src/anonreq/cache/manager.py` — Existing Valkey key-prefixing and caching logic.
- `src/anonreq/middleware/rbac.py` — Role hierarchy and RBAC middleware models.
- `req/requirements_v2.md` — Product specifications (Operational Resilience, Business Unit Segregation).
- `redis.asyncio` & `SQLAlchemy 2.0` Official Documentation — Sentinel, Cluster connection patterns, and event listeners.

### Secondary (MEDIUM confidence)
- Vault Transit Secrets Engine and ESO (External Secrets Operator) integration patterns.
- OpenFGA API specs — Relationship-based access control paradigms.

---
*Research completed: 2026-07-12*
*Ready for roadmap: yes*
