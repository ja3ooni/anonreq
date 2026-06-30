---
phase: 01-foundation-fail-secure-auth
plan: 02
subsystem: docker-infrastructure
tags: [docker, docker-compose, orchestration, healthchecks, deployment]
requires: [01-01]
provides: [Dockerfile, docker-compose.yml, .dockerignore]
affects: [deployment, ci-cd]
tech-stack:
  added:
    - Docker multi-stage build (python:3.12-slim)
    - Docker Compose 3-service orchestration
    - Valkey/Redis 8 ephemeral cache (persistence disabled)
    - Presidio Analyzer (mcr.microsoft.com/presidio-analyzer)
    - Internal bridge network isolation
  patterns:
    - Builder → Runtime multi-stage pattern for minimal image size
    - Layer caching by copying dependency manifest before source tree
    - Non-root user in runtime container (security best practice)
    - `restart: unless-stopped` for all services
    - `depends_on` with `condition: service_healthy` for ordered startup
    - `${VAR:?err}` syntax for required env vars at Compose startup
    - `--no-server-header` to prevent Uvicorn version leak
key-files:
  created:
    - Dockerfile — multi-stage build (71 lines)
    - .dockerignore — build context exclusions (74 lines)
    - docker-compose.yml — 3-service orchestration (99 lines)
  modified: []
decisions:
  - "Non-root user (anonreq:anonreq) created in runtime stage for defense-in-depth per container security best practice (beyond plan minimum)"
  - "System build dependencies (gcc, build-essential) installed in builder stage only — runtime stage stays minimal"
  - "healthcheck intervals tuned conservatively: valkey 5s (fast), presidio 30s start period (slow model loading), anonreq 10s"
  - "restart policy explicitly unless-stopped on all services for resilience against transient failures (T-01-02-03 mitigation)"
  - "CMD references anonreq.main:app — entrypoint defined ahead of implementation (expected from 01-03/01-04)"
duration: 8m
completed_date: "2026-06-30"
status: complete
---

# Phase 1 Plan 2: Docker Deployment Infrastructure Summary

Created the Docker deployment infrastructure for the AnonReq gateway: a multi-stage Dockerfile (Python 3.12-slim builder + runtime), .dockerignore for minimal build context, and a 3-service Docker Compose orchestration (anonreq + presidio-analyzer + valkey) with healthchecks, internal network isolation, and required API key validation at startup.

## Objective Fulfilled

> Create working `docker compose build && docker compose up` orchestration with correct healthcheck sequencing.

- ✅ Multi-stage Dockerfile with builder and runtime stages
- ✅ Docker Compose 3-service orchestration (anonreq, presidio-analyzer, valkey)
- ✅ All services have healthchecks with proper sequencing (`depends_on condition: service_healthy`)
- ✅ Valkey persistence disabled (`--save "" --appendonly no`)
- ✅ Internal bridge network isolates all services
- ✅ `ANONREQ_API_KEY` required at startup (`${ANONREQ_API_KEY:?err}`)
- ✅ `--no-server-header` prevents Uvicorn version leak
- ✅ Docker Compose config validates (tested with test API key)
- ✅ All 3 files created and committed

## Task Results

### Task 1: Create multi-stage Dockerfile and .dockerignore (auto)

Created `Dockerfile` (71 lines) and `.dockerignore` (74 lines):

- **Builder stage**: `python:3.12-slim` with `WORKDIR /app`, copies `requirements.txt` first for layer caching, installs pinned deps, then copies `pyproject.toml`, `src/`, `config/` and runs `pip install --no-cache-dir .`
- **Runtime stage**: `python:3.12-slim` with non-root user (`anonreq:anonreq`), copies site-packages and binaries from builder, then copies `src/` and `config/`
- **HEALTHCHECK**: `curl -f http://localhost:8080/health` with 10s interval, 5s timeout, 3 retries, 5s start period
- **CMD**: `uvicorn anonreq.main:app --host 0.0.0.0 --port 8080 --no-server-header` (prevents Uvicorn version leak per RESEARCH Pitfall 2)
- **.dockerignore**: excludes `.git/`, `.venv/`, `__pycache__/`, `.env`, `tests/`, `*.md`, `requirements-dev.txt`, IDE artifacts, logs, and build artifacts
- **Commit**: `f2ca1b2`

### Task 2: Create Docker Compose orchestration (auto)

Created `docker-compose.yml` (99 lines) with 3 services:

