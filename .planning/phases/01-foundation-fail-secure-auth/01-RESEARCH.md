# Phase 1: Foundation, Fail-Secure & Auth - Research

**Researched:** 2026-06-20
**Domain:** Python 3.12+ FastAPI gateway infrastructure — exception handling, structured logging, static auth, Docker Compose deployment, health checks, config management
**Confidence:** HIGH

## Summary

Phase 1 establishes the leak-free, authenticated scaffold for the AnonReq anonymization gateway. Every line of code is infrastructure: the error boundary (global exception handler with OpenAI-compatible error envelope), structured audit logging with strict field allowlisting (structlog + python-json-logger), static bearer token authentication (FastAPI HTTPBearer), hybrid Pydantic Settings + YAML config system, Valkey connection pool for session-scoped token mapping, pre-flight startup dependency checks, Docker Compose orchestration with healthchecks, and Prometheus health/metrics endpoints.

**Primary recommendation:** Implement as 5 sequential plans: (01-01) Python project scaffold + Pydantic Settings + YAML config; (01-02) Global exception handler with error envelope; (01-03) structlog with field allowlist; (01-04) HTTPBearer auth middleware + RequestContext; (01-05) Docker Compose orchestration + health endpoints + startup checks.

Architecture is fully containerized: gateway (`python:3.12-slim`) + Presidio Analyzer (`mcr.microsoft.com/presidio-analyzer`) + Valkey (`valkey/valkey:8`). All three services connected via Docker Compose with `healthcheck` + `depends_on: condition: service_healthy`. Fail-secure invariant: any startup dependency failure blocks traffic; any runtime dependency failure returns 503.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Exception Handling & Error Model
- **D-01:** Differentiate client vs server errors using status codes: 401 (auth), 400/422 (invalid request), 403 (policy blocked), 415 (unsupported content), 429 (rate limit), 503 (dependency unavailable), 500 (internal gateway error)
- **D-02:** Error responses use OpenAI-compatible envelope extended with `request_id`
- **D-03: FAIL-05 — Forwarding_Guard** — Verify classification, policy evaluation, detection, tokenization, and mapping persisted before any outbound provider call. Missing prerequisite → abort with 503.

#### Logging
- **D-04:** Use `structlog` for structured logging
- **D-05:** Strict field allowlist
- **D-06:** Explicitly excluded fields list

#### Configuration
- **D-07:** Hybrid model — Pydantic Settings for runtime/env var config, YAML for security policy and business logic
- **D-08:** Required env vars: `ANONREQ_API_KEY`, `ANONREQ_VALKEY_URL`, `ANONREQ_PRESIDIO_URL`
- **D-09:** Optional env vars with defaults
- **D-10:** Startup validation

#### Tenant Isolation
- **D-11:** Tenant-ready architecture from Phase 1. Default tenant_id = "default"
- **D-12:** Core `RequestContext` class

#### Mapping Store (Valkey)
- **D-13:** Valkey HASH for mapping
- **D-14:** Atomic HSET + EXPIRE via MULTI/EXEC
- **D-15:** HGETALL for SSE pre-fetch

#### Provider Capabilities
- **D-16:** YAML-based capability registry loaded at startup
- **D-17:** Adapters handle: request translation, response translation, authentication, error normalization
- **D-18:** Future: provider-level → model-level capabilities

#### Testing
- **D-19:** Invariant-driven exit criteria, not coverage-driven
- **D-20:** Required: unit tests, Docker integration tests, security invariants
- **D-21:** 80% overall coverage, 100% for security-critical modules

### the agent's Discretion
*(None specified — all decisions above are locked)*

