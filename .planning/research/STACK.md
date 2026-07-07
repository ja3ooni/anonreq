# Stack Research — AnonReq v1.5 Enterprise Hardening

**Domain:** Self-hosted AI security & anonymization gateway
**Researched:** 2026-07-07
**Confidence:** HIGH

## Recommended Stack

AnonReq v1.5 introduces **zero new pip dependencies**. All v1.5 features build on the existing stack plus Python stdlib modules.

### Core Technologies (Existing, Unchanged)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12 | Runtime | Already invested, 3.12-slim Docker base, all existing code targets this |
| FastAPI | 0.115+ | Web framework | Router registration pattern, dependency injection, app factory — all established |
| Pydantic Settings | 2.x | Configuration | Config toggle pattern, env prefix `ANONREQ_`, validation — established |
| pytest | 8.x | Testing | 768+ existing tests, pytest-asyncio, fakeredis, respx — established |
| structlog | 24.x | Logging | Existing logging infrastructure — Trust Center uses for audit |
| prometheus-client | 0.20+ | Metrics | Trust Center reads from REGISTRY for aggregate metrics |
| Redis/Valkey | 7.x | Cache | SLO engine reads from Valkey, rate limiting uses Valkey — established |

### v1.5 Additions (stdlib only)

| Technology | Module | Purpose | When to Use |
|------------|--------|---------|-------------|
| Python stdlib | `hmac` | HMAC-SHA256 symmetric signing | License key validation |
| Python stdlib | `hashlib` | SHA-256 hashing | Key derivation for license validation |
| Python stdlib | `re` | Regex compilation | Custom recognizer patterns (already used) |
| Python stdlib | `json` | License payload encoding | Already used throughout project |
| Python stdlib | `base64` | License key encoding | HMAC output encoding |

### Infrastructure (Existing, Unchanged)

| Technology | Purpose | Notes |
|------------|---------|-------|
| Docker Compose | Local deployment | Phase 1 modifies secure defaults |
| Valkey | SLO data, rate limiting | Trust Center service reads aggregated SLO from Valkey |
| Prometheus | Metrics scraping | Trust Center reads in-memory counter values |
| Presidio Analyzer | NER detection | Sidecar — custom recognizers do NOT go through Presidio |

### Development Tools (Phase 1 Additions)

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| ruff | 0.6+ | Linter + formatter | `target-version = "py312"`, `line-length = 100`, select E/F/I/N/W/UP/B/SIM/ARG/PT/RUF |
| mypy | 1.11+ | Static type checking | `strict = true` with per-module overrides for untyped deps |

## Installation

No new pip packages for v1.5. The `hmac`, `hashlib`, `re`, `json`, `base64` modules are Python stdlib.

```bash
# Existing dev dependencies for Phase 1:
uv sync --group dev

# ruff and mypy are dev dependencies added in Phase 1
```

For license validation, the only configuration is the `ANONREQ_LICENSE_SECRET` and `ANONREQ_LICENSE_KEY` environment variables added to docker-compose.yml.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| HMAC-SHA256 (stdlib) | JWT (PyJWT) | JWT if public-key cryptography needed (RSA/ECDSA). HMAC is simpler for symmetric signing, no phone-home. JWT adds decoder complexity without benefit here. |
| RegexDetector for custom recognizers | Presidio Custom Analyzer | If true NER-based custom entities needed. Requires modifying Presidio sidecar container — maintenance burden outweighs benefit for pattern-based detection. |
| Valkey rate limiting | In-process dict | If deployment has high request volume and Valkey latency is a concern. But Valkey is already a dependency, and in-process rate limits don't survive restarts. |
| Config gate (settings toggle) | Feature flags service | If dynamic toggling at runtime needed without restart. Not needed for v1.5 — Trust Center is a startup decision. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PyJWT / PyJWT libraries | Unnecessary dependency. License validation with HMAC-SHA256 is simpler, doesn't need all JWT features, and avoids dependency update burden. | `hmac` from stdlib |
| `presidio-analyzer` Python library in-process | Adds heavy dependency (spaCy model, ONNX), conflicts with sidecar architecture. Presidio runs as a separate container. | `RegexDetector` + compiled `re.Pattern` objects |
| `httpx` for license validation | License validation is local HMAC computation. HTTP calls add latency and failure modes. | Direct function call in-process |
| `redis` for license caching | License payload is small and validated at startup. No need for external caching. | In-process variable on `app.state` |

## Stack Patterns by Variant

**If license validation needs asymmetric cryptography:**
- Use `cryptography` library (already a dependency for TLS handling) with RSA key pair
- Because asymmetric allows license generation by a different entity than validation
- But HMAC-SHA256 is simpler for MVP

**If Trust Center needs high throughput (>1000 RPM):**
- Add dedicated metrics cache (snapshot SLO compliance every 60s into a Valkey key)
- Because each Trust Center `/status` request currently reads directly from Valkey SLO counters
- Not needed for v1.5 — Trust Center is low-traffic (public portal)

**If custom recognizers need dynamic hot-reload without restart:**
- Use existing `AtomicConfigRegistry` pattern in `admin/config.py`
- Because it already supports hot-reload for custom recognizer patterns via admin API
- Configured for v1.5 at startup from `config/recognizers.yaml`; hot-reload is an enhancement path

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Python 3.12 | `hmac` | Standard library, no version issues |
| Python 3.12 | `re` | Standard library, no version issues |
| Python 3.12 | `hashlib` | Standard library, no version issues |
| ruff 0.6+ | Python 3.12 | Full support for 3.12 syntax (type parameter syntax, etc.) |
| mypy 1.11+ | Python 3.12 | Full support for 3.12 patterns |

## Sources

- `src/anonreq/detection/recognizers/mnpi.py` — Custom recognizer module pattern (verified)
- `src/anonreq/pipeline/detection.py` — DetectionStage with AtomicConfigRegistry integration (verified)
- `src/anonreq/detection/provider.py` — Custom regex pattern compilation pattern (verified)
- `src/anonreq/admin/config.py` — AtomicConfigRegistry hot-reload pattern (verified)
- `.planning/v1.5-SPEC.md` — Phase 4 license mechanism specification (canonical)
- Python docs: `hmac` module, `hashlib` module — no compatibility concerns (verified)

---
*Stack research for: AnonReq v1.5 Enterprise Hardening*
*Researched: 2026-07-07*
