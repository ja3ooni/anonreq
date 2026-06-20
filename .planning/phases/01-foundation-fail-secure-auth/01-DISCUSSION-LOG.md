# Phase 1: Foundation, Fail-Secure & Auth - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 1-Foundation, Fail-Secure & Auth
**Areas discussed:** Exception Granularity, Logging, Configuration, Testing Bar, Tenant Isolation, Mapping Store, Capability Registry

---

## Exception Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| All errors → HTTP 500 | Simplest and strictest fail-secure | |
| Differentiate client vs server | Auth 401, bad request 400/422, internal 500, etc. | ✓ |

**User's choice:** Differentiate client vs server errors
**Notes:** Fail-secure means never forward without safe classification, anonymization, policy evaluation, cache, restoration completing. Status code map: 401, 400/422, 403, 415, 429, 503, 500. FAIL-05 Forwarding_Guard verifies all pipeline prerequisites before any outbound call. Missing prerequisite → abort with 503.

### Error Response Format (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal (OpenAI-compatible) | `{"error": {"message": "...", "type": "..."}}` | |
| Structured + request_id | Extended OpenAI envelope with code + request_id | ✓ |

**User's choice:** OpenAI-compatible envelope extended with request_id. `{"error": {"message": "...", "type": "...", "code": "...", "request_id": "req_xxxxx"}}`. No PII, tokens, URLs, keys, or stack traces in bodies.

---

## Logging

| Option | Description | Selected |
|--------|-------------|----------|
| structlog | Structured logging library, field processor pipelines | ✓ |
| stdlib logging + JSON | Standard library with custom JSON formatter | |

**User's choice:** structlog

### Field Allowlist

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 1 minimum | timestamp, level, event, logger, request_id | |
| Richer | + method, path, status_code, duration_ms, source_ip (anon) | |
| Full | + session_id, component, version, error_type | ✓ (custom) |

**User's choice:** Strict 9-field allowlist: timestamp, level, event, request_id, component, status_code, duration_ms, error_type, version. Exclude all request/response content, entity values, token mappings, prompts, headers, auth data, IP addresses, session IDs. Non-allowlisted fields dropped before serialization.

---

## Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic Settings | Typed env var config, .env support, FastAPI-native | |
| Custom YAML + env overrides | YAML file with flexible nested config | |
| Hybrid | Pydantic for runtime/env, YAML for policy/security | ✓ |

**User's choice:** Hybrid. Infrastructure and secrets in env vars. Security policy and business logic in YAML.

### Minimum Viable Config

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal | API key + log level + port | |
| Standard | + Valkey/Presidio URLs, host | ✓ (custom) |
| Full | + opentelemetry, workers, debug | |

**User's choice:** 3 required env vars (ANONREQ_API_KEY ≥ 32 chars, ANONREQ_VALKEY_URL, ANONREQ_PRESIDIO_URL). 4 optional vars (HOST, PORT, LOG_LEVEL, REQUEST_TIMEOUT_SECONDS). Startup validates connectivity to all dependencies.

---

## Testing Bar

| Option | Description | Selected |
|--------|-------------|----------|
| Unit tests only | Config, auth, exception handler, health | |
| Unit + integration | Plus Docker Compose integration tests | ✓ (custom) |

**User's choice:** Invariant-driven exit criteria. Unit tests (config, auth, exception handler, health, logging, startup checks). Docker integration tests (gateway + valkey + presidio). Security invariants (no PII in logs/error responses, dependency failures block forwarding/startup). 80% overall coverage, 100% security-critical modules.

---

## Tenant Isolation

| Option | Description | Selected |
|--------|-------------|----------|
| Build tenant-ready from Phase 1 | tenant_id in keys, logs, metrics, models | ✓ |
| Single-tenant only, defer | No tenant scoping until needed | |

**User's choice:** Tenant-ready from Phase 1. Default tenant_id = "default". Namespace: `anonreq:{tenant_id}:{session_id}`. Core `RequestContext` class with request_id, tenant_id, session_id.

---

## Mapping Store

| Option | Description | Selected |
|--------|-------------|----------|
| Valkey HASH | Native type, HGETALL for SSE pre-fetch | ✓ |
| Valkey STRING + JSON | Simpler inspect, needs deserialization | |
| Combined HASH + TTL | Atomic HSET + EXPIRE | ✓ (this) |

**User's choice:** Valkey HASH with atomic HSET + EXPIRE. Key: `anonreq:{tenant_id}:{session_id}`. Fields: token → original_value. HGETALL at stream start. Async DEL post-response.

---

## Capability Registry

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-coded in adapters | Each adapter defines its own capabilities | |
| YAML-based registry | Loaded at startup, provider-level capabilities | ✓ |

**User's choice:** YAML-based capability registry loaded at startup. Adapters handle: request/response translation, auth, error normalization. Registry handles: streaming, tool calling, vision, JSON mode, embeddings, reasoning, context limits. Future: provider-level → model-level capabilities.

---

## the agent's Discretion

No areas deferred to agent discretion — all decisions explicitly captured.

## Deferred Ideas

- Classification framework details — Phase 2
- Policy engine evolution — Phase 2+
- Dynamic provider/model discovery — Phase 3+
- Multi-tenancy (non-default tenants) — Req 19, post-Stage 3
