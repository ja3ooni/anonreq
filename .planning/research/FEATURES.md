# Feature Landscape

**Domain:** Self-hosted LLM Anonymization Gateway
**Researched:** 2026-06-19

## Table Stakes

Features users expect from any LLM proxy/PII gateway. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| OpenAI-compatible endpoint | `POST /v1/chat/completions` is the universal wire protocol | Low | Just FastAPI + Pydantic schema matching the OpenAI spec. All major LLM clients (openai-python, langchain, llamaindex) support base_url override. |
| PII detection (email, phone, SSN, credit card, names, addresses) | Core value prop — must catch common PII out of the box | Medium | Presidio ships with built-in recognizers for US/EU PII. Regex patterns for CC# (Luhn), phone (E.164), email, SSN are well-known. |
| Token replacement (`[NAME_1]`) | Informative placeholders preserve LLM reasoning ability | Low | Simple string replacement in reverse span order. Format `[TYPE_N]` is compact and context-preserving. |
| Token restoration in responses | Needed for round-trip correctness | Low | String replacement of `[TYPE_N]` with original values. Case-insensitive + bracket-optional matching adds slight complexity. |
| SSE streaming | Real-time chat apps require streaming responses | High | Tail_Buffer state machine for split tokens across chunk boundaries. Pre-fetch cache at stream start. |
| Multi-provider routing (OpenAI, Anthropic, Gemini) | Enterprise users have existing provider contracts | Medium | Schema translation layer. OpenAI → Anthropic Messages API, OpenAI → Gemini contents[], Ollama = passthrough. |
| Fail-secure: any error → HTTP 5xx, never forward unsanitized data | Core trust guarantee for compliance teams | Medium | Error boundary middleware, per-component health probes, pre-flight startup checks, detection timeout handling. |
| Docker Compose deployment | `docker compose up` must work | Low | Req 12 specifies this exactly. Three services: anonreq, presidio, valkey. Health check dependencies. |
| Health endpoint (`GET /health`) | Kubernetes liveness/readiness probes | Low | Returns 200 only when Presidio + Valkey are healthy. Returns 503 with degraded component info. |
| Metadata-only audit logging | Audit trail without PII liability | Medium | Structured JSON to stdout. Field allowlist enforced. Empty prompt/response in logs = compliance requirement. |

## Differentiators

Features that set AnonReq apart from open-source alternatives (e.g., direct Presidio usage, generic MITM proxies).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Ephemeral, provably-deleted mapping store** | Cache with `save ""`, no AOF, no RDB. Configuration includes `MONITOR`/`SLOWLOG` disable to prevent operational leak. | Low | Most PII tools write to persistent DB. AnonReq's in-memory-only architecture is a differentiator for compliance teams. |
| **Per-jurisdiction compliance presets (GDPR, LGPD, PDPA, POPIA)** | Select a named regulation; gateway auto-configures entity types and thresholds | Medium | Preset defines mandatory entity types + minimum confidence thresholds. Multiple presets merge as union-of-entities, highest-threshold. |
| **Cross-request token randomization** | Same value in different sessions = different token strings, preventing token-based correlation attacks | Low | Cryptographically random seed per session drives token index assignment. `P(duplicate) ≥ 1 − 2⁻³²` across 1000+ sessions. |
| **Multi-locale PII detection (8 locales)** | German Steuer-ID, French NIR, Dutch BSN, Brazilian CPF/CNPJ, Italian Codice Fiscale, Arabic GCC national IDs | High | Each locale needs regex patterns + checksum validation. Presidio's recognizer architecture supports locale bundles loaded from config files. |
| **Post-restoration token verification** | Scan response for residual `[TYPE_N]` tokens before delivery | Low | Simple regex scan. Logs warning if any remain — doesn't block, but signals misconfiguration. |
| **Prompt injection detection** | Block jailbreak/direct injection attempts at gateway level | Medium | Pattern-matching rules loaded from YAML. Configurable actions: block, flag-and-forward, monitor. |
| **Hot-reloadable custom recognizers + exclusion lists** | Define org-specific patterns (employee IDs, fund codes) without restarting | Medium | RCU pattern: build new config in full, then atomic pointer swap. 60-second polling interval. |

