# Architecture Patterns — AnonReq v1.5 Enterprise Hardening

**Domain:** Self-hosted AI security & anonymization gateway
**Researched:** 2026-07-07
**Project Phase:** v1.5 — Enterprise Hardening & Trust Center, Documentation Parity, Guardrails

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application (create_app)                │
├─────────────────────────────────────────────────────────────────────────┤
│  Middleware Stack                                                       │
│  ┌──────────┐ ┌────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Metrics  │ │Classifictn│ │   Policy     │ │ ClassificationResp   │ │
│  │Middleware│ │Middleware  │ │ Middleware   │ │ Middleware           │ │
│  └──────────┘ └────────────┘ └──────────────┘ └──────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│  Router Registration Section (in create_app)                            │
│  ┌─────────────┐ ┌──────────┐ ┌────────────────┐ ┌──────────────────┐ │
│  │ Health       │ │ Chat +   │ │ Compliance     │ │ Governance /     │ │
│  │ (auth)       │ │ Models   │ │ (auth)         │ │ Oversight (auth) │ │
│  └─────────────┘ └──────────┘ └────────────────┘ └──────────────────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────────┐│
│  │ Admin        │ │ Discovery    │ │ TRUST CENTER  ◄── NEW + public   ││
│  │ (auth)       │ │ (auth)       │ │ (no auth, rate-limited, gated)   ││
│  └──────────────┘ └──────────────┘ └──────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────────┤
│  Root / Metadata / Metrics endpoints                                    │
└─────────────────────────────────────────────────────────────────────────┘

                        NEW: Config + License Gate Layer
            ┌──────────────────────────────────────────────────┐
            │  Config Gate: settings.TRUST_CENTER_ENABLED      │
            │  License Gate: Depends(check_license("trust"))   │
            │  Result: Trust Center routes return 404 if off   │
            └──────────────────────────────────────────────────┘

                        NEW: Trust Center Module
┌─────────────────────────────────────────────────────────────────────────┐
│  src/anonreq/trust_center/                                              │
│  ├── __init__.py                                                        │
│  ├── router.py         APIRouter(prefix="/v1/trust")                    │
│  ├── schemas.py        Pydantic response models                         │
│  ├── service.py        Reads from SLOEngine, PresetEngine, REGISTRY     │
│  ├── config.py         TrustCenterSettings (pydantic-settings)          │
│  └── deps.py           Gate dependencies (toggle + license)             │
└─────────────────────────────────────────────────────────────────────────┘

                        NEW: License Module
┌─────────────────────────────────────────────────────────────────────────┐
│  src/anonreq/license/                                                   │
│  ├── __init__.py                                                        │
│  ├── models.py         LicenseKey, FeatureGate, LicenseStatus           │
│  ├── validator.py      HMAC-SHA256 validation                           │
│  ├── config.py         LicenseSettings (pydantic-settings)              │
│  └── deps.py           check_license(feature) → FastAPI Dependency      │
└─────────────────────────────────────────────────────────────────────────┘

                        NEW: Custom Recognizers
┌─────────────────────────────────────────────────────────────────────────┐
│  src/anonreq/detection/recognizers/                                     │
│  ├── __init__.py                                                        │
│  ├── mnpi.py           Existing MNPI recognizer                         │
│  ├── api_key.py        APIKeyRecognizer (NEW)                           │
│  ├── aws_access_key.py AWSAccessKeyRecognizer (NEW)                     │
│  ├── github_token.py   GitHubTokenRecognizer (NEW)                      │
│  └── hostname.py       InternalHostnameRecognizer (NEW)                 │
│                                                                         │
│  config/recognizers.yaml  → Enable/disable + thresholds config          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `trust_center/router.py` | Public endpoints for compliance evidence | `trust_center/service.py` |
| `trust_center/service.py` | Aggregates SLO, compliance, metrics data | `app.state.slo_engine`, `app.state.preset_engine`, `prometheus_client.REGISTRY` |
| `trust_center/config.py` | Trust Center settings (enabled, display name, frameworks) | YAML config file `config/trust_center.yaml` |
| `trust_center/deps.py` | Gate dependencies: config toggle + license check | `trust_center/config.py`, `license/validator.py` |
| `license/validator.py` | HMAC-SHA256 symmetric key verification | `ANONREQ_LICENSE_SECRET` env var |
| `license/deps.py` | `Depends(check_license("feature"))` for gated routes | `license/validator.py` |
| Detection custom recognizers | Pattern-based secret detection (API keys, tokens) | `RegexDetector` (not Presidio sidecar) |
| Doc translation infrastructure | `docs/{lang}/` mirrors + manifest | `docs/TRANSLATION_MANIFEST.md` |

