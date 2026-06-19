# Research Summary: AnonReq — Self-Hosted LLM Anonymization Gateway

**Domain:** PII detection + anonymization proxy for LLM API calls
**Researched:** 2026-06-19
**Overall confidence:** HIGH

## Executive Summary

AnonReq is a FastAPI-based reverse proxy that intercepts outbound LLM API calls, detects and replaces Personally Identifiable Information (PII) with context-preserving placeholder tokens, forwards sanitized requests to external LLM providers (OpenAI, Anthropic, Gemini, Ollama), and restores the original values in responses — all within the customer's secure perimeter.

The architecture follows a clean sidecar pattern: the FastAPI gateway process remains lightweight (~100-200MB) and delegates heavy NER-based PII detection to Microsoft Presidio Analyzer running as an independent container. Valkey (ephemeral Redis-compatible) stores per-request token-to-value mappings in-memory with persistence disabled, ensuring no sensitive data ever touches disk.

The key architectural finding is that the request pipeline is best implemented as a **composable step sequence within the route handler**, not as ASGI middleware. This avoids the well-documented limitations of Starlette's `BaseHTTPMiddleware` with streaming responses and gives the pipeline direct access to Pydantic-validated schemas. SSE streaming uses a Tail_Buffer state machine that handles split tokens across chunk boundaries with a 50-chunk / 500ms flush heuristic.

The recommended stack (Python 3.12, FastAPI, Presidio Analyzer, Valkey, HTTPX) is battle-tested and well-documented. The build order prioritizes the non-streaming pipeline first (Phase 2), then fail-secure guarantees (Phase 3), then multi-provider support (Phase 4), and finally SSE streaming (Phase 5), because streaming depends on both the core pipeline and fail-secure patterns being established.

## Key Findings

**Stack:** Python 3.12 + FastAPI + Presidio Analyzer (sidecar) + Valkey/Redis + HTTPX + Hypothesis (testing)
**Architecture:** Route-handler-based pipeline orchestration with ASGI middleware reserved for cross-cutting concerns (fail-secure, timing, auth). Component boundaries: Presidio = sidecar, Tokenization/Restoration = in-process, Valkey = external container.
**Critical pitfall:** Do NOT use `BaseHTTPMiddleware` to wrap SSE streaming responses — it buffers the entire body. Do NOT load Presidio in-process — it adds 1-2GB memory per worker.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Phase 1: Foundation** — Project scaffold, settings, logging, health endpoint
   - Addresses: Configuration management, structured audit logging
   - Avoids: Shipping without health probes or startup validation

2. **Phase 2: Core Pipeline (Non-Streaming)** — Text extraction, detection client, tokenization, caching, restoration, OpenAI passthrough
   - Addresses: Core anonymization round-trip (Req 1)
   - Avoids: Attempting streaming without a working non-streaming pipeline first

3. **Phase 3: Fail-Secure Architecture** — Error boundaries, health probes, pre-flight checks, timeouts
   - Addresses: Req 2 (fail-secure guarantee)
   - Avoids: Shipping without the fail-secure guarantees that the product is built around

4. **Phase 4: Multi-Provider Support** — Anthropic, Gemini, Ollama adapters, model routing
   - Addresses: Req 7 (multi-provider)
   - Avoids: Provider coupling in the core pipeline design

5. **Phase 5: SSE Streaming** — Tail_Buffer, streaming route path, TTL extension, post-stream verification
   - Addresses: Req 6 (SSE streaming) — depends on Phases 2-4 being complete
   - Avoids: Building streaming without understanding the full request/response lifecycle

6. **Phase 6: Multi-Locale Detection** — 8 locale bundles, checksum validation, header parsing
   - Addresses: Req 8 (multilingual)
   - Avoids: Locking into English-only detection before architecture supports extensibility

7. **Phase 7: Configuration & Observability** — Hot-reload, custom recognizers, Prometheus metrics, compliance presets, token verification
   - Addresses: Reqs 9-13
   - Avoids: Releasing without operational tooling

**Phase ordering rationale:**
- The non-streaming pipeline is the simplest complete path to a working product — it should ship first.
- Fail-secure is the product's core guarantee and must be wired before any provider traffic flows.
- Multi-provider depends on the core pipeline but not on streaming — they can be parallelized.
- SSE streaming is the most complex component and benefits from having all other pieces stabilized.

**Research flags for phases:**
- Phase 5 (SSE Streaming): Needs deeper research into FastAPI's `EventSourceResponse` lifecycle and cancellation semantics; the Tail_Buffer state machine design is established but the interaction with ASGI shutdown signals needs implementation-time testing.
- Phase 6 (Multi-Locale): Requires creating Presidio custom recognizer YAML files per locale — well-understood pattern but labor-intensive.
- Phase 7 (Hot-reload): Requires `watchfiles` / `awatch` integration; the RCU swap pattern is standard but thread-safety with ASGI needs attention.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Python 3.12 + FastAPI + Presidio + Valkey is a proven combination. Presidio's Docker deployment is well-documented. HTTPX is the standard async HTTP client for FastAPI. |
| Features | HIGH | Requirements (Req 1-21) are well-specified with clear acceptance criteria. The feature set maps cleanly to the component architecture. |
| Architecture | HIGH | Sidecar pattern for Presidio, in-process tokenization/restoration, route-handler pipeline composition are all well-understood patterns. SSE Tail_Buffer is novel but the state machine design is straightforward. |
| Pitfalls | HIGH | Anti-patterns documented — BaseHTTPMiddleware with SSE, per-chunk cache lookups, in-process NER models — are known issues with clear workarounds. |

## Gaps to Address

- **Presidio Analyzer version compatibility**: The latest Presidio v2.x Docker image version should be verified at implementation time (the v2 docs reference separate analyzer + anonymizer containers; AnonReq only needs the analyzer).
- **FastAPI `EventSourceResponse` cancellation**: How does ASGI cancellation propagate when a client disconnects mid-stream? Needs testing — the `request.is_disconnected()` pattern is documented but behavior with long-running LLM streams needs verification.
- **Valkey vs Redis compatibility**: Requirements specify Valkey as the preferred in-memory store. Valkey's API is Redis 7.2-compatible, but the `redis-py` client compatibility should be confirmed with the exact Valkey version specified in docker-compose.
- **Multi-stage Dockerfile model download**: The spaCy/transformers model must be downloaded in a build stage for Presidio's Docker image. The `presidio-analyzer` Docker image from MCR handles this, but custom locale recognizers may require additional model artifacts.
