# Multi-Tenant Operation

Every chat request names a tenant with the `X-AnonReq-Tenant-ID` header. A tenant is a customer, workspace, or business unit. Unknown tenants get HTTP 400, disabled tenants HTTP 403, and an unreadable registry HTTP 503. The gateway never guesses a tenant.

## Where tenants live

| Source | Use | Editable at runtime |
|---|---|---|
| `config/tenants.yaml` (seed) | Built-ins such as `default`, loaded at startup | No. The API returns 409. |
| `tenant` table in `ANONREQ_DATABASE_URL` | Tenants created through the admin API | Yes |

The table is the shared source of truth. Tenants created through the API survive restarts and are visible to every replica. If the same id exists in both places, the YAML seed wins.

**Production requires a shared database.** The default `sqlite+aiosqlite:///./anonreq.db` is a file inside one container, so replicas would each see a different registry. Use PostgreSQL (`postgresql+asyncpg://...`) whenever more than one replica runs.

## Schema and startup

The gateway checks that the `tenant` table is readable at startup and refuses to start if not. Run migrations as a deploy step before the first start and after upgrades:

```bash
alembic upgrade head
```

## How changes spread between replicas

Each replica caches a tenant for `ANONREQ_TENANT_CACHE_TTL_SECONDS` (default 10) and remembers an unknown id for `ANONREQ_TENANT_NEGATIVE_CACHE_TTL_SECONDS` (default 5). The replica that handled the admin call updates immediately. Other replicas apply a **disable** within the cache TTL, and see a **new** tenant within the negative TTL. Set the cache TTL to 0 to read the database on every request, at the cost of one query per chat request.

If the database is unreachable when a lookup needs it, the request fails with 503. Cached tenants keep working until their TTL expires.

## Admin API

Authenticated with the admin credential (`ANONREQ_ADMIN_API_KEY`, or OIDC when configured) and the ADMINISTRATOR role. The gateway bearer key does **not** work here, so a service that only sends chat traffic cannot manage tenants. These routes need no tenant header.

```bash
# Create or update. Idempotent: the same call twice leaves the same row.
curl -X PUT http://gateway:8080/v1/admin/tenants/0b5c3f0e-7a52-4f6b-9a83-5f1f0e0c9d11 \
  -H "Authorization: Bearer $ANONREQ_ADMIN_API_KEY" -H "Content-Type: application/json" \
  -d '{"display_name":"Acme Agency","allowed_providers":["openai"],"allowed_models":["gpt-4o-mini"]}'
# 201 on create, 200 on update

curl -X POST .../v1/admin/tenants/<id>/disable -H "Authorization: Bearer $ANONREQ_ADMIN_API_KEY"
curl -X POST .../v1/admin/tenants/<id>/enable  -H "Authorization: Bearer $ANONREQ_ADMIN_API_KEY"
curl .../v1/admin/tenants            -H "Authorization: Bearer $ANONREQ_ADMIN_API_KEY"
curl .../v1/admin/tenants/<id>       -H "Authorization: Bearer $ANONREQ_ADMIN_API_KEY"
```

- `PUT` replaces the record; it does not merge. Send every field you want kept.
- `tenant_id`: 1 to 64 characters, letters, digits, `_` or `-`, starting with a letter or digit. A UUID is valid.
- Unknown body fields are rejected (422).
- Tenants cannot be deleted, only disabled, so audit records keep resolving.

## What a tenant setting enforces today

| Field | Enforced | Notes |
|---|---|---|
| `enabled` | Yes | 403 when false |
| `allowed_models` | Yes | Matches the requested alias or the resolved model. Empty list means no restriction. 403 on mismatch, before detection and before any provider call. |
| `allowed_providers` | Yes | Same rules, matched against the resolved provider. |
| `spend_limits`, `rate_limits`, `kms_key_arn` | **No** | Stored and returned, not yet applied. |
| Compliance preset | **Deployment-wide** | `ANONREQ_ACTIVE_PRESETS` applies to all tenants. There is no per-tenant preset yet. |
| Locale | Per request | Send `X-AnonReq-Locale` on each request. |

## Health checks

`/health` and `/health/ready` require the gateway bearer key. HTTP-only health checks that cannot send headers (a load balancer) should treat 200 and 401 as healthy for `/health`. Container-level checks should use a command, as the Dockerfile and Helm chart do.