### Data Flow: Trust Center Request

```
Client
  │
  ▼
GET /v1/trust/status
  │
  ▼
Rate Limiter (60 RPM per IP — new dependency)
  │
  ▼
Config Gate (trust_center.enabled == false → 404)
  │
  ▼
License Gate (license missing/expired → 402)
  │
  ▼
trust_center/router.py
  │
  ▼
trust_center/service.py
  ├── app.state.slo_engine.get_all_compliance("*")
  │     └── Reads from Valkey (slo:* keys, metadata-only aggregates)
  ├── app.state.preset_engine.list_presets()
  │     └── Returns framework metadata from config/compliance/*.yaml
  └── prometheus_client.REGISTRY.get_sample_value(...)
        └── In-process metric counters (no external call)
  │
  ▼
Return: aggregated metadata → JSON response
  │
  ▼
Rate Limiter updates counter
```

### Data Flow: License Gate

```
Startup
  │
  ▼
LicenseValidator.load_key()
  └── Reads ANONREQ_LICENSE_SECRET from env
  └── No phone-home, validates at startup
  └── Caches in-process for lifetime of app (no Redis needed)
  │
  ▼
Per-request: Depends(check_license("feature_x"))
  │
  ▼
LicenseValidator.check_feature("feature_x")
  ├── HMAC-SHA256 verify license payload signature
  ├── Check expiry
  └── Check feature in allowed set
  │
  ▼
Return True → route handler executes
Return False → HTTP 402 Payment Required
```

---

## Component Architecture: Trust Center

### Package Layout

```
src/anonreq/trust_center/
├── __init__.py
│   └── from anonreq.trust_center.router import router as trust_center_router
│
├── config.py
│   class TrustCenterSettings(BaseSettings):
│       enabled: bool = False
│       model_config = SettingsConfigDict(env_prefix="ANONREQ_TRUST_")
│   trust_center_settings = TrustCenterSettings()
│   # Also loads YAML for display_name, contact_email, logo_url,
│   # supported_frameworks, feature_summary
│
├── schemas.py
│   class TrustStatusResponse(BaseModel):
│       status: str  # "operational" | "degraded" | "maintenance"
│       last_checked: datetime
│       slo_compliance: list[SLOComplianceSummary]
│
│   class ComplianceFrameworkSummary(BaseModel):
│       id: str
│       name: str
│       jurisdictions: list[str]
│       mandatory_entity_types: list[str]
│
├── service.py
│   class TrustCenterService:
│       def __init__(self, slo_engine, preset_engine, trust_config):
│       async def get_status_summary(self) -> TrustStatusResponse
│       async def get_compliance_frameworks(self) -> list[ComplianceFrameworkSummary]
│       async def get_metrics_summary(self) -> dict
│       async def get_security_posture(self) -> dict
│
├── deps.py
│   async def trust_center_enabled(request: Request) -> None:
│       """Gate: returns 404 if Trust Center disabled."""
│       if not trust_center_settings.enabled:
│           raise HTTPException(404)
│
│   async def trust_center_rate_limit(request: Request) -> None:
│       """Rate limit: 60 RPM per IP."""
│       # Uses Valkey with IP-based key, TTL 60s, count per minute
│
├── router.py
│   router = APIRouter(prefix="/v1/trust",
│       dependencies=[Depends(trust_center_enabled),
│                     Depends(trust_center_rate_limit)])
│
│   @router.get("/status", response_model=TrustStatusResponse)
│   @router.get("/compliance", response_model=list[ComplianceFrameworkSummary])
│   @router.get("/metrics")
│   @router.get("/security")
│
└── config/trust_center.yaml
    enabled: false
    display_name: "AnonReq Trust Center"
    contact_email: "security@example.com"
    supported_frameworks: [soc2, iso27001, gdpr, hipaa]
    feature_summary:
      anonymization: true
      dlp: false
      firewall: false
```

