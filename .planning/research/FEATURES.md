# FEATURES Research: Enterprise & Deployment Moat (Milestone v2.0)

This document analyzes the required capabilities and landscape details for the new enterprise and deployment features in Milestone v2.0 of the AnonReq gateway. It focuses on four core dimensions: **SSO/RBAC**, **Multi-Tenancy**, **HA/Scaling**, and **Secrets Management**, categorizing them into Table Stakes, Differentiators, and Anti-Features, with opinionated design decisions.

---

## 1. Executive Summary

Milestone v2.0 establishes the commercial enterprise moat for AnonReq. While Milestone v1.0 delivered the core high-performance in-memory anonymization pipeline, v2.0 transforms AnonReq from a standalone developer utility into a production-grade enterprise AI control plane. By enforcing strict tenant isolation, delegating authentication to corporate Identity Providers (IdPs), guaranteeing horizontal scalability with sub-100ms latency overhead, and securing credentials through industry-standard vaults, we provide compliance and SRE teams with verifiable controls that withstand rigorous regulator audits.

---

## 2. SSO and Role-Based Access Control (RBAC)

Enterprise authentication ensures that access to the administrative and governance control plane of AnonReq matches the organization's existing identity lifecycle.

### Feature Matrix

| Capability | Table Stakes | Differentiators | Anti-Features |
| :--- | :--- | :--- | :--- |
| **Authentication Protocols** | • OpenID Connect (OIDC) JWT verification<br>• mTLS machine authentication | • Dynamic claims-to-role mappings<br>• Just-In-Time (JIT) provisioning | • Direct SAML 2.0 XML parsing (avoid security debt)<br>• Local username/password DB |
| **Authorization & Roles** | • Standard enterprise roles (`administrator`, `security_officer`, `operator`, `read_only_auditor`) | • Field-level and preset-level authorization rules based on user attributes | • Self-managed user groups or team lists within AnonReq |
| **Session Control** | • Configurable JWT expiry (min 60s)<br>• Cache-backed token revocation list | • Instant global session termination via Valkey revocation broadcasts | • Local, non-distributed session storage |

### Opinionated Design Decisions
*   **Use OIDC (OAuth 2.0 JWT) with JWKS Caching for SSO:** Implement OIDC using `PyJWT` and an in-memory cached JWKS (JSON Web Key Set) endpoint. Do not integrate SAML 2.0 directly inside the gateway container. SAML's XML parsing requirements (`lxml`, `xmlsec`) introduce severe dependency bloat and high CVE exposure risk. For enterprise clients requiring SAML 2.0, mandate the use of an external identity proxy (e.g., Keycloak, Authentik, or cloud API gateways) that translates SAML assertions to standard OIDC JWTs.
*   **Use mTLS for Machine-to-Machine administrative clients:** For internal automations or DevOps scripts interacting with administrative APIs, bypass OIDC by extracting client certificate Common Names (CN) and matching them against a strictly defined tenant registry.
*   **Enforce Fail-Closed Identity Failures:** If the OIDC provider (JWKS endpoint) becomes unreachable, the gateway must fail closed immediately—rejecting administrative operations and falling back to a pre-configured local rescue credential only if explicitly enabled in local configuration.

---

## 3. Multi-Tenancy

Multi-tenancy enables a single deployment of AnonReq to safely serve multiple departments, business units, or downstream corporate clients with absolute isolation of data, policies, and resource consumption.

### Feature Matrix

| Capability | Table Stakes | Differentiators | Anti-Features |
| :--- | :--- | :--- | :--- |
| **Context Scoping** | • Required request header `X-AnonReq-Tenant-ID`<br>• Tenant registry validation | • OIDC claim-based tenant resolution<br>• Custom routing rules per tenant | • URL path-based tenant ID injection (`/v1/tenant-id/...`) |
| **Data Plane Isolation** | • Tenant-scoped Valkey key namespaces (`anonreq:{tenant_id}:{session_id}`) | • Dynamic encryption of token mappings using tenant-specific keys | • Cross-tenant token mapping reuse or cross-tenant cache lookups |
| **Resource & Spend Limits** | • Tenant-level RPM/TPM throttling<br>• Daily/monthly USD budgets | • Automated fallback routing to cheaper models when budget is depleted | • Gateway-level credit card charging or billing integration |
| **Audit & Metrics** | • Separate tenant log streams<br>• `tenant_id` labeled Prometheus metrics | • Tenant-specific cryptographic log signing for non-repudiation | • Combined raw logs containing multi-tenant payloads |

### Opinionated Design Decisions
*   **Enforce Namespace Isolation in Valkey:** Every cache key must be explicitly constructed as `anonreq:{tenant_id}:{session_id}`. The Tenant Context Middleware must extract the `Tenant_ID` from the authenticated request header (`X-AnonReq-Tenant-ID`) and inject it into the context. No code path should accept a user-supplied cache key without prepending the context-derived `Tenant_ID`.
*   **Decouple Configuration Registry from Runtime:** Tenant configurations (presets, recognizers, credentials) must be stored in PostgreSQL and cached in-memory inside the gateway. Provide an administrative API (`POST /v1/admin/tenants`) that triggers a cache invalidation event via Valkey Pub/Sub, causing all gateway nodes to reload the configuration dynamically without a restart.
*   **Implement Strict Rate Limiting in Valkey:** Enforce per-tenant Rate Limiting (RPM/TPM) and Concurrent Request Limiting directly in Valkey using Redis Lua scripts. This prevents "noisy neighbor" scenarios where one tenant's traffic spike degrades the anonymization latency of other tenants.

