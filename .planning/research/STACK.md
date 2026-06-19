# Technology Stack

**Project:** AnonReq — Self-Hosted LLM Anonymization Gateway
**Researched:** 2026-06-19

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12-slim | Runtime | Per Req 12; 3.12 has improved async performance, better error messages, and is the current LTS-equivalent for the 3.12 stream. Alpine variants cause libc compatibility issues with spaCy/transformers. |
| FastAPI | 0.115+ | Web framework | Native async, Pydantic v2 integration, built-in SSE support via `EventSourceResponse`, OpenAPI generation, dependency injection system that maps well to the pipeline step pattern. |
| uvicorn | 0.30+ | ASGI server | Standard FastAPI server; `--workers N` for multi-process, graceful shutdown handling. |

### Detection

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Presidio Analyzer | 2.x | PII detection engine | Industry-standard open-source PII detection from Microsoft. Supports hybrid regex + NER pipeline. Docker image available (`mcr.microsoft.com/presidio-analyzer`). Multi-language with spaCy/transformers/stanza backends. Extensible with custom recognizers. |
| spaCy | 3.7+ | NLP engine (via Presidio) | Default NLP backend for Presidio. `en_core_web_lg` model for English NER. Transformers backend also supported for non-English models. |
| HTTPX | 0.27+ | Async HTTP client | Required for async communication with Presidio sidecar and external LLM providers. Used by OpenAI Python SDK internally. Single client shared across all outbound calls via FastAPI lifespan. |

### Cache

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Valkey | 7.2+ | Ephemeral mapping store | Redis 7.2-compatible fork. Persistence disabled (`save ""`), no AOF, no RDB. Per Req 5: provably ephemeral. LRU eviction under memory pressure. Official Docker image from Docker Hub. |
| redis-py | 5.x | Python client | Async (`redis.asyncio`) support. Battle-tested. Supports `HGETALL`, `HSET`, `EXPIRE`, `DEL` — all operations required by the Mapping store. `hiredis` parser for ~10x parsing speed. |

### Observability

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Prometheus client | 0.20+ | Metrics | `prometheus_client` for `/metrics` endpoint. Histograms for latency, counters for requests/entities/errors. Standard FastAPI integration. |
| Python logging | stdlib | Structured audit logs | Structured JSON to stdout via `logging.config.dictConfig`. No external logging dependency — logs are consumed by Docker's log driver. |

### Testing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pytest | 8.x | Test runner | Standard Python test framework. Marks for unit/integration/property separation. |
| Hypothesis | 6.x | Property-based testing | Per Req 16. Generates random test inputs, finds edge cases, shrinks failures to minimal counterexamples. |
| respx | 0.21+ | HTTP mocking | Mock `httpx` requests in tests. Used to simulate Presidio responses without running the container. |
| testcontainers | 4.x | Integration test containers | Spin up Valkey container for integration tests. No need for external Docker Compose in test suite. |

### Infrastructure

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Docker Compose | 2.24+ | Local deployment | Per Req 12. `docker compose up` starts anonreq + presidio + valkey. |
| Docker | 24+ | Container runtime | Per Req 12 spec. Multi-stage Dockerfile with Python 3.12-slim. |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Web framework | FastAPI | Flask | Flask sync-only would require thread pool for async detection calls. FastAPI's async-first architecture is essential for SSE streaming and non-blocking HTTP to Presidio. |
| PII detection | Presidio Analyzer (sidecar) | Presidio Analyzer (in-process) | In-process would add 1-2GB memory per Gateway worker and couple NER model crashes to gateway availability. Sidecar gives process isolation, independent scaling, and cleaner fail-secure semantics. |
| PII detection | Presidio Analyzer | PrivateAI / Gretel / custom NER | Presidio is the only open-source solution with Docker deployment, multi-language, hybrid regex+NER, and extensible recognizer registry. Commercial alternatives would violate Apache 2.0 licensing strategy (Req 14). |
| Cache | Valkey | Redis (upstream) | Per Req 5, Valkey is preferred. Both are compatible at the API level. Valkey is the community fork (no SSPL license change). If Valkey isn't available, standard Redis works identically. |
| Cache | Valkey | Memcached | Memcached lacks `HGETALL` / hash data structures. Valkey/Redis's hash type is ideal for the token mapping: key = `anonreq:{session_id}`, field = `[TYPE_N]`, value = original_text. |
| Async HTTP | HTTPX | aiohttp | aiohttp has a lower-level API and doesn't match the Requests-style interface that OpenAI SDK uses internally. HTTPX provides `AsyncClient` with identical API to `Client`. |
| Property-based testing | Hypothesis | Schemathesis | Schemathesis is for API-level fuzzing (generates HTTP requests). Hypothesis generates Python data — better for unit-testing the tokenization/restoration invariants. Both can be used; Hypothesis is primary. |

## Installation

```bash
# Core
pip install fastapi uvicorn[standard] httpx presidio-analyzer redis prometheus-client pyyaml pydantic-settings

# NLP model (for Presidio container, not gateway)
python -m spacy download en_core_web_lg

# Dev
pip install pytest pytest-asyncio hypothesis respx testcontainers[redis]

# Optional: hiredis for faster redis-py parsing
pip install hiredis
```

## Docker Compose Layout

```yaml
services:
  anonreq:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"    # only with override file
    environment:
      - ANONREQ_PRESIDIO_URL=http://presidio:3000
      - ANONREQ_VALKEY_URL=redis://valkey:6379
      - ANONREQ_OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      presidio: { condition: service_healthy }
      valkey:   { condition: service_healthy }

  presidio:
    image: mcr.microsoft.com/presidio-analyzer:latest
    ports:
      - "5002:3000"    # only with override file
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 10s
      timeout: 3s
      retries: 5

  valkey:
    image: valkey/valkey:7.2-alpine
    command: ["valkey-server", "--save", "", "--appendonly", "no", "--maxmemory", "256mb", "--maxmemory-policy", "allkeys-lru"]
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
```

## Sources

- **Presidio Analyzer Docker deployment**: microsoft.github.io/presidio/installation/ — HIGH confidence
- **FastAPI EventSourceResponse**: fastapi.tiangolo.com/tutorial/server-sent-events — HIGH confidence
- **Valkey configuration**: valkey.io/docs/ — HIGH confidence
- **HTTPX best practices**: python-httpx.org/advanced/ — HIGH confidence
- **Hypothesis documentation**: hypothesis.readthedocs.io — HIGH confidence
