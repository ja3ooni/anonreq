# Deployment

## Production Considerations

### Resource Allocation

Ensure your host meets the minimum resource requirements for all three containers. For production deployments, add 50% headroom above peak observed usage.

### Logging Configuration

Logs are written to stdout in structured JSON format. Configure log aggregation via your preferred tool (Docker logging driver, syslog, or a log shipper like Fluentd or Vector).

### Network Security

The gateway binds to port 8000. Presidio Analyzer and Valkey are isolated on an internal Docker network and are not directly accessible from outside.

### TLS Termination

Terminate TLS at your reverse proxy (nginx, Caddy, or a cloud load balancer) and forward to the gateway over HTTP on the internal network.

## Environment Variables

| Variable | Type | Default | Required | Description |
|----------|------|---------|----------|-------------|
| `ANONREQ_API_KEY` | string | — | Yes | Bearer token for API authentication (≥ 32 chars) |
| `ANONREQ_LOG_LEVEL` | string | `INFO` | No | Log level: DEBUG, INFO, WARNING, ERROR |
| `ANONREQ_CACHE_URL` | string | `valkey://localhost:6379` | No | Valkey server URL |
| `ANONREQ_CACHE_PASSWORD` | string | — | No | Valkey requirepass |
| `ANONREQ_CACHE_TTL` | int | `600` | No | Session TTL in seconds (60–3600) |
| `ANONREQ_OPENAI_API_KEY` | string | — | Conditional | OpenAI API key |
| `ANONREQ_ANTHROPIC_API_KEY` | string | — | Conditional | Anthropic API key |
| `ANONREQ_GEMINI_API_KEY` | string | — | Conditional | Google Gemini API key |
| `ANONREQ_OLLAMA_BASE_URL` | string | — | No | Ollama server URL |
| `ANONREQ_LOCALE` | string | `en-US` | No | Default detection locale |
| `ANONREQ_COMPLIANCE_PRESET` | string | — | No | Compliance preset name |
| `ANONREQ_CONFIDENCE_THRESHOLD` | float | `0.7` | No | Detection confidence threshold (0.0–1.0) |
| `PRESIDIO_ANALYZER_URL` | string | `http://presidio-analyzer:5001` | No | Presilio Analyzer URL |

## Docker Compose Production Configuration

Customize the default `docker-compose.yml` with a `docker-compose.override.yml` file:

```yaml
services:
  anonreq:
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: "4G"
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"
```

### Health Check Configuration

Each service has a built-in health check. Monitor all three via the gateway `/health` endpoint. Set up external monitoring to alert on non-200 responses.

### Restart Policies

All services use `restart: unless-stopped`. For zero-downtime deployments, run multiple gateway replicas behind a load balancer.

## Logging

Structured JSON logs are emitted to stdout. Key fields: `timestamp`, `level`, `event`, `session_id`, `latency_ms`, `entity_count`, `provider`. Consume with your preferred log aggregation tool.

## Upgrading

1. Pull the latest image: `docker compose pull anonreq`
2. Recreate services: `docker compose up -d --force-recreate anonreq`
3. Verify health: `curl http://localhost:8000/health`

## Security

- The gateway fails secure: any detection or cache error returns HTTP 5xx and never forwards unsanitized data upstream
- API key rotation is supported via restart: update `ANONREQ_API_KEY` in `.env` and run `docker compose restart anonreq`
- All cache data is ephemeral — no data written to disk
