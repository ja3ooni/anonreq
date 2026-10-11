# API Reference

The full OpenAPI specification is available at `docs/openapi.json` (auto-generated from the FastAPI application). This page provides a summary of available endpoints.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | Send a chat completion request (OpenAI-compatible) |
| GET | `/health` | Process liveness (requires the gateway bearer key) |
| GET | `/health/ready` | Readiness: Valkey and Presidio (requires the gateway bearer key) |
| GET | `/v1/admin/tenants` | List tenants (admin credential) |
| GET | `/v1/admin/tenants/{tenant_id}` | Read one tenant (admin credential) |
| PUT | `/v1/admin/tenants/{tenant_id}` | Create or update a tenant, idempotent (admin credential) |
| POST | `/v1/admin/tenants/{tenant_id}/disable` | Disable a tenant (admin credential) |
| POST | `/v1/admin/tenants/{tenant_id}/enable` | Enable a tenant (admin credential) |
| GET | `/v1/models` | List available model aliases |
| GET | `/v1/compliance/presets` | List available compliance presets |
| GET | `/v1/config/rules` | List active custom detection rules |
| GET | `/metrics` | Prometheus metrics endpoint |

### POST /v1/chat/completions

Accepts an OpenAI-compatible chat completion request body. Supports both streaming (`stream: true`) and non-streaming modes. See the OpenAPI spec for the full schema.

### GET /health and GET /health/ready

`/health` reports process liveness only. `/health/ready` also checks Valkey and Presidio and returns 503 when either is down. Both require the gateway bearer key, so an HTTP health check that cannot send headers (a load balancer) should accept a 401 as "process is up" or use a container-level command check, as the Dockerfile does.

```json
{"status":"healthy","version":"0.1.0","components":{"gateway":{"status":"healthy"}}}
```

### GET /v1/models

Returns the list of configured model aliases and their target providers.

### GET /v1/compliance/presets

Returns available compliance presets with their mandated entity types and confidence thresholds.

### GET /v1/config/rules

Returns active custom detection rules (recognizers and exclusion lists).

### GET /metrics

Returns Prometheus-format metrics including request counts, detection latency, entity counts, and fail-secure event counters.

## Authentication

Chat, model, health, and metrics endpoints require the gateway bearer key in the `Authorization` header (`/metrics` can be opened with `ANONREQ_METRICS_NO_AUTH`). Chat requests also need an `X-AnonReq-Tenant-ID` header naming an enabled tenant. `/v1/admin/tenants*` uses a different credential, the admin key (`ANONREQ_ADMIN_API_KEY`) or OIDC, and needs no tenant header. See [multi-tenant.md](multi-tenant.md).

```bash
Authorization: Bearer <your-anonreq-api-key>
```

The API key is configured via the `ANONREQ_API_KEY` environment variable.