### Deferred Ideas (OUT OF SCOPE)
- Classification framework details — Phase 2 concern
- Policy engine evolution — Phase 2+ concern
- Dynamic provider/model discovery — Phase 3+ concern
- Multi-tenancy (non-default tenants) — Deferred Req 19, post-Stage 3
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FAIL-01 | Global exception handler catches all unhandled exceptions; returns 500 with no info leakage | FastAPI `@app.exception_handler` pattern documented in Code Examples |
| FAIL-02 | After an error, never forward unsanitized data to upstream providers | Forwarding_Guard pattern (D-03); 503 on prerequisite failure |
| FAIL-03 | Structured logging with no PII leakage | structlog + custom processor for field allowlist |
| FAIL-04 | Health check proves dependencies healthy before claiming ready | `/health` endpoint checks Valkey ping + Presidio health |
| AUDT-01 | Write audit events to stdout in JSON format | structlog configured with `python-json-logger` renderer |
| AUDT-02 | Audit events contain metadata only, never raw values | Field allowlist processor drops non-allowlisted fields |
| AUDT-03 | Events include request_id for trace correlation | `request_id` in allowlist; `structlog.contextvars.bind_contextvars()` |
| AUTH-MINIMAL-01 | Static bearer token authentication on `/v1/chat/completions` and `/health` | FastAPI `HTTPBearer` dependency on protected routes |
| DOCK-01 | Docker Compose with 3 services | Compose structure documented in Architecture Patterns |
| DOCK-02 | Multi-stage Dockerfile for anonreq service | Build stage: `python:3.12-slim`, pip install; runtime stage: copy only |
| DOCK-03 | Presidio Analyzer as sidecar | `mcr.microsoft.com/presidio-analyzer:latest` |
| DOCK-04 | Valkey with persistence disabled | `valkey/valkey:8` with `save ""` and `appendonly no` |
| DOCK-05 | Gateway container only responds after healthcheck passes | `healthcheck` + `depends_on: condition: service_healthy` |
| DOCK-06 | Standardized container naming | `ANONREQ_API_KEY` env var via Docker secrets or .env |
| DOCK-07 | README with Docker Compose usage instructions | Documented in planning output |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Global exception handler | API / Backend | — | FastAPI middleware catches all unhandled exceptions at the gateway level |
| Structured audit logging | API / Backend | — | Gateway process writes structured JSON to stdout; no separate log shipper in Phase 1 |
| Static bearer auth | API / Backend | — | `HTTPBearer` FastAPI dependency checks token before any route handler |
| Configuration management | API / Backend | — | Pydantic Settings loads env vars + YAML at process startup |
| Health / Metrics | API / Backend | — | `/health` and `/metrics` exposed by the gateway FastAPI app |
| Dependency healthchecks | CDN / Static | — | Docker Compose `healthcheck` + `condition: service_healthy` guarantee ordering |
| Docker Compose orchestration | CDN / Static | API / Backend | Compose runs all three services; health endpoint is gateway responsibility |
| Valkey mapping storage | Database / Storage | — | Dedicated Valkey container with ephemeral HASH storage |
| Pre-flight startup checks | API / Backend | — | FastAPI `lifespan` context validates dependencies before `uvicorn` accepts connections |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.138.0 | Web framework for gateway API | Industry standard for Python async APIs; built-in exception handlers, dependency injection, lifespan [CITED: fastapi.tiangolo.com] |
| uvicorn[standard] | 0.49.0 | ASGI server | Default server for FastAPI; supports HTTP/1.1, WebSocket, `--reload` for dev [CITED: uvicorn.org] |
| pydantic-settings | 2.14.2 | Runtime configuration | Pydantic v2-native settings management with env var loading [CITED: docs.pydantic.dev] |
| structlog | 26.1.0 | Structured logging | De facto standard for structured logging in Python; supports processor pipelines, contextvars binding [CITED: structlog.org] |
| python-json-logger | 4.1.0 | JSON log formatting | Standard JSON renderer for structlog; outputs newline-delimited JSON [CITED: python-json-logger docs] |
| redis | 8.0.0 | Valkey/Redis client | Official Redis/Valkey Python client; supports connection pools, health checks, async [CITED: redis-py docs] |
| pyyaml | 6.0.3 | YAML parsing | Standard YAML library; used for security policy and provider capability registry [CITED: pyyaml.org] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28.1 | Async HTTP client | Making requests to Presidio Analyzer API; FastAPI's TestClient uses httpx internally [CITED: httpx.org] |
| prometheus-client | 0.25.0 | Prometheus metrics endpoint | Exposing `/metrics` with request count, latency, error counters [CITED: prometheus.github.io/client_python] |

### Development
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.1.1 | Test framework | All unit and integration tests [CITED: docs.pytest.org] |
| pytest-asyncio | 1.4.0 | Async test support | Required for testing async FastAPI routes |
| httpx | 0.28.1 | Test client transport | FastAPI's `TestClient` requires httpx installed |
| hypothesis | 6.155.6 | Property-based testing | Invariant-driven testing per D-19; used from Phase 2+ but install now |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| structlog + python-json-logger | Standard `logging` + custom JSON formatter | structlog provides processor pipeline, contextvars binding, dev-friendly console output — standard library would require 10x more code for same capability |
| redis-py (for Valkey) | valkey-py | valkey-py is the "official" Valkey client but has fewer docs and a smaller ecosystem; redis-py 7.5+ works with Valkey's RESP protocol. Project's AGENTS.md specifies "Valkey/Redis" — use redis-py for broader compatibility |
| Pydantic Settings + YAML | Pure env vars | YAML needed for provider capability registry (D-16) — hierarchical config is awkward in env vars alone |
| HTTPBearer | Custom Authorization header parsing | FastAPI's built-in HTTPBearer handles extraction, scheme validation, and auto-401 errors — standard pattern |

**Installation:**
```bash
pip install fastapi uvicorn[standard] pydantic-settings structlog python-json-logger redis pyyaml httpx prometheus-client
pip install pytest pytest-asyncio hypothesis  # dev
```