## Anti-Features

Features to explicitly NOT build in v1.0 (core).

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Persistent storage of any kind** | Violates fail-secure + ephemeral principles | TTL-based eviction in Valkey. Logs are stdout only (Docker log driver handles persistence). |
| **Image/video PII detection** | Requires OCR pipeline (Tesseract + image processing). Presidio supports this but it adds 2-3x complexity for v1. | Focus on text-only. Image de-identification can be v2. |
| **User management / RBAC dashboard** | Requires a full web UI, session management, database | Use middleware API keys + JWT validation. Admin endpoints are API-only. Web UI is a commercial tier feature. |
| **Data residency / geo-routing** | Requires latency-based provider selection, failover logic | Client-side selection of provider via model alias. Geo-routing is a future differentiator. |
| **Anomaly detection on user behavior** | ML model training + serving pipeline | Focus on deterministic detection. ML-based anomaly detection leads to false positives in compliance contexts. |
| **Custom encryption of tokens in cache** | Adds complexity without additional security guarantee | Valkey runs on isolated Docker network, persistence disabled. Encryption at rest is irrelevant when there's no disk. |

## Feature Dependencies

```
Client SDK compatibility (OpenAI schema)
  └── Pydantic request/response models
       ├── Text extraction from messages
       │    └── PII detection (Presidio sidecar)
       │         └── Tokenization (reverse-order replacement)
       │              ├── Cache write (Valkey HSET)
       │              │    ├── Provider call (translated schema)
       │              │    │    ├── Non-streaming restoration
       │              │    │    │    └── Post-restore verification
       │              │    │    │         └── Audit log
       │              │    │    └── SSE streaming restoration
       │              │    │         ├── Tail_Buffer state machine
       │              │    │         ├── Pre-fetch cache at stream start
       │              │    │         └── Post-stream verification
       │              │    └── Cache cleanup (DEL)
       │              └── Fail-secure: all error paths → HTTP 5xx
       └── Health probes (composite: detection + cache)
            └── Pre-flight startup validation
```

## MVP Recommendation

Prioritize:
1. **Non-streaming anonymization round-trip** — Req 1. OpenAI → AnonReq → OpenAI → AnonReq → Client. PII detected, tokenized, forwarded, restored.
2. **Fail-secure architecture** — Req 2. Error boundaries, health probes, pre-flight checks. Ship NOTHING without this.
3. **Docker Compose deployment** — Req 12. Make `docker compose up` the single command that works end-to-end.
4. **SSE streaming** — Req 6. Most LLM interactions are streaming. Without it, the product is a toy.
5. **Multi-provider routing** — Req 7. At minimum: OpenAI + Ollama (the two simplest). Anthropic and Gemini can follow.

Defer:
- **Multi-locale detection (Req 8)**: The 8-locale recognizer bundles are labor-intensive to write and validate. Start with English + `en-*` locale. Add per-locale regex + checksum in Phase 6.
- **Compliance presets (Req 9)**: Presets are metadata overlays on entity type config. Implement after the core detection pipeline is stable.
- **Custom recognizer hot-reload (Req 11)**: Requires config file watching + atomic swap. Important for enterprise adoption but not for MVP.
- **Rate limiting / spend controls (Req 22)**: Enterprise feature. Add when you have > 1 tenant.
- **Prompt injection detection (Req 36)**: Completely separate feature track (AI firewall). Not part of core anonymization.

## Sources

- Req 1-21 (requirements.md): HIGH confidence — directly specifies features
- Req 22-56 (requirements_v2.md): HIGH confidence — enterprise feature specifications
- **Presidio built-in recognizers**: microsoft.github.io/presidio/supported_entities — HIGH confidence
- **OpenAI API schema**: platform.openai.com/docs/api-reference/chat — HIGH confidence
- **SSE streaming patterns**: fastapi.tiangolo.com/tutorial/server-sent-events — HIGH confidence