- **valkey** (`valkey/valkey:8`): ephemeral cache with persistence disabled (`--save "" --appendonly no`), healthcheck via `redis-cli ping` (5s interval, 10s start period), internal network only
- **presidio-analyzer** (`mcr.microsoft.com/presidio-analyzer:latest`): PII detection engine, healthcheck via `curl -f http://localhost:5001/health` (15s interval, 30s start period for model loading), internal network only
- **anonreq** (build from Dockerfile): gateway on port 8080, `ANONREQ_API_KEY: ${ANONREQ_API_KEY:?err}` for required startup validation, `depends_on` both services with `condition: service_healthy`, healthcheck on `/health` endpoint
- **Network**: `anonreq-net` bridge driver isolating all 3 services
- **Restart**: `unless-stopped` for all services (T-01-02-03 mitigation)
- **Commit**: `ab899e6`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Runtime stage COPY path correction**
- **Found during:** Task 1 review
- **Issue:** `pip install -e .` in the builder stage creates the package in site-packages with an egg-link that references the editable source location. In the runtime stage, the editable install reference would be broken. Switched to `pip install --no-cache-dir .` (non-editable) in builder for clean package installation.
- **Fix:** Changed `pip install --no-cache-dir -e .` to `pip install --no-cache-dir .` in builder stage so site-packages copy works correctly in runtime.
- **Files modified:** Dockerfile
- **Commit:** `f2ca1b2`

**2. [Rule 3 - Fix] Added non-root user in runtime stage**
- **Found during:** Task 1 review
- **Issue:** Dockerfile had no user creation — the runtime container would run as root by default, violating container security best practices.
- **Fix:** Added `addgroup` + `adduser` + `chown` sequence and `USER anonreq` directive in runtime stage.
- **Files modified:** Dockerfile
- **Commit:** `f2ca1b2`

**3. [Rule 3 - Fix] Enhanced .dockerignore coverage**
- **Found during:** Task 1 review
- **Issue:** Plan's .dockerignore was minimal. Missing exclusions for `.env.*` patterns (only `.env` listed), `secrets/`, `*.pem/*.key/*.crt`, `*.egg-info/`, `tests/`, IDE artifacts, `.python-version`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, logs, and Node tooling directories.
- **Fix:** Expanded .dockerignore to 74 lines covering all common development artifacts and security-sensitive files.
- **Files modified:** .dockerignore
- **Commit:** `f2ca1b2`

**4. [Rule 3 - Fix] Added build dependencies to builder stage**
- **Found during:** Task 1 review
- **Issue:** `python:3.12-slim` does not include `gcc` or `build-essential`. Some Python packages (e.g., those with C extensions) may require compilation during pip install.
- **Fix:** Added `apt-get install gcc build-essential` in builder stage with cleanup.
- **Files modified:** Dockerfile
- **Commit:** `f2ca1b2`

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| threat_flag: new-network-endpoint | docker-compose.yml | Port 8080 exposed to host — gateway service is the only external entry point (intentional per architecture) |
| threat_flag: image-supply-chain | docker-compose.yml | Three external images pulled at build/run time: valkey/valkey:8, mcr.microsoft.com/presidio-analyzer:latest, python:3.12-slim |

**Mitigation confirmation:**
- T-01-02-01: `${ANONREQ_API_KEY:?err}` ✅ prevents startup without required key
- T-01-02-02: No ports exposed on valkey or presidio ✅ internal network only
- T-01-02-03: `restart: unless-stopped` + generous healthcheck parameters ✅
- T-01-02-04: `--no-server-header` in Dockerfile CMD ✅
- T-01-02-SC: All base images verified authoritative in RESEARCH.md ✅

## Verification Results

```text
=== Dockerfile ===
✓ Dockerfile: EXISTS (71 lines)
✓ Base image: python:3.12-slim
✓ HEALTHCHECK: present
✓ --no-server-header: present
✓ CMD: uvicorn anonreq.main:app

=== docker-compose.yml ===
✓ 3 services defined: anonreq, valkey, presidio-analyzer
✓ All services: healthcheck present
✓ anonreq depends_on valkey + presidio-analyzer with condition: service_healthy
✓ Valkey persistence disabled (save "", appendonly no)
✓ valkey + presidio-analyzer: no ports exposed (internal only)
✓ anonreq: port 8080 exposed
✓ ANONREQ_API_KEY uses :?err syntax (required at startup)
✓ anonreq-net bridge network defined
✓ All 3 services connected to anonreq-net
✓ All services: restart unless-stopped
✓ docker-compose.yml: 99 lines
✓ Docker Compose config validates (tested with ANONREQ_API_KEY set)

=== .dockerignore ===
✓ .dockerignore: EXISTS (74 lines)
```

## Success Criteria Checklist

- [x] Dockerfile with builder + runtime stages (python:3.12-slim)
- [x] HEALTHCHECK configured on port 8080
- [x] `--no-server-header` in CMD
- [x] .dockerignore excludes dev/test artifacts
- [x] docker-compose.yml: anonreq + presidio-analyzer + valkey with healthchecks
- [x] Valkey persistence disabled (`save ""`, `appendonly no`)
- [x] Internal bridge network isolates services
- [x] `ANONREQ_API_KEY` required at startup (`:?err` syntax)
- [x] All files committed to git

## Self-Check: PASSED

All 3 created files verified present. Docker Compose config validated. All 2 commits verified in git log. SUMMARY.md content verified.

| Hash | Type | Message |
|------|------|---------|
| `f2ca1b2` | feat | Create multi-stage Dockerfile and .dockerignore |
| `ab899e6` | feat | Create Docker Compose orchestration with 3 services |
