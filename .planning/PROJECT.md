# AnonReq

## What This Is

AnonReq is a self-hosted data anonymization gateway that intercepts outbound LLM API calls from internal applications, detects and replaces sensitive data (PII, PHI, financial identifiers) with context-preserving placeholder tokens, forwards the sanitized request to any supported external LLM provider, and restores original values in the response — all within the customer's secure perimeter. No raw sensitive data ever crosses the network boundary.

The core product is Apache 2.0 licensed, designed for enterprise adoption across Europe, Asia-Pacific, Africa, South America, and Canada with multilingual PII detection (8 locales), per-jurisdiction compliance presets, and a fail-secure architecture.

## Core Value

Raw PII never crosses the network boundary. Every other concern is secondary to that guarantee.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Core Anonymization Pipeline — OpenAI-compatible POST /v1/chat/completions, detection on all message roles, tokenization, restoration, cache cleanup (Req 1)
- [ ] Fail-Secure Architecture — any error returns HTTP 5xx, never forward unsanitized data, health endpoint, startup pre-flight (Req 2)
- [ ] Hybrid PII Detection Engine — regex tier (email, phone, credit card, IBAN, IP, URL, DOB, national IDs, SWIFT, crypto) + NER tier (name, org, address, city, job title), conflict resolution via regex priority (Req 3)
- [ ] Context-Preserving Tokenization — `[TYPE_N]` format, deduplication, reverse-offset replacement, cryptographically random seed per session (Req 4)
- [ ] Ephemeral Mapping Store — Valkey/Redis with persistence disabled, TTL 60-3600s, DEL post-response (Req 5)
- [ ] SSE Streaming Support — token restoration in stream, Tail_Buffer for split tokens, case-insensitive + bracket-optional matching (Req 6)
- [ ] Multi-Provider LLM Support — OpenAI, Anthropic, Gemini, Ollama; Provider_Adapter translation layer, GET /v1/models (Req 7)
- [ ] Multilingual PII Detection — 8 locales via X-AnonReq-Locale header, locale-specific recognizer bundles, checksum validation (Req 8)
- [ ] Per-Jurisdiction Compliance Presets — GDPR, LGPD, PDPA, POPIA, Privacy Act, PIPEDA; GET /v1/compliance/presets (Req 9)
- [ ] Metadata-Only Audit Logging — structured JSON to stdout, field allowlist, no raw values, fail-secure log entries (Req 10)
- [ ] Custom Detection Rules and Exclusion Lists — YAML-based custom patterns, hot-reload, GET /v1/config/rules (Req 11)
- [ ] Docker Compose Deployment — multi-stage Dockerfile (Python 3.12-slim), presidio + valkey services, .env.example (Req 12)
- [ ] Response-Side Token Verification — post-restoration `\[[A-Z]+_\d+\]` scan, Prometheus /metrics (Req 13)
- [ ] Commercial Open-Source Positioning — Apache 2.0, NOTICE file, SECURITY.md, README with roadmap (Req 14)
- [ ] Developer Experience and Multilingual Documentation — docs/ directory with quickstarts in 5 languages, SDK examples, CHANGELOG.md (Req 15)
- [ ] Property-Based Test Suite — Hypothesis-based round-trip correctness, token uniqueness, deduplication, fail-secure, locale checksum, no-PII-in-logs, streaming round-trip, cross-request randomization (Req 16)

### Out of Scope

- Enterprise Authentication & Auth (Req 17) — OAuth/JWT/mTLS, RBAC, OIDC/SAML — deferred post-Stage 3
- Secrets Management & Network Security (Req 18) — HashiCorp Vault, AWS/Azure/GCP secret stores, mTLS between internal components — deferred post-Stage 3
- Multi-Tenant Isolation (Req 19) — tenant namespacing, per-tenant config, tenant provisioning API — deferred post-Stage 3
- High Availability / Scalability / DR (Req 20) — Valkey Sentinel/Cluster, Kubernetes Helm chart, HA deployment — deferred post-Stage 3
- Data Sovereignty & Compliance Assurance (Req 21) — geographic routing, detection quality benchmarks, SLO dashboards — deferred post-Stage 3

## Context

- **Greenfield**: No code exists yet. All source code, Docker setup, CI/CD, and tests are yet to be built.
- **Requirements defined**: 21 core requirements (Req 1–16 = v1, Req 17–21 = enterprise v2), plus 35 enterprise/appliance requirements (Req 22–56).
- **Current state**: Requirements are documented in `req/requirements.md` (core), `req/requirements_v2.md` (enterprise), and `.planning/REQUIREMENTS.md` (consolidated traceability). A `.docx` version exists as the authoritative source.
- **Roadmap**: Consolidated into 3 stages, 21 phases — see `.planning/ROADMAP.md`.
- **Deployment target**: Docker Compose with `anonreq` + `presidio-analyzer` + `valkey` services on an internal Docker network.

## Constraints

- **Fail-secure**: Any error → HTTP 5xx, never forward unsanitized data. Non-negotiable.
- **No PII in logs**: Metadata-only audit; field allowlist enforced. The audit log itself must not become a PII liability.
- **Ephemeral cache only**: Redis with `save ""`, no AOF, no RDB. Mapping exists only in RAM during request lifecycle.
- **Token format**: `[TYPE_N]` — case-insensitive + bracket-optional matching during restoration.
- **OpenAI-compatible input schema**: Single wire protocol; adapters translate for other providers.
- **Session-scoped mapping**: `anonreq:{Session_ID}` key, TTL 60–3600s, deleted post-response.
- **Multi-locale**: `X-AnonReq-Locale` header, 8 locales, locale-specific recognizer bundles.
- **Tech stack**: Python 3.12, FastAPI, Presidio Analyzer, Valkey/Redis, Prometheus client, Docker Compose.
- **License**: Apache 2.0.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python 3.12 + FastAPI | Best ecosystem fit for Presidio integration, async support for SSE streaming, strong typing | — Pending |
| Single wire protocol (OpenAI schema) | Minimum friction for existing OpenAI SDK users; adapters for others | — Pending |
| Microsoft Presidio Analyzer | Mature NER pipeline with regex support, locale extensibility, active community | — Pending |
| Valkey over Redis | Open-source fork with identical API, no licensing concerns | — Pending |
| Property-based tests (Hypothesis) | Required by Req 16 for generative proof of correctness | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-19 — consolidated roadmaps into 3 stages, 21 phases*