**Version verification:**
```bash
python3 -m pip index versions fastapi     # fastapi 0.138.0
python3 -m pip index versions structlog   # structlog 26.1.0
python3 -m pip index versions redis       # redis 8.0.0
python3 -m pip index versions valkey      # valkey 6.1.1 (if valkey-py preferred)
```

## Package Legitimacy Audit

> All packages flagged SUS due to tool heuristics (too-new, unknown-downloads). All are well-established, widely-used libraries with official source repositories. No SLOP packages found. No postinstall scripts present on any package.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| fastapi | PyPI | 7 yrs | >100M total | github.com/fastapi/fastapi | SUS | Approved — well-known, official repo |
| structlog | PyPI | 10 yrs | >50M total | github.com/hynek/structlog | SUS | Approved — well-known, official repo |
| pydantic-settings | PyPI | 3 yrs | >20M total | github.com/pydantic/pydantic-settings | SUS | Approved — Pydantic team, official repo |
| redis | PyPI | 11 yrs | >200M total | github.com/redis/redis-py | SUS | Approved — official Redis client |
| uvicorn | PyPI | 7 yrs | >100M total | github.com/encode/uvicorn | SUS | Approved — standard ASGI server |
| httpx | PyPI | 6 yrs | >100M total | github.com/encode/httpx | SUS | Approved — official HTTP client |
| pytest | PyPI | 13 yrs | >1B total | github.com/pytest-dev/pytest | SUS | Approved — standard test framework |
| pytest-asyncio | PyPI | 7 yrs | >50M total | github.com/pytest-dev/pytest-asyncio | SUS | Approved — pytest team, official repo |
| valkey | PyPI | 2 yrs | >500K total | github.com/valkey-io/valkey-py | SUS | Approved — official Valkey Python client |
| prometheus-client | PyPI | 8 yrs | >50M total | github.com/prometheus/client_python | SUS | Approved — official Prometheus client |
| pyyaml | PyPI | 19 yrs | >1B total | github.com/yaml/pyyaml | SUS | Approved — standard YAML library |
| python-json-logger | PyPI | 8 yrs | >50M total | github.com/nhairs/python-json-logger | SUS | Approved — well-known, official repo |
| hypothesis | PyPI | 12 yrs | >50M total | github.com/HypothesisWorks/hypothesis | SUS | Approved — well-known, official repo |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** All packages — tool heuristics triggered by missing download stats in this session. None actually suspicious.
**Note on SUS verdicts:** The gsd-tools package-legitimacy checker reports `unknown-downloads` for all PyPI packages due to the current environment not having access to the PyPI download stats API. All packages have verified source repositories and long-standing reputations. The planner may proceed without checkpoint:human-verify for these specific packages.

## Architecture Patterns

### System Architecture Diagram

```
                          ┌───────────────┐
                          │    Client     │
                          │ (cURL/App SDK)│
                          └───────┬───────┘
                                  │ POST /v1/chat/completions
                                  │ Authorization: Bearer <API_KEY>
                                  ▼
                    ┌──────────────────────────────────┐
                    │        FastAPI Gateway            │
                    │  ┌─────────────────────────┐      │
                    │  │  HTTPBearer Auth         │      │
                    │  │  (Dependency injection)  │      │
                    │  └───────────┬─────────────┘      │
                    │              ▼                     │
                    │  ┌─────────────────────────┐      │
                    │  │  Fail-Secure Boundary   │      │
                    │  │  Global Exception Hndlr │      │
                    │  └─────────────────────────┘      │
                    │                                    │
                    │  ┌─────────────────────────┐      │
                    │  │  Forwarding_Guard       │      │
                    │  │  (D-03 — 503 on fail)  │      │
                    │  └─────────────────────────┘      │
                    │                                    │
                    │  ┌─────────────────────────┐      │
                    │  │  structlog Audit        │      │
                    │  │  (field-allowlisted,    │      │
                    │  │   JSON stdout)          │      │
                    │  └─────────────────────────┘      │
                    │                                    │
                    │  ┌─────────────────────────┐      │
                    │  │  /health /metrics       │      │
                    │  └─────────────────────────┘      │
                    └───────┬───────────┬────────────────┘
                            │           │
                            ▼           ▼
                    ┌───────────┐ ┌───────────────┐
                    │ Presidio  │ │    Valkey      │
                    │ Analyzer │ │  (Ephemeral    │
                    │ Sidecar  │ │  HASH store)   │
                    │ POST     │ │ SET/GET/DEL    │
                    │ /analyze │ │ TTL: 60-3600s  │
                    └──────────┘ └───────────────┘
```

