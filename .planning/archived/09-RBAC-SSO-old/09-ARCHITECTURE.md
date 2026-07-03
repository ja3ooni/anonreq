# Phase 09 Architecture: RBAC and SSO

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Components

- **CredentialVerifier**: owns a bounded part of the phase capability and exposes typed interfaces to the gateway orchestration layer.
- **OIDCVerifier**: owns a bounded part of the phase capability and exposes typed interfaces to the gateway orchestration layer.
- **SAMLServiceProvider**: owns a bounded part of the phase capability and exposes typed interfaces to the gateway orchestration layer.
- **MTLSIdentityExtractor**: owns a bounded part of the phase capability and exposes typed interfaces to the gateway orchestration layer.
- **RBACAuthorizer**: owns a bounded part of the phase capability and exposes typed interfaces to the gateway orchestration layer.
- **RevocationCache**: owns a bounded part of the phase capability and exposes typed interfaces to the gateway orchestration layer.
- **SessionPrincipalMiddleware**: owns a bounded part of the phase capability and exposes typed interfaces to the gateway orchestration layer.

## Sequence Diagram

```mermaid
sequenceDiagram
  participant Client
  participant Gateway
  participant Auth as Auth/RBAC
  participant Tenant as Tenant Context
  participant Phase as Phase 09 Components
  participant Guard as ForwardingGuard
  participant Provider
  participant Audit as Audit/Metrics

  Client->>Gateway: Request
  Gateway->>Auth: Verify principal and role
  Auth-->>Gateway: Principal or denial
  Gateway->>Tenant: Resolve tenant-scoped config
  Tenant-->>Gateway: Active config and policy version
  Gateway->>Phase: Execute RBAC and SSO decision/workflow
  Phase-->>Gateway: Typed decision, metadata, failure, or sanitized envelope update
  alt allowed to forward
    Gateway->>Guard: Validate sanitized envelope
    Guard->>Provider: Forward sanitized request
    Provider-->>Guard: Provider response
    Guard-->>Gateway: Restored/checked response path
  else denied or failed
    Gateway-->>Client: Controlled 4xx/5xx
  end
  Gateway->>Audit: Metadata-only event and metrics
  Gateway-->>Client: Response
```

## Data Flow

Inputs are accepted only after authentication, schema validation, tenant resolution, and configuration version binding. Phase data structures carry tenant ID, session ID, actor ID, policy version, and correlation ID. Sensitive runtime values remain in memory and are never copied into durable records. Durable records contain counts, hashes, status codes, policy actions, timestamps, and HMAC-verifiable identifiers.

## Failure Modes

- Missing or unknown tenant: reject before phase execution.
- Dependency unavailable: return 503 and emit fail-secure metric.
- Invalid phase configuration: reject activation or fail startup.
- Partial write to audit/evidence: preserve request outcome where safe, increment failure metric, and retry only for durable evidence workers.
- Provider forwarding attempted without sanitized envelope: block in ForwardingGuard.

## Threat Model

Administrative endpoints deny access unless a verified principal has a role granting the exact endpoint permission; external IdP outages fail closed. Additional threats are tenant confusion, stale configuration, unauthorized administration, log injection, schema drift, and denial-of-service through expensive evaluation paths. Mitigations are context-derived tenant scoping, immutable config versioning, RBAC checks, field allowlists, OpenAPI contract tests, latency budgets, and bounded queues.

## OpenAPI Changes

- `GET /v1/security/status`
- `POST /v1/admin/api-keys`
- `DELETE /v1/admin/api-keys/{key_id}`
- `GET /v1/admin/auth/events`

All endpoints use Pydantic v2 request/response models, structured error bodies, explicit RBAC metadata, tenant-aware filtering, and OpenAPI examples with synthetic data only.

## Metrics

- `anonreq_auth_events_total`
- `anonreq_authz_denials_total`
- `anonreq_jwks_refresh_total`
- `anonreq_revocation_lookup_seconds`

Each metric is labeled by `tenant_id` only where authorized and where cardinality is bounded. No labels contain raw payload fragments, token strings, secrets, or user-provided free text.
