# Installation

## Prerequisites

- Python 3.12+
- Docker Engine 24+ with Docker Compose v2+
- Minimum 4 GB RAM (8 GB recommended)

## Clone the Repository

```bash
git clone https://github.com/anonreq/anonreq.git
cd anonreq
```

## Environment Configuration

Copy the example environment file and configure the required variables:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANONREQ_API_KEY` | Yes | — | Static bearer token for API authentication (≥ 32 chars) |
| `ANONREQ_LOG_LEVEL` | No | `INFO` | Logging level |
| `ANONREQ_CACHE_TTL` | No | `600` | Session cache TTL in seconds |
| `ANONREQ_PRESIDIO_URL` | No | `http://presidio-analyzer:5001` | Presilio Analyzer URL |
| `ANONREQ_VALKEY_URL` | No | `valkey://localhost:6379` | Valkey connection string |

At least one provider API key (`ANONREQ_OPENAI_API_KEY`, `ANONREQ_ANTHROPIC_API_KEY`, or `ANONREQ_GEMINI_API_KEY`) must be set.

## Docker Compose Setup

```bash
docker compose up -d --wait
```

This starts all three services: `anonreq` (gateway), `presidio-analyzer` (PII detection), and `valkey` (ephemeral cache).

## Verify Installation

```bash
curl http://localhost:8000/health
```

Expected response: HTTP 200 with `{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}`.

## Troubleshooting

| Issue | Likely Cause | Solution |
|-------|-------------|----------|
| Health check returns 503 | Presidio model still loading | Wait 60s for model download, then retry |
| `docker compose up` fails | Port 8000 in use | Stop other services or change port mapping |
| `curl: connection refused` | Gateway not ready | Run `docker compose ps` to check status |