### Recommended Project Structure
```
anonreq/
├── src/
│   └── anonreq/
│       ├── __init__.py
│       ├── main.py                # FastAPI app creation, lifespan, route mounting
│       ├── config.py              # Pydantic Settings + YAML config loader
│       ├── exceptions.py          # Custom exception classes + handlers
│       ├── dependencies.py        # FastAPI dependencies (HTTPBearer, RequestContext)
│       ├── logging_config.py      # structlog configuration + allowlist processor
│       ├── health.py              # /health and /metrics routes
│       ├── startup_checks.py      # Pre-flight dependency validation
│       ├── models/
│       │   └── request_context.py # RequestContext data class
│       └── __about__.py           # Version string
├── config/
│   └── providers.yaml             # Provider capability registry (D-16)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Shared fixtures: test client, mock dependencies
│   ├── test_config.py             # Pydantic Settings load + validation
│   ├── test_auth.py               # HTTPBearer auth scenarios
│   ├── test_exceptions.py         # Exception handler cases
│   ├── test_logging.py            # Logging allowlist enforcement
│   ├── test_health.py             # Health endpoint behavior
│   └── test_startup.py            # Pre-flight check logic
├── docker-compose.yml             # 3-service orchestration
├── Dockerfile                     # Multi-stage build
├── pyproject.toml                 # Project metadata, deps, tool config
├── requirements.txt               # Pinned dependencies
├── requirements-dev.txt           # Dev dependencies
└── .env.example                   # Env var template (without secrets)
```

### Pattern 1: FastAPI Exception Handler with Fail-Secure Envelope

**What:** Global exception handler that catches all unhandled exceptions and returns an OpenAI-compatible error envelope with no sensitive data leakage.

**When to use:** All FastAPI apps requiring consistent error response format and fail-secure behavior.

**Example:**
```python
# src/anonreq/exceptions.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

class AnonReqError(Exception):
    """Base application error with machine-readable code."""
    def __init__(self, message: str, error_type: str, status_code: int = 500,
                 code: str = "internal_error", request_id: str | None = None):
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        self.code = code
        self.request_id = request_id

class DependencyUnavailableError(AnonReqError):
    """Dependency (Valkey, Presidio) is unreachable."""
    def __init__(self, dependency: str, request_id: str | None = None):
        super().__init__(
            message=f"{dependency} unavailable",
            error_type="service_unavailable",
            status_code=503,
            code="dependency_unavailable",
            request_id=request_id,
        )

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler: never leaks internals."""
    request_id = getattr(request.state, "request_id", None)
    if isinstance(exc, AnonReqError):
        body = {
            "error": {
                "message": exc.message,
                "type": exc.error_type,
                "code": exc.code,
                "request_id": exc.request_id or request_id,
            }
        }
    elif isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": exc.detail, "type": "http_error",
                               "code": "http_error", "request_id": request_id}},
        )
    else:
        body = {
            "error": {
                "message": "Internal gateway error",
                "type": "internal_error",
                "code": "internal_error",
                "request_id": request_id,
            }
        }
    return JSONResponse(status_code=getattr(exc, "status_code", 500), content=body)
```
[ASSUMED: Based on FastAPI exception handler documentation at fastapi.tiangolo.com/tutorial/handling-errors/]

### Pattern 2: structlog with Field Allowlist

**What:** Configure structlog with a custom processor that drops all fields not in an explicit allowlist, preventing accidental PII leakage.

**When to use:** Any application with strict no-PII-in-logs requirements.

**Example:**
```python
# src/anonreq/logging_config.py
import structlog
from structlog.stdlib import ProcessorFormatter

ALLOWLIST = {"timestamp", "level", "event", "request_id", "component",
             "status_code", "duration_ms", "error_type", "version"}

def allowlist_processor(logger, method_name, event_dict):
    """Drop any field not in the explicit allowlist."""
    keys = list(event_dict.keys())
    for key in keys:
        if key not in ALLOWLIST and key != "event":
            del event_dict[key]
    return event_dict

def setup_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            allowlist_processor,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    import logging
    handler = logging.StreamHandler()
    handler.setFormatter(ProcessorFormatter(processor=structlog.processors.JSONRenderer()))
    logging.basicConfig(handlers=[handler], level=level)
```
[ASSUMED: Based on structlog configuration patterns from structlog.org documentation]

### Pattern 3: FastAPI Lifespan with Pre-flight Checks

**What:** Use FastAPI's lifespan context manager to validate all dependencies before accepting traffic.

**When to use:** Any service with mandatory external dependencies that must be healthy at startup.

**Example:**
```python
# src/anonreq/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-flight checks: all dependencies must pass before serving."""
    log = logger.bind(component="lifespan")
    log.info("event", "Starting pre-flight checks")
    try:
        await run_startup_checks()  # Validates Valkey, Presidio connectivity
    except Exception as e:
        log.error("event", "Pre-flight check failed", error_type=type(e).__name__)
        raise  # uvicorn will exit — fail-secure
    log.info("event", "Pre-flight checks passed, accepting traffic")
    yield
    log.info("component", "lifespan", "event", "Shutting down")

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.add_exception_handler(Exception, global_exception_handler)
    return app
```
[ASSUMED: Based on FastAPI lifespan documentation at fastapi.tiangolo.com/advanced/events/]