### Integration in `main.py`

Add near line 688 (after discovery_admin_router registration, before PAC router):

```python
# Phase 2: Trust Center — public compliance evidence portal
# Config-gated: enabled=false returns 404 on all endpoints
# No auth — public endpoints with IP-based rate limiting
if trust_center_settings.enabled:
    from anonreq.trust_center import trust_center_router
    from anonreq.trust_center.deps import trust_center_rate_limit
    # Public routes, no auth dependency
    app.include_router(trust_center_router)
    logger.info("Trust Center enabled", component="router")
```

**Important:** Do NOT add `Depends(auth_context)` to the Trust Center router. It's explicitly public. The rate limiter and config gate are the only protections.

---

## Component Architecture: License Module

### Package Layout

```
src/anonreq/license/
├── __init__.py
│
├── models.py
│   @dataclass
│   class FeatureGate:
│       name: str
│       tier: str  # "core" | "appliance"
│
│   @dataclass
│   class LicensePayload:
│       org: str
│       tier: str
│       features: list[str]
│       issued_at: datetime
│       expires_at: datetime
│
│   class LicenseStatus(BaseModel):
│       valid: bool
│       tier: str
│       features: list[str]
│       expires_at: datetime | None
│       expired: bool
│
├── config.py
│   class LicenseSettings(BaseSettings):
│       LICENSE_SECRET: str | None = None
│       LICENSE_KEY: str | None = None
│       model_config = SettingsConfigDict(env_prefix="ANONREQ_")
│
├── validator.py
│   class LicenseValidator:
│       @classmethod
│       async def initialize(cls, settings: LicenseSettings) -> None
│           # Decode and verify LICENSE_KEY using HMAC-SHA256
│           # with LICENSE_SECRET as key
│           # Cache parsed LicensePayload in-memory
│           pass
│
│       @classmethod
│       async def get_status(cls) -> LicenseStatus:
│           pass
│
│       @classmethod
│       def has_feature(cls, gate: str) -> bool:
│           pass
│
├── deps.py
│   def check_license(gate: str):
│       async def _check(request: Request) -> None:
│           status = await LicenseValidator.get_status()
│           if not status.valid or status.expired:
│               raise HTTPException(402, "License required")
│           if gate not in status.features:
│               raise HTTPException(402, f"Feature '{gate}' not licensed")
│       return _check
│
└── router.py  (admin endpoint)
    router = APIRouter(prefix="/v1/admin")
    @router.get("/license")
    async def get_license_status(...) -> LicenseStatus
```

### Feature Gate Mapping

| Gate | Tier | Blocks | Used On |
|------|------|--------|---------|
| `trust_center` | Core | Trust Center routes | Free tier |
| `ai_firewall` | Appliance | AI Firewall routes | Appliance |
| `soc_integration` | Appliance | SOC/SIEM sinks | Appliance |
| `advanced_detection` | Appliance | Custom recognizers (4.1) | Appliance |
| `compliance_monitoring` | Appliance | Evidence endpoint (4.2) | Appliance |

**Design decision:** Trust Center routes are gated to "Core" tier (free), meaning every installation gets them. The license gate is still enforced, but the `trust_center` feature is included in all tier licenses. This provides a uniform enforcement surface and future-proofs for enterprise-only Trust Center enhancements.

---

