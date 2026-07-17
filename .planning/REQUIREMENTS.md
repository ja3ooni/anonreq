# Requirements: Milestone v2.0 Enterprise & Deployment Moat

## Categories

### 1. SSO and Role-Based Access Control (SSO)

- [x] **SSO-01**: User can authenticate via OpenID Connect (OIDC) JWT signature verification against a cached JWKS endpoint.
- [x] **SSO-02**: Enforce predefined enterprise roles (`administrator`, `security_officer`, `operator`, `read_only_auditor`) protecting administrative and gateway endpoints.
- [x] **SSO-03**: Support Mutual TLS (mTLS) machine-to-machine authentication by validating client certificate attributes forwarded by trusted perimeter ingress proxies.

### 2. Multi-Tenancy (TEN)

- [ ] **TEN-01**: Require header `X-AnonReq-Tenant-ID` on all client requests and validate it against the tenant registry context.
- [ ] **TEN-02**: Enforce strict namespace partitioning in Valkey (`anonreq:tenant_{tenant_id}:{session_id}`) for ephemeral session tokens.
- [ ] **TEN-03**: Dynamically encrypt Valkey token mappings using tenant-specific KMS keys.
- [ ] **TEN-04**: Scope structured logs and custom Prometheus metrics with the active `tenant_id` context.

### 3. High Availability (HA) & Scaling (HA)

- [x] **HA-01**: Support Valkey Sentinel (failover) and Valkey Cluster (sharding) connection factories in `CacheManager` based on connection scheme.
- [ ] **HA-02**: Create an official Helm v3 deployment package supporting horizontal pod autoscaling (HPA) and node anti-affinity rules.
- [x] **HA-03**: Handle Valkey failover/master election latency by wrapping cache requests with exponential backoffs and fail-closed security guards.

### 4. Secrets Management & Rotation (SEC)

- [x] **SEC-01**: Retrieve upstream provider credentials dynamically from HashiCorp Vault or cloud KMS at startup, without persisting secrets to environment variables or disk.
- [x] **SEC-02**: Watch secret volumes and reload rotated configurations dynamically in-memory without service disruption.
- [x] **SEC-03**: Redact secret substrings in log serializations with a `[REDACTED]` formatter safety net.
- [x] **SEC-04**: Maintain previous keys in a read-only buffer during rotation to allow active SSE streams to complete.

## Future Requirements

- Hardware HSM integration for cryptographic evidence validation.
- Customer-managed evidence storage integration.
- Federated control plane across regional deployments.

## Out of Scope

- Built-in username/password databases (always delegate to OIDC IdP).
- Direct SAML 2.0 XML parsing within the gateway (delegated to external proxies).
- Sticky session affinity requirements (gateway nodes remain completely stateless).

## Traceability

| Requirement | Description | Phase |
|-------------|-------------|-------|
| **SSO-01** | User authentication via OpenID Connect (OIDC) JWT signature verification against cached JWKS. | Phase 30 |
| **SSO-02** | Enforce predefined enterprise roles (`administrator`, `security_officer`, `operator`, `read_only_auditor`) on endpoints. | Phase 30 |
| **SSO-03** | Support Mutual TLS (mTLS) machine-to-machine authentication validation. | Phase 30 |
| **TEN-01** | Require and validate `X-AnonReq-Tenant-ID` header on client requests. | Phase 31 |
| **TEN-02** | Enforce strict namespace partitioning in Valkey (`anonreq:tenant_{tenant_id}:{session_id}`). | Phase 31 |
| **TEN-03** | Dynamically encrypt Valkey token mappings using tenant-specific KMS keys. | Phase 31 |
| **TEN-04** | Scope structured logs and custom Prometheus metrics with active `tenant_id`. | Phase 31 |
| **HA-01** | Support Valkey Sentinel and Valkey Cluster connection factories in `CacheManager`. | Phase 28 |
| **HA-02** | Create Helm v3 deployment package supporting HPA and node anti-affinity. | Phase 32 |
| **HA-03** | Handle Valkey failover reelection latency via exponential retry backoffs and fail-closed guards. | Phase 28 |
| **SEC-01** | Retrieve credentials dynamically from HashiCorp Vault or cloud KMS at startup. | Phase 29 |
| **SEC-02** | Watch secret volumes and reload configurations dynamically in-memory. | Phase 29 |
| **SEC-03** | Redact secret substrings in log serializations with `[REDACTED]` formatter. | Phase 29 |
| **SEC-04** | Maintain previous keys in read-only buffer during rotation for active streams. | Phase 29 |