---

## 4. High Availability (HA) and Scaling

HA and Scaling features guarantee that AnonReq can process massive request volumes under strict SLAs without introducing single points of failure.

### Feature Matrix

| Capability | Table Stakes | Differentiators | Anti-Features |
| :--- | :--- | :--- | :--- |
| **State Management** | • Completely stateless API gateway tier<br>• All shared state in Valkey | • In-memory cache warming for localized regex recognizers | • Disk-backed message queues for request buffering |
| **Valkey Resiliency** | • Support for Valkey Sentinel (failover)<br>• Support for Valkey Cluster (sharding) | • Adaptive Sentinel failover recovery in <30 seconds | • Single-node Valkey without persistence checks in prod |
| **Kubernetes Integration** | • Official Helm chart with HPA support<br>• Standard readiness/liveness probes | • Automated resource tuning profile generation based on load tests | • Custom operator or service mesh implementation |
| **Throttling & Backpressure** | • Rate limit HTTP 429 returns | • Real-time load shedding when queue latencies exceed 100ms | • TCP window throttling at the gateway layer |

### Opinionated Design Decisions
*   **Stateless Gateways behind standard L4/L7 Load Balancers:** Maintain a zero-session-affinity design. Since the cache mapping is stored globally in a highly available Valkey cluster, any gateway node can process any request or stream chunk for a given session.
*   **Enforce Fail-Secure during Valkey Failover:** If Valkey experiences a primary node failover, the gateway must return HTTP 503 within 30 seconds rather than bypassing the anonymizer or caching mappings locally. Temporary local caching violates data sovereignty, and forwarding unsanitized requests is blocked by the `ForwardingGuard`.
*   **Optimize streaming tail-buffers in-memory:** Do not use temporary files or databases to buffer SSE streams. Streaming chunk parsing and token restoration must occur entirely in-memory using small sliding-window buffers to prevent local disk writes.

---

## 5. Secrets Management

Secrets management secures sensitive upstream credentials, client API keys, and internal communication certificates, ensuring no plaintext secrets exist at rest or in logs.

### Feature Matrix

| Capability | Table Stakes | Differentiators | Anti-Features |
| :--- | :--- | :--- | :--- |
| **Secret Storage** | • HashiCorp Vault, AWS Secrets Manager, Azure Key Vault integration | • Multi-provider dynamic fallback (AWS + Vault)<br>• Decentralized key generation | • Production environment variables (`.env`) or disk-based keys |
| **Rotation & Grace Periods** | • Seamless secret rotation (polling 300s) | • Active SSE request tracking to allow old keys to drain during rotation | • Gateway restarts for credential rotation |
| **Security Sanitization** | • Shannon entropy validation (min 256 bits)<br>• Redacting known secrets in logs | • AST-based JSON payload scanning to catch leaked keys in prompts | • Dynamic decryption APIs exposed to administrative users |

### Opinionated Design Decisions
*   **Integrate directly with Enterprise KMS:** The gateway must retrieve secrets dynamically at startup and cache them in-memory only. Support HashiCorp Vault (KV v2) and cloud-native managers (AWS Secrets Manager, Azure Key Vault). Restrict environment variable loading (`.env`) strictly to development environments.
*   **Enforce Live Secrets Redaction in Logs:** Run a regex-based search-and-replace formatter over all log records before serialization. Replace any substring matching a loaded secret value with `[REDACTED]`. This acts as a safety net to prevent developer logging mistakes from exposing API keys.
*   **Support Graceful Rotation for Active Streams:** When a provider key is rotated, the gateway must load the new key immediately for all *new* requests, but maintain the previous key in a read-only transit buffer for up to 300 seconds to allow long-running SSE chat completions to finish processing.

---

## 6. Milestone v2.0 Phase Alignment

To execute this roadmap, the features are divided into the following phases:

1.  **Phase 09: Enterprise Authentication & RBAC**
    *   *Deliverables:* PyJWT-based OIDC and mTLS authentication middleware; predefined role-based decorators (`@requires_role`); revocation list caching in Valkey.
2.  **Phase 10: Tenant Isolation**
    *   *Deliverables:* `TenantContextMiddleware` enforcing header parsing; namespace prefixing in cache lookups; tenant config storage in PostgreSQL; tenant-scoped metrics and logging pipelines.
3.  **Phase 15: Deployment Models (HA & Infrastructure)**
    *   *Deliverables:* Kubernetes Helm chart; Valkey Sentinel/Cluster connection pooling; pre-flight check validation logic.
4.  **Phase 16: Performance and Scale**
    *   *Deliverables:* Load-shedding controller based on request processing latency; concurrency queue tuning; k6 load scenario suites verifying sub-100ms overhead at scale.