## Component Architecture: Custom Presidio Recognizers

### Current State

The detection pipeline already supports hot-reloaded custom **regex** patterns via `AtomicConfigRegistry` → `get_custom_recognizer_patterns()` in the `DetectionStage`. These compile into `re.Pattern` objects and run through `RegexDetector.detect()` — they do NOT go through the Presidio sidecar.

### For v1.5 Advanced Secret Detection

**Decision: Register custom recognizers through `RegexDetector`, NOT through Presidio sidecar.**

Rationale:
1. Presidio Analyzer HTTP API (`POST /analyze`) does not accept custom regex recognizers — it only filters by built-in NER entity types. True custom recognizers in Presidio require `presidio-analyzer` Python library and modifying the sidecar container.
2. The AnonReq container does not run `presidio-analyzer` in-process — it's a sidecar. Adding the library would require architectural changes.
3. The existing `DetectionStage` + `RegexDetector` pattern already supports compiled regex with confidence thresholds, entity type labels, and is fully integrated with arbitration, exclusion lists, and checksum validation.
4. MNPI recognizers already use this exact pattern (`MNPIRecognizer.analyze()` returns pipeline-compatible dicts).

### Integration Pattern

```
config/recognizers.yaml
  │
  ▼
load_custom_recognizers()  ← new function in anonreq/detection/recognizers/
  │
  ▼
List[Dict{entity_type, patterns, confidence, enabled}]
  │
  ▼
DetectionStage.__init__()
  └── Accepts list of custom recognizer dicts (alongside mnpi_recognizers)
  └── Each recognizer compiled to regex during execute()
  └── Matches added to regex_patterns dict before RegexDetector runs
```

### New Recognizer Modules

Each recognizer in `src/anonreq/detection/recognizers/`:

| Module | Class | Pattern | Confidence | Config |
|--------|-------|---------|------------|--------|
| `api_key.py` | `APIKeyRecognizer` | `sk-...`, `pk-...`, `sk-proj-...`, `sk-ant-...` | 0.85 | `api_key.enabled` |
| `aws_access_key.py` | `AWSAccessKeyRecognizer` | `AKIA[0-9A-Z]{16}`, `ASIA...` | 0.90 | `aws_access_key.enabled` |
| `github_token.py` | `GitHubTokenRecognizer` | `ghp_[a-zA-Z0-9]{36}`, `ghs_...` | 0.90 | `github_token.enabled` |
| `hostname.py` | `InternalHostnameRecognizer` | FQDNs matching internal domains | 0.80 | `hostname.internal_domains` |

Each recognizer follows the `MNPIRecognizer` pattern:
```python
class APIKeyRecognizer:
    def __init__(self, config: dict):
        self._patterns = [re.compile(p) for p in config["patterns"]]
        self._confidence = config.get("confidence", 0.85)
    
    def analyze(self, text: str, node_index: int = 0) -> list[dict]:
        """Return pipeline-compatible detection dicts."""
```

### License Gate for Custom Recognizers

Registration of advanced custom recognizers checks the `advanced_detection` feature gate:

```python
def load_advanced_custom_recognizers(config_path: str) -> list:
    if not LicenseValidator.has_feature("advanced_detection"):
        return []  # Graceful degradation — no custom recognizers without license
    # ... load from config/recognizers.yaml ...
```

---

## Component Architecture: Documentation Translation

### Directory Structure

```
docs/
├── TRANSLATION_MANIFEST.md          ← NEW: tracks translation state
├── architecture.mmd
├── architecture/
│   └── multimodal.md
├── compliance/
├── operations/
│   ├── policy-runbook.md
│   └── slo-runbook.md
├── security/
│   └── incident-response.md
├── en/                              ← Source language (canonical)
│   ├── getting-started.md
│   ├── installation.md
│   ├── deployment.md
│   ├── api-reference.md
│   ├── compliance.md
│   └── faq.md
├── de/                              ← Already exists (Phase 2)
│   └── (same 6 files)
├── fr/                              ← NEW
│   └── (same 6 files)
├── es/                              ← NEW
├── pt/                              ← NEW
├── it/                              ← NEW
├── ar/                              ← NEW (RTL)
├── nl/                              ← NEW
└── glossary.md                      ← NEW: shared technical term translations
```