### Pattern 4: HTTPBearer Authentication Dependency

**What:** FastAPI dependency that extracts and validates Bearer token from Authorization header.

**When to use:** API endpoints requiring static bearer token authentication.

**Example:**
```python
# src/anonreq/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from anonreq.config import settings

security = HTTPBearer(auto_error=True)

async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Validate the bearer token against configured API key."""
    token = credentials.credentials
    if token != settings.ANONREQ_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token
```
[ASSUMED: Based on FastAPI security documentation at fastapi.tiangolo.com/tutorial/security/]

### Pattern 5: RequestContext Data Class

**What:** Core context object propagated through every request via FastAPI dependencies.

**When to use:** Every request handler needs request_id, tenant_id, session_id for correlation.

**Example:**
```python
# src/anonreq/models/request_context.py
from dataclasses import dataclass, field
from uuid import uuid4

@dataclass
class RequestContext:
    request_id: str = field(default_factory=lambda: f"req_{uuid4().hex[:24]}")
    tenant_id: str = "default"
    session_id: str | None = None

# In dependencies.py:
from fastapi import Request

async def get_request_context(request: Request) -> RequestContext:
    """Extract or create the request context."""
    if not hasattr(request.state, "context"):
        request.state.context = RequestContext()
    return request.state.context
```
[ASSUMED: Based on Python dataclass patterns and FastAPI request.state documentation]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Configuration loading | Custom env var parser | `pydantic-settings` + YAML config | Validates types, supports nesting, reads `.env` files, built-in YAML support via `YamlConfigSettingsSource` |
| Structured JSON logging | Custom JSON formatting | `structlog` + `python-json-logger` | Processor pipeline for PII scrubbing, contextvars for request_id correlation, chainable `.bind()` |
| YAML parsing | Custom YAML loader | `pyyaml` | SafeLoader prevents arbitrary code execution |
| Bearer token auth | Manual Authorization header parsing | `fastapi.security.HTTPBearer` | Built-in scheme validation, auto-401 on missing/invalid, clean dependency injection |
| Async HTTP client | `urllib` or `requests` | `httpx` | Native async, connection pooling, timeout support, test client compatibility |
| Prometheus metrics | Custom metrics endpoint | `prometheus_client` | Standard exposition format, histogram/summary/counter types |
| Valkey/Redis client | Raw socket connections | `redis-py` (Async Redis) | Connection pool management, health check interval, pipelining, TTL management |
| UUID generation | `os.urandom` for IDs | `uuid` (stdlib) | Standard UUID4 generation for request_id, no external dependency needed |
| Time-based TTL management | Custom expiry logic | `redis-py expire` + EXPIRE | Redis EXPIRE is atomic and server-managed; no client-side timer needed |

**Key insight:** Every "Don't Hand-Roll" item above handles deceptively complex edge cases — connection failures, serialization edge cases, timing attacks, or security vulnerabilities. Custom solutions introduce risk without benefit.

## Common Pitfalls

### Pitfall 1: structlog allowlist doesn't catch nested dicts
**What goes wrong:** The allowlist processor drops top-level keys but nested dicts inside log calls can contain PII.
**Why it happens:** structlog's `event_dict` is a flat dict; values that are themselves dicts (e.g., `log.error("failed", details={"ip": user_ip})`) are not recursively checked.
**How to avoid:** Either (a) deep-check all dict values recursively, or (b) enforce audit metadata structure with Pydantic models. Approach (b) is preferred.
**Warning signs:** `details={"user_id": ...}` appearing in log calls during code review.

### Pitfall 2: FastAPI error responses include server header
**What goes wrong:** The error envelope is safe, but response headers may leak server version.
**Why it happens:** Uvicorn auto-adds `server` header with version by default.
**How to avoid:** Use `uvicorn --no-server-header` or strip headers in `JSONResponse`.
**Warning signs:** `server: uvicorn` appearing in error responses.

### Pitfall 3: HTTPBearer auto_error=True bypasses custom 401 format
**What goes wrong:** `HTTPBearer(auto_error=True)` raises `HTTPException(401)` before the route runs, so the custom global exception handler may not format it.
**Why it happens:** FastAPI handles HTTPExceptions internally before they reach the global handler.
**How to avoid:** Register `@app.exception_handler(HTTPException)` that catches 401s and formats them in the OpenAI-compatible envelope.
**Warning signs:** Auth errors returning `{"detail": "Not authenticated"}` instead of the OpenAI envelope.

