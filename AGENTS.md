# AGENTS.md

## Project status

Greenfield — only requirements documents exist.

## Source of truth

- `req/requirements.md` — core requirements (Req 1–21)
- `req/requirements_v2.md` — enterprise/Appliance requirements (Req 22–56)
- `AnonReq_Requirements_v1.0.docx` — same as above (original source, may drift)

Read both `.md` files before writing any code or making architectural decisions. The `.docx` is the authoritative source if `.md` files are stale.

## What this project builds

AnonReq: self-hosted anonymization gateway that sits between enterprise apps and external LLM APIs. Intercepts outbound requests, detects/replaces PII with tokens, forwards sanitized data to OpenAI/Anthropic/Gemini/Ollama, restores tokens in responses. All in-memory, no data written to disk.

## Architecture at a glance

- **Gateway** — FastAPI proxy, the single entrypoint
- **Detection Engine** — hybrid regex + NER (Microsoft Presidio Analyzer) pipeline
- **Tokenization Engine** — replaces entity spans with `[TYPE_N]` placeholders
- **Restoration Engine** — reverses tokenization in LLM responses (supports SSE streaming with Tail_Buffer for split tokens)
- **Cache Manager** — Valkey/Redis, ephemeral, persistence disabled, TTL-based eviction
- **Provider Adapter** — translates OpenAI schema → Anthropic/Gemini/Ollama formats
- **Audit Logger** — structured JSON to stdout, metadata only, no raw values
- **Health/Metrics** — `/health`, `/metrics` (Prometheus)

Deployed via Docker Compose: `anonreq` + `presidio` + `valkey`. Multi-stage Dockerfile, Python 3.12-slim.

## Key constraints to preserve

- **Fail-secure**: any error → HTTP 5xx, never forward unsanitized data
- **No PII in logs**: metadata-only audit; field allowlist enforced
- **Ephemeral cache only**: Redis with `save ""`, no AOF, no RDB
- **Token format**: `[TYPE_N]` — case-insensitive + bracket-optional matching during restoration
- **OpenAI-compatible input schema**: single wire protocol, adapters for other providers
- **Session-scoped mapping**: `anonreq:{Session_ID}` key, TTL 60–3600s, deleted post-response
- **Multi-locale**: `X-AnonReq-Locale` header, 8 locales, locale-specific recognizer bundles

## Testing requirements (Req 16)

Property-based tests (Hypothesis) for:
- round-trip correctness (anonymize → restore → byte-for-byte match)
- token uniqueness and deduplication invariants
- fail-secure invariants (detection/cache/timeout → HTTP 500, 0 forwarded)
- locale checksum validation
- no-PII-in-logs
- streaming round-trip (split at every possible Token index)
- cross-request token randomization (1000+ session pairs, probability ≥ 1 − 2⁻³²)

## Tech stack (from requirements)

- Python 3.12, FastAPI, Presidio Analyzer, Valkey/Redis, Prometheus client
- Docker Compose, multi-stage Dockerfile
- License: Apache 2.0

## No code yet

No source code, no build system, no CI, no tests, no git repo exist. Everything here is pre-implementation requirements.