### TRANSLATION_MANIFEST.md Format

```markdown
# Translation Manifest

| Source File | fr | es | pt | it | ar | nl |
|---|---|---|---|---|---|---|
| docs/en/getting-started.md | reviewed | draft | draft | draft | draft | draft |
| docs/en/installation.md | draft | draft | draft | — | — | draft |
| docs/en/deployment.md | — | — | — | — | — | — |
| docs/en/api-reference.md | draft | draft | — | — | — | — |
| docs/en/compliance.md | — | — | — | — | — | — |
| docs/en/faq.md | — | — | — | — | — | — |

Status: draft / reviewed / published / —
```

### Processing

Translation is content work, not code work. The architecture consideration is:
1. Each language is a complete mirror of `docs/en/` — same filenames, same structure
2. `docs/glossary.md` defines invariant technical terms per language (e.g., "fail-secure", "tokenization", "Presidio")
3. Arabic (`ar/`) needs a note in README about RTL rendering
4. Architecture diagrams (`architecture.mmd`) rendered as PNG per language in `docs/{lang}/architecture/`

---

## Patterns to Follow

### Pattern 1: Config-Gated Router Registration

**What:** Register a router only when its configuration toggle is enabled.

**When:** Any new feature that should be disableable without code changes.

**Why:** Follows existing convention (see `requires_detection(active_mode)` in lifespan), provides operational control.

**Implementation:**
```python
# In create_app(), after other routers:
if trust_center_settings.enabled:
    from anonreq.trust_center import trust_center_router
    app.include_router(trust_center_router)
    logger.info("Trust Center router registered", component="router")
else:
    logger.info("Trust Center disabled — routes not registered", component="router")
```

**Why not a middleware-based gate?** If routes aren't registered at all, FastAPI returns 404 more efficiently. A middleware falls through to a 404 anyway, but costs middleware overhead on every request.

### Pattern 2: License Gate as FastAPI Dependency

**What:** A factory function returning a `Depends`-compatible callable that checks license for a specific feature.

**When:** Any route that should be license-gated.

**Why:** Composable with existing dependency chain. Can be combined with `auth_context` for protected routes, or standalone for public routes.

**Implementation:**
```python
# In license/deps.py:
from fastapi import HTTPException, Request
from anonreq.license.validator import LicenseValidator

def require_license(feature: str):
    """FastAPI dependency factory for license-gated features."""
    async def _check(request: Request) -> None:
        status = await LicenseValidator.get_status()
        if not status.valid:
            raise HTTPException(
                status_code=402,
                detail={"error": "license_required", "message": "Valid license required"}
            )
        if feature not in status.features:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "feature_not_licensed",
                    "message": f"Feature '{feature}' not included in current license tier"
                }
            )
    return _check

# Usage on Trust Center routes (combined with config gate + rate limit):
router = APIRouter(
    prefix="/v1/trust",
    dependencies=[
        Depends(trust_center_enabled),
        Depends(trust_center_rate_limit),
        Depends(require_license("trust_center")),
    ]
)
```

### Pattern 3: Custom Recognizer via RegexDetector Extension

**What:** Adding secret detection patterns to the existing regex-based detection engine rather than Presidio sidecar.

**When:** Pattern-based detection (API keys, tokens, internal hostnames) where regex is sufficient.

**Why:** Presidio sidecar HTTP API does not support custom regex recognizers. Running patterns through the existing `RegexDetector` avoids architectural changes to the Presidio container.

**Implementation:**
```python
# In DetectionStage.execute(), after hot-reload custom patterns:
if self._custom_recognizers:
    for recognizer in self._custom_recognizers:
        if recognizer.enabled:
            patterns = recognizer.compile_patterns()
            extra_patterns.update(patterns)

# Then pass to RegexDetector.detect():
regex_results = self._regex_detector.detect(
    node_value,
    extra_patterns=extra_patterns,
)
```