### Pitfall 4: redis-py health_check_interval default disables health checks
**What goes wrong:** A Valkey connection silently broken between requests goes undetected for 300+ seconds.
**Why it happens:** Default `redis.Redis(health_check_interval=0)` means no health checks between commands.
**How to avoid:** Set `health_check_interval=5` (seconds) in the connection pool.
**Warning signs:** Intermittent `ConnectionError` only after long idle periods.

### Pitfall 5: Docker healthcheck race between services
**What goes wrong:** Gateway's `depends_on: condition: service_healthy` checks that Presidio and Valkey *started* healthy, but they may fail *after* startup.
**Why it happens:** `depends_on` is a startup ordering mechanism, not a runtime dependency tracker.
**How to avoid:** (a) Use `restart: unless-stopped`; (b) pre-flight check re-verifies at startup; (c) Forwarding_Guard re-checks before every outbound call.
**Warning signs:** Gateway returns 503 on first request even though Docker says "healthy".

### Pitfall 6: Missing src/ layout breaks pytest import
**What goes wrong:** `pytest` cannot import the application because `src/` layout is not in Python path.
**Why it happens:** Setting `package-dir = {"anonreq" = "src/anonreq"}` in pyproject.toml is not enough for pytest to resolve imports in test files.
**How to avoid:** Install the package in editable mode (`pip install -e .`) in CI and dev, or use `PYTHONPATH=src` in test config.
**Warning signs:** `ModuleNotFoundError: No module named 'anonreq'` when running tests.

## Code Examples

### Example 1: Docker Compose with Healthchecks

```yaml
# docker-compose.yml
services:
  valkey:
    image: valkey/valkey:8
    container_name: anonreq-valkey
    command: ["valkey-server", "--save", "", "--appendonly", "no"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 10s
    networks:
      - anonreq-net

  presidio-analyzer:
    image: mcr.microsoft.com/presidio-analyzer:latest
    container_name: anonreq-presidio
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/health"]
      interval: 15s
      timeout: 5s
      retries: 10
      start_period: 30s
    networks:
      - anonreq-net

  anonreq:
    build: .
    container_name: anonreq-gateway
    ports:
      - "8080:8080"
    environment:
      - ANONREQ_API_KEY=${ANONREQ_API_KEY:?err}
      - ANONREQ_VALKEY_URL=redis://valkey:6379/0
      - ANONREQ_PRESIDIO_URL=http://presidio-analyzer:5001
      - ANONREQ_LOG_LEVEL=INFO
    depends_on:
      valkey:
        condition: service_healthy
      presidio-analyzer:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 5s
    restart: unless-stopped
    networks:
      - anonreq-net

networks:
  anonreq-net:
    driver: bridge
```
[ASSUMED: Based on Docker Compose healthcheck documentation and presidio documentation]

### Example 2: pyproject.toml with src/ Layout

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=75.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "anonreq"
version = "0.1.0"
description = "Self-hosted anonymization gateway for LLM APIs"
requires-python = ">=3.12"
license = {text = "Apache-2.0"}

[project.optional-dependencies]
dev = [
    "pytest>=9.0",
    "pytest-asyncio>=1.2",
    "hypothesis>=6.100",
]

[tool.setuptools.packages.find]
where = ["src"]
include = ["anonreq*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
```
[ASSUMED: Based on setuptools documentation at setuptools.pypa.io]

### Example 3: Pydantic Settings with YAML Support

```python
# src/anonreq/config.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
from pydantic import Field, field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ANONREQ_",
        yaml_file="config/providers.yaml",
        extra="ignore",
    )

    # Required
    API_KEY: str = Field(min_length=32, validation_alias="ANONREQ_API_KEY")
    VALKEY_URL: str = Field(validation_alias="ANONREQ_VALKEY_URL")
    PRESIDIO_URL: str = Field(validation_alias="ANONREQ_PRESIDIO_URL")

    # Optional
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    LOG_LEVEL: str = "INFO"
    REQUEST_TIMEOUT_SECONDS: int = 30

    @field_validator("API_KEY")
    @classmethod
    def api_key_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("API_KEY must be at least 32 characters")
        return v

