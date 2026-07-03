# API Reference

The full OpenAPI specification is available at `docs/openapi.json` (auto-generated from the FastAPI application). This page provides a summary of available endpoints.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | Send a chat completion request (OpenAI-compatible) |
| GET | `/health` | Aggregate health check for all dependencies |
| GET | `/v1/models` | List available model aliases |
| GET | `/v1/compliance/presets` | List available compliance presets |
| GET | `/v1/config/rules` | List active custom detection rules |
| GET | `/metrics` | Prometheus metrics endpoint |

### POST /v1/chat/completions

Accepts an OpenAI-compatible chat completion request body. Supports both streaming (`stream: true`) and non-streaming modes. See the OpenAPI spec for the full schema.

### GET /health

Returns the aggregate health status of the gateway and its dependencies (Presidio Analyzer, Valkey). Response:

```json
{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}
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

All API endpoints (except `/health` and `/metrics`) require a Bearer token in the `Authorization` header:

```bash
Authorization: Bearer <your-anonreq-api-key>
```

The API key is configured via the `ANONREQ_API_KEY` environment variable.