### Pattern 4: Translation Mirror with Manifest

**What:** Mirror directory structure per language with a manifest file tracking review state.

**When:** Multi-language documentation projects.

**Why:** Prevents drift between languages. Clear ownership for review.

**Implementation:**
```
docs/{lang}/           → exact mirror of docs/en/
docs/TRANSLATION.md    → status table
docs/glossary.md       → shared technical terms per language
```

### Pattern 5: Structured Service Module for Aggregate Endpoints

**What:** A service class that abstracts reading from multiple sources (SLO engine, compliance registry, metrics) behind a clean interface.

**When:** Any endpoint that aggregates data from multiple subsystems.

**Why:** Keeps route handlers thin, testable in isolation, and allows mocking.

**Implementation:**
```python
# In trust_center/service.py:
class TrustCenterService:
    def __init__(
        self,
        slo_engine: SLOEngine,
        preset_engine: PresetEngine,
        trust_config: dict,
    ):
        self._slo = slo_engine
        self._presets = preset_engine
        self._config = trust_config

    async def get_status_summary(self) -> dict:
        compliance = await self._slo.get_all_compliance("*")
        # Aggregate across tenants (aggregate metrics only, no raw data)
        return {
            "status": self._aggregate_status(compliance),
            "last_checked": datetime.now(timezone.utc),
            "slo_compliance": [
                {
                    "slo": name,
                    "windows": [
                        {"window": c.window_type, "current": c.current,
                         "target": c.target, "compliant": c.compliant}
                        for c in entries
                    ]
                }
                for name, entries in compliance.items()
            ],
        }

    def get_compliance_frameworks(self) -> list[dict]:
        presets = self._presets.list_presets()
        # Filter to frameworks listed in trust_center config
        supported = set(self._config.get("supported_frameworks", []))
        return [
            {
                "id": pid,
                "name": p.name,
                "jurisdictions": p.jurisdictions,
                "mandatory_entity_types": p.mandatory_entity_types,
            }
            for pid, p in presets.items()
            if pid in supported
        ]
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Registering Trust Center Behind the Auth Middleware

**What:** Adding `Depends(auth_context)` to Trust Center routes or mounting the router in the same group as auth-protected routers.

**Why bad:** Trust Center is explicitly a **public** portal. Auth would defeat the purpose — customers need to see compliance evidence without logging in.

**Instead:** Register Trust Center router **after** all auth-protected routers in `main.py`, with **no** auth dependency. Rate limiting is acceptable but auth is not.

### Anti-Pattern 2: Trust Center Reading Raw Tenant or Request Data

**What:** Trust Center service queries tenant-level SLO data or request payloads.

**Why bad:** Violates the "no PII in Trust Center" constraint. Aggregated metadata only.

**Instead:** SLO engine's `get_all_compliance("*")` with tenant ID wildcard returns aggregated metrics across all tenants. Use `prometheus_client` `REGISTRY` for request-level aggregates (counters, histograms) — not individual requests.

### Anti-Pattern 3: Custom Presidio Recognizers via Sidecar Modification

**What:** Fork the Presidio Analyzer Docker image to add custom Python recognizers.

**Why bad:** Introduces maintenance burden whenever Presidio updates. Requires rebuilding the sidecar image. The detection pipeline has a pattern-based alternative that's simpler and already works.

**Instead:** Add custom recognizers through the existing `RegexDetector` → `DetectionStage` pipeline. If true NER-based custom detection is needed later, it should be in-process (not sidecar HTTP).

### Anti-Pattern 4: License Check as Method on Every Route Handler

**What:** Calling `LicenseValidator` inside each route handler explicitly.

**Why bad:** Duplication. Easy to forget on new routes. Violates DRY.

**Instead:** Use FastAPI's dependency injection. Define `require_license("feature")` as a dependency factory, add it to the router-level `dependencies` list. Every route on that router inherits the gate.

### Anti-Pattern 5: Phone-Home License Validation

**What:** License validator pings an external API to validate the key.

**Why bad:** Requires internet access. Breaks air-gapped deployments. Adds latency. Creates a single point of failure.

**Instead:** HMAC-SHA256 symmetric signing with local key. Zero external calls. Verified at startup. In-memory cached for the app lifetime.

---

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---------|--------------|--------------|-------------|
| **Trust Center rate limiting** | In-process IP rate map (dict + timestamps) | Valkey-backed rate counter per IP | Valkey-backed with sharding, 120 RPM per IP |
| **SLO engine read load** | Direct Valkey reads per request | Snapshot SLO compliance to a cache key every 60s | Dedicated read replica of Valkey for Trust Center queries |
| **License validation** | In-memory cache, startup-only decode | In-memory cache, startup-only decode | Same — no scaling concern (O(1) check) |
| **Custom recognizer patterns** | Loaded per request from config | Loaded per request, LRU cache of compiled patterns | Pre-compiled at startup, versioned |
| **Prometheus metrics scrape** | Direct `REGISTRY.get_sample_value()` | Aggregated counters rolled up per hour | Dedicated metrics pipeline (push to thanos/cortex) |

---

## Integration Points Summary

| New Component | Integrates With | How |
|---------------|----------------|-----|
| Trust Center router | `main.py` `create_app()` | Registered conditionally behind `trust_center_settings.enabled` |
| Trust Center service | `app.state.slo_engine` | Calls `get_all_compliance("*")` for aggregated SLO data |
| Trust Center service | `app.state.preset_engine` | Calls `list_presets()` for compliance framework metadata |
| Trust Center service | `prometheus_client.REGISTRY` | Reads aggregate metric values directly |
| License validator | `os.environ` / `pydantic-settings` | Reads `ANONREQ_LICENSE_SECRET` + `ANONREQ_LICENSE_KEY` |
| License gate | FastAPI dependency system | `Depends(require_license("feature"))` on routers |
| Custom recognizers | `DetectionStage` in pipeline | Loaded as extra `re.Pattern` dicts into `RegexDetector` |
| Custom recognizers | License gate | `advanced_detection` feature gate blocks loading without license |
| Translation manifest | docs/ directory | Manually maintained per-language doc structure |

---

## New vs Modified Files

### New Files

```
src/anonreq/trust_center/__init__.py
src/anonreq/trust_center/config.py
src/anonreq/trust_center/schemas.py
src/anonreq/trust_center/service.py
src/anonreq/trust_center/deps.py
src/anonreq/trust_center/router.py
src/anonreq/license/__init__.py
src/anonreq/license/models.py
src/anonreq/license/config.py
src/anonreq/license/validator.py
src/anonreq/license/deps.py
src/anonreq/license/router.py
src/anonreq/detection/recognizers/api_key.py
src/anonreq/detection/recognizers/aws_access_key.py
src/anonreq/detection/recognizers/github_token.py
src/anonreq/detection/recognizers/hostname.py
config/trust_center.yaml
config/recognizers.yaml
docs/fr/ (6 files + manifest entries)
docs/es/ (6 files + manifest entries)
docs/pt/ (6 files + manifest entries)
docs/it/ (6 files + manifest entries)
docs/ar/ (6 files + manifest entries)
docs/nl/ (6 files + manifest entries)
docs/glossary.md
docs/TRANSLATION_MANIFEST.md
```

### Modified Files

| File | Change |
|------|--------|
| `src/anonreq/main.py` | Add Trust Center router registration, Trust Center service init in lifespan, custom recognizer loader call |
| `src/anonreq/config/__init__.py` | Add `TRUST_CENTER_ENABLED` setting, `LICENSE_SECRET`, `LICENSE_KEY` settings |
| `src/anonreq/detection/recognizers/__init__.py` | Export new recognizers |
| `src/anonreq/pipeline/detection.py` | Accept `custom_recognizers` parameter, integrate into regex_patterns |
| `src/anonreq/detection/pipeline.py` | Add `load_advanced_custom_recognizers()` function |
| `src/anonreq/pipeline/manager.py` | Pass custom recognizers through to DetectionStage |
| `src/anonreq/monitoring/metrics.py` | Optionally add Trust Center-specific metric counters |
| `src/anonreq/admin/router.py` | Optionally add license admin route to admin router |
| `docker-compose.yml` | Add `ANONREQ_LICENSE_SECRET` and `ANONREQ_LICENSE_KEY` env vars to gateway service |
| `docs/TRANSLATION_MANIFEST.md` | Initially created, then updated per language |

---

## Build Order

Phase order per the v1.5 spec:

```
Phase 1 (Hygiene) → Phase 2 (Trust Center) → Phase 4 (Guardrails)
                ↘ Phase 3 (Docs) — independent fork
