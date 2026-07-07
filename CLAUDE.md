# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

AnonReq: a self-hosted, fail-secure anonymization gateway between enterprise apps and external LLM APIs. It accepts OpenAI-compatible requests, detects PII (regex + Microsoft Presidio NER), replaces entity spans with `[TYPE_N]` tokens, forwards the sanitized request to a provider (OpenAI/Anthropic/Gemini/Ollama), and restores tokens in the response — including SSE streams. Python 3.12, FastAPI, managed with `uv`.

## Commands

```bash
uv sync                                          # install deps (dev extras included)
uv run pytest                                    # full test suite
uv run pytest tests/test_cache.py                # single file
uv run pytest tests/test_cache.py::test_name     # single test
uv run pytest tests/property/                    # Hypothesis property tests
uv run pytest -m load                            # load/concurrency tests (only custom marker)
uv run uvicorn anonreq.main:app --port 8080 --reload   # run gateway locally
docker-compose up --build                        # full stack: gateway + Valkey + Presidio
```

- Tests need no `.env` or running services for most suites: `tests/conftest.py` sets required `ANONREQ_*` env vars at import time and provides a `fakeredis`-backed `cache_manager` fixture. Upstream HTTP is mocked with `respx`.
- Running the gateway locally requires Valkey/Redis at `redis://localhost:6379/0` and Presidio Analyzer at `http://localhost:5001`.
- `pytest` is configured in `pyproject.toml`: `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed), `pythonpath = ["src"]`.
- No linter/formatter is configured in this repo.

## Critical invariants (do not break)

These come from the requirements in `req/` and `AGENTS.md` and are enforced by property tests:

- **Fail-secure**: any pipeline error (detection, cache, parsing, timeout) must abort with HTTP 5xx. Never forward unsanitized data upstream. `pipeline/forwarding_guard.py` and the global exception handlers in `exceptions.py` implement this.
- **No PII in logs**: structured JSON logging to stdout with a field allowlist (`logging_config.py`). Never log raw prompt/response values.
- **Ephemeral cache only**: Valkey/Redis with persistence disabled. Token mappings are session-scoped (`anonreq:{Session_ID}`), TTL 60–3600s, deleted after response processing. Nothing sensitive touches disk.
- **Token format**: `[TYPE_N]`; restoration must match case-insensitively and with optional brackets (LLMs mangle tokens).
- **Round-trip correctness**: anonymize → restore must be byte-for-byte identical, including streaming responses split at any byte index (Tail Buffer in `streaming/`).
- **Config singleton**: `config.py` instantiates `settings = Settings()` at import time with `ANONREQ_`-prefixed env vars. Required vars must be in the environment *before* any `anonreq` import — this is why `conftest.py` sets them at module level, not in a fixture.

## Architecture

Entry point is `create_app()` in `src/anonreq/main.py`, which wires everything: logging, lifespan startup checks (dependencies unhealthy → refuse to start), middleware (request_id before auth, then metrics/classification/policy), and all routers. Shared state (CacheManager, registries, services) lives on `app.state`.

**Core request flow** (`pipeline/`, orchestrated by `pipeline/manager.py` and built in `routing/chat.py`): extraction → detection → tokenization → forwarding guard → provider call → restoration → cleanup. Each stage is in its own module under `pipeline/`. Supporting engines:

- `detection/` — hybrid regex + Presidio client
- `tokenization/`, `restore/`, `streaming/` — token generation, response restoration, SSE parsing with tail buffer
- `providers/` — OpenAI-schema → Anthropic/Gemini/Ollama adapters behind `ProviderRegistry`
- `routing/` — model alias registry and route selection
- `cache/` — Valkey/Redis session mapping manager
- `locale/` — 8-locale recognizer bundles selected via `X-AnonReq-Locale` header, with checksum validation

**Enterprise layers** (built in later phases, layered around the core pipeline): `policy/`, `classification/`, `compliance/` (middleware-enforced), `services/` (audit chain with hash chaining + anchoring, breach detection, DSAR, e-discovery, SLO engine, retention), `admin/` and `api/v1/admin/` (admin REST APIs), `proxy/` (TLS MITM interception + CA manager), `gateway/` (transparent AI-traffic detection/routing), plus `firewall/`, `casb/`, `rag/`, `agent/`, `multimodal/`, `governance/`, `incidents/`.

**Configuration**: env vars via pydantic-settings (`ANONREQ_` prefix, see `.env.example`) for runtime settings; YAML files in `config/` (policy, classification, compliance presets, audit, export, model aliases, locales) for behavior. Alembic (`alembic/`) manages migrations for the audit database.

**Dependency gotcha**: `sqlalchemy` (and alembic) are imported by `main.py` and the audit services but are *not* declared in `pyproject.toml`, `requirements.txt`, or `uv.lock`. If you touch dependencies, declare them in `pyproject.toml` and keep the pinned `requirements*.txt` files in sync (they are generated mirrors for reproducible builds).

## Planning docs

Development follows a phased roadmap (GSD workflow). Source of truth for requirements: `req/requirements.md` (Req 1–21) and `req/requirements_v2.md` (Req 22–56); design docs in `req/` (PRD/HLD/LLD). Live project state is in `.planning/` (`ROADMAP.md`, `STATE.md`, per-phase plans) and per-phase artifacts in `phases/`. Note that `AGENTS.md` still says "greenfield / no code yet" — that is stale; the implementation is well past Phase 8.