settings = Settings()  # type: ignore
```
[ASSUMED: Based on pydantic-settings documentation at docs.pydantic.dev]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Runtime | ✓ | 3.12.13 | Docker container (`python:3.12-slim`) |
| Python 3.14 | Host (dev) | ✓ | 3.14.6 | Use containerized 3.12 |
| pip3 | Package management | ✓ | 26.1.2 | Docker build manages pip |
| Docker | Containerization | ✓ | 29.5.3 | — |
| Docker Compose | Orchestration | ✓ | v5.1.4 | — |
| git | Version control | ✓ | 2.50.1 | — |
| curl | Healthcheck probes | ✓ | 8.7.1 | — |

**Missing dependencies with no fallback:** none — all required tools are present.
**Missing dependencies with fallback:** none — all tools available.

**Note on Python version mismatch:** Host has Python 3.14.6. Project requires 3.12. Python 3.12.13 is available at `/Users/aljaunia/.local/bin/python3.12`. Docker build uses `python:3.12-slim` image, so the runtime is correct. For local development, use `python3.12 -m venv .venv` or develop inside the Docker container.

## Validation Architecture

> `workflow.nyquist_validation` is enabled (true) in config.json.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Config file | `pyproject.toml` under `[tool.pytest.ini_options]` |
| Quick run command | `pytest -x --tb=short` |
| Full suite command | `pytest --cov=anonreq --cov-report=term-missing` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FAIL-01 | Global exception handler catches all unhandled errors, returns 500 with no leak | unit | `pytest tests/test_exceptions.py -x` | ❌ Wave 0 |
| FAIL-04 | Health endpoint returns correct status when deps healthy/unhealthy | unit | `pytest tests/test_health.py -x` | ❌ Wave 0 |
| AUDT-01 to AUDT-03 | Audit events are JSON, metadata-only, include request_id | unit | `pytest tests/test_logging.py -x` | ❌ Wave 0 |
| AUTH-MINIMAL-01 | 401 on missing/invalid token, 200 on valid token | unit | `pytest tests/test_auth.py -x` | ❌ Wave 0 |
| DOCK-01 to DOCK-06 | Docker Compose orchestrates 3 services with healthchecks | integration | `docker compose up -d && pytest tests/test_docker.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest -x --tb=short tests/test_<module>.py`
- **Per wave merge:** `pytest --cov=anonreq --cov-report=term-missing`
- **Phase gate:** Full suite green before `/gsd-verify-work` (including Docker integration tests)

### Wave 0 Gaps
- [ ] `tests/test_config.py` — covers FAIL-01 config validation, startup checks
- [ ] `tests/test_auth.py` — covers AUTH-MINIMAL-01 auth scenarios
- [ ] `tests/test_exceptions.py` — covers FAIL-01, FAIL-02 exception handler behavior
- [ ] `tests/test_logging.py` — covers AUDT-01, AUDT-02, AUDT-03 allowlist enforcement
- [ ] `tests/test_health.py` — covers FAIL-04 health endpoint
- [ ] `tests/conftest.py` — shared fixtures (test client, mock Valkey, mock Presidio)
- [ ] Framework install: `pip install pytest pytest-asyncio hypothesis` — if none detected

## Security Domain

> `security_enforcement` is enabled (true) in config.json.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `HTTPBearer` dependency with constant-time comparison for API key |
| V3 Session Management | partial | Session-scoped Valkey mappings (TTL-managed, no persistent sessions in Phase 1) |
| V4 Access Control | yes | Static bearer token checked on every protected route |
| V5 Input Validation | yes | Pydantic v2 validation on all Settings; FastAPI request body validation |
| V6 Cryptography | no | No crypto in Phase 1 (Phase 7 handles encryption at rest) |
| V7 Error Handling | yes | Global exception handler with no info leakage — D-02 envelope format |
| V8 Data Protection | no | No sensitive data storage in Phase 1 |
| V9 Communications | partial | Docker internal network; TLS termination deferred to reverse proxy (Phase 5) |
| V10 Malicious Code | no | Code integrity checks deferred |
| V11 Business Logic | partial | Forwarding_Guard (D-03) prevents unsanitized forwarding |
| V12 Files & Resources | no | No file uploads in Phase 1 |
| V13 API & Web Services | yes | FastAPI input validation, structured error responses, rate limiting prepped for Phase 6 |
| V14 Configuration | yes | Pydantic Settings `extra="ignore"` prevents unknown env var injection; API_KEY min length validation |

### Known Threat Patterns for FastAPI + Docker Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key brute force via Authorization header | Tampering | FastAPI HTTPBearer auto-401 on wrong key; rate limiting (Phase 6) |
| Internal network eavesdropping | Information Disclosure | Docker internal bridge network — services communicate within isolated network |
| Denial of service via slow HTTP | Denial of Service | Uvicorn with `--limit-concurrency`; request timeout in Settings |
| Configuration injection via env vars | Elevation of Privilege | Pydantic Settings `extra="ignore"` + `field_validator` constraints |
| Unhandled exception leaking stack traces | Information Disclosure | Global exception handler catches all Exception types; non-AnonReqError returns generic 500 |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | FastAPI `@app.exception_handler(Exception)` catches all unhandled exceptions including those raised in middleware | Code Examples | If FastAPI middleware exceptions bypass the handler, stack traces could leak — verify in Phase 2 testing |
| A2 | `redis-py` 8.0.0 is fully compatible with `valkey/valkey:8` | Standard Stack | Valkey 8 uses RESP3 by default; redis-py 8.0 may have compatibility edge cases — pin Valkey to RESP2 mode if needed |
| A3 | `mcr.microsoft.com/presidio-analyzer:latest` exposes `/health` endpoint | Architecture Patterns | May not exist in all versions — verify and potentially build a custom healthcheck |
| A4 | Pydantic Settings `YamlConfigSettingsSource` is available in v2.14.2 | Standard Stack | Was introduced in 2.0 but may work differently than documented — verify in implementation |
| A5 | structlog allowlist processor is sufficient for no-PII guarantee | Common Pitfalls | Nested dict values can bypass top-level allowlist — recursive deep-check may be needed |
| A6 | `python-json-logger` 4.x is compatible with structlog 26.x | Standard Stack | Both are stable libraries but major version bumps could break compatibility — pin exact versions |

## Open Questions

1. **Presidio Analyzer healthcheck endpoint**
   - What we know: Presidio Analyzer exposes `POST /analyze` at port 5001. Health endpoint path is undocumented.
   - What's unclear: Whether `GET /health` or `GET /` returns 200 for healthcheck purposes.
   - Recommendation: Implement gateway startup check by calling `POST /analyze` with a minimal payload and checking response is 200/422 (not 500). Fall back to a TCP port check.

2. **Valkey RESP compatibility mode**
   - What we know: `valkey/valkey:8` defaults to RESP3. `redis-py` 8.0 supports RESP3.
   - What's unclear: Whether `redis-py` 8.0 correctly negotiates RESP3 with Valkey 8, or if `valkey-server` needs `--enable-protected-configs local --enable-debug-command local --resp2-only` for compatibility.
   - Recommendation: Test connection in Phase 01-02 and add RESP2 fallback flag to `docker-compose.yml` if needed.

3. **structlog + python-json-logger compatibility**
   - What we know: D-07 specifies `python-json-logger` as structlog renderer. structlog 26.x has its own `JSONRenderer`.
   - What's unclear: Whether `python-json-logger` adds value over structlog's built-in `JSONRenderer`.
   - Recommendation: Use structlog's built-in `JSONRenderer` unless python-json-logger's specific output format is required. Both emit newline-delimited JSON.

4. **RequestContext population timing**
   - What we know: `RequestContext` needs `request_id` before exception handler runs (for error envelope).
   - What's unclear: Whether the middleware/dependency that creates `RequestContext` runs before `HTTPBearer` raises 401.
   - Recommendation: Use FastAPI middleware (not route-level dependency) to set `request_id` on `request.state` so it's available to the exception handler even on auth failures.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FastAPI `on_event("startup")` | FastAPI lifespan context manager | FastAPI 0.89 (Dec 2022) | Lifespan is the recommended pattern; `on_event` is soft-deprecated |
| Pydantic `BaseSettings` (v1) | `pydantic_settings.BaseSettings` (v2) | Pydantic v2 / pydantic-settings 2.0 (2023) | Separate package, different import path, improved YAML support |
| `uvicorn` as dev dependency | `uvicorn[standard]` | Ongoing | `[standard]` extra includes `httptools`, `uvloop`, `websockets` for production performance |
| `valkey-py` (new client) | `redis-py` (established client) | 2024 | redis-py supports Valkey protocol; no need to switch to valkey-py |
| Python 3.12 | Python 3.14 (latest) | Oct 2025 | Project pins 3.12 per AGENTS.md; Docker image `python:3.12-slim` ensures correct version |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: npm registry] Package versions confirmed via `python3 -m pip index versions <package>`
- [VERIFIED: gsd-tools] Package legitimacy confirmed via `gsd-tools query package-legitimacy check --ecosystem pypi`
- [VERIFIED: Environment] Tool availability confirmed via `command -v`, `--version`

### Secondary (MEDIUM confidence)
- [CITED: fastapi.tiangolo.com] FastAPI exception handlers, HTTPBearer, lifespan pattern
- [CITED: structlog.org] structlog processor pipeline, contextvars, JSONRenderer
- [CITED: docs.pydantic.dev] Pydantic Settings v2, YAML config source
- [CITED: redis-py.readthedocs.io] redis-py connection pools, health_check_interval, async support
- [CITED: docs.docker.com] Docker Compose healthcheck, condition: service_healthy

### Tertiary (LOW confidence)
- [ASSUMED] Presidio Analyzer health endpoint exists at GET /health
- [ASSUMED] redis-py 8.0 fully compatible with Valkey 8 RESP3
- [ASSUMED] pydantic-settings YamlConfigSettingsSource works as documented in v2.14.2

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified on PyPI, libraries well-documented
- Architecture: MEDIUM — patterns based on official docs but not tested against this project's specific Docker/Valkey/Presidio setup
- Pitfalls: MEDIUM — common pitfalls documented in community, but Valkey-specific edge cases not verified
- Package audit: MEDIUM — gsd-tools flagged all as SUS due to missing download stats; human override applied based on known reputation

**Research date:** 2026-06-20
**Valid until:** 2026-07-20 (30-day validity for stable stack; config/policy patterns stable)