```

**Phase 1 first** because CI/code quality fixes are a prerequisite for confident changes in all subsequent phases. Phase 2 and 3 are independent. Phase 4 depends on Phase 2 (licensing gates the Trust Center).

### Dependency Map

```
Phase 1 (Hygiene)
  ├── No dependencies
  └── Prerequisite for: Phase 2, 4

Phase 2 (Trust Center)
  ├── Depends on: Phase 1 (CI)
  ├── No license module dependency (trust_center is Core tier)
  └── Implementation order:
      1. trust_center/config.py + YAML
      2. trust_center/schemas.py
      3. trust_center/service.py
      4. trust_center/deps.py (config gate + rate limit)
      5. trust_center/router.py
      6. Integration in main.py

Phase 3 (Docs)
  ├── Depends on: nothing (pure content)
  └── Implementation order:
      1. Create TRANSLATION_MANIFEST.md
      2. Create glossary.md
      3. Mirror docs/en/ to fr/, es/, pt/, it/, ar/, nl/
      4. Translate one language at a time
      5. Validate links per language

Phase 4 (Guardrails)
  ├── Depends on: Phase 1, Phase 2
  └── Implementation order:
      1. license/models.py + config.py
      2. license/validator.py
      3. license/deps.py + router.py
      4. Integration in main.py
      5. config/recognizers.yaml
      6. Detection recognizer modules
      7. DetectionStage integration
      8. License gate on recognizer loading
      9. Evidence endpoint (4.2)
```

---

## Sources

- `src/anonreq/main.py` — App factory pattern, router registration, middleware stack, lifespan context manager
- `src/anonreq/config/__init__.py` — Pydantic Settings pattern, env prefix `ANONREQ_`
- `src/anonreq/dependencies.py` — `auth_context` dependency pattern, `Depends` composition
- `src/anonreq/pipeline/detection.py` — DetectionStage with AtomicConfigRegistry integration, MNPI recognizer pattern
- `src/anonreq/detection/pipeline.py` — `load_mnpi_recognizers()` pattern for custom recognizer loading
- `src/anonreq/locale/merger.py` — RecognizerMerger pattern for locale-based entity config merging
- `src/anonreq/compliance/engine.py` — PresetEngine, YAML-based compliance preset loading
- `src/anonreq/services/slo_engine.py` — SLOEngine interface, `compute_compliance()`, `get_all_compliance()`
- `src/anonreq/admin/router.py` — Router aggregation pattern (sub-routers on admin_router)
- `src/anonreq/admin/config.py` — AtomicConfigRegistry pattern for hot-reloadable config
- `src/anonreq/middleware/rbac.py` — RBAC require_role dependency factory pattern
- `config/compliance/gdpr.yaml` — Compliance preset YAML format
- `config/slo.yaml` — SLO target configuration format
- `.planning/v1.5-SPEC.md` — Milestone specification for Trust Center, docs, guardrails
- `.planning/PROJECT.md` — Project context, current milestone, constraints
