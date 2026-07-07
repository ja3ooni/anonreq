# Domain Pitfalls — AnonReq v1.5 Enterprise Hardening

**Domain:** Self-hosted AI security & anonymization gateway
**Researched:** 2026-07-07
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Trust Center Routes Behind Auth Middleware

**What goes wrong:**
Trust Center is designed as a **public** compliance evidence portal. If routes are registered with `Depends(auth_context)` or placed before/within auth-protected router groups, every request returns 401 Unauthorized. Users cannot view compliance evidence, SLO status, or security posture without logging in — defeating the entire purpose of a public Trust Center.

**Why it happens:**
The existing codebase registers all routers with `Depends(auth_context)` (lines 674-688 in `main.py`). It's the default pattern. It's easy to add Trust Center routes in the same `include_router()` block and inherit auth protection automatically.

**Consequences:**
- Anyone clicking "View Trust Center" from the website gets an auth error
- Enterprise prospects evaluating AnonReq cannot see compliance evidence
- Vanta/Trust Center baseline requirement is not met
- Bug gets reported, requiring urgent fix and redeployment

**Prevention:**
Register Trust Center router as a separate `include_router()` call **after** all auth-protected routers, with **no** `dependencies=[Depends(auth_context)]`:

```python
# WRONG — inherits auth from being in the same block:
# app.include_router(trust_center_router, dependencies=[Depends(auth_context)])

# RIGHT — standalone registration, no auth:
if trust_center_settings.enabled:
    app.include_router(trust_center_router)
```

**Detection:**
Test that `GET /v1/trust/status` returns 200 (not 401 or 403) without any `Authorization` header.

**Phase to address:** Phase 2

---

### Pitfall 2: Custom Recognizers Registered Through Presidio Sidecar

**What goes wrong:**
Custom recognizers (API keys, AWS access keys, GitHub tokens) are sent to the Presidio Analyzer HTTP API for analysis. Presidio's `/analyze` endpoint only recognizes built-in NER entities (PERSON, EMAIL_ADDRESS, etc.) and filters by entity types — it does NOT accept custom regex patterns. The custom recognizers silently detect nothing, and developers wonder why secret detection isn't working.

**Why it happens:**
Presidio's documentation mentions "custom recognizers" but via the Python `presidio-analyzer` library API (in-process). The HTTP API does not support custom recognizer injection. Developers who know Presidio by name assume it handles custom patterns.

**Consequences:**
- API keys and tokens pass through undetected
- False sense of security ("we have Presidio-based detection")
- DLP requirements are not met
- Requires emergency rework when discovered

**Prevention:**
Route all pattern-based custom recognizers through the `RegexDetector` pipeline, NOT through `PresidioClient.analyze_text_nodes()`. The existing `DetectionStage.execute()` already merges regex patterns from entity configs and hot-reloaded custom rules. Add custom recognizer patterns to the `extra_patterns` dict:

```python
# WRONG — sending to Presidio sidecar that can't handle custom entities:
custom_entities = ["API_KEY", "AWS_ACCESS_KEY"]
ner_results = await presidio_client.analyze(text, entities=custom_entities)

# RIGHT — compile regex patterns and add to RegexDetector:
patterns = compile_custom_recognizer_patterns(config)
regex_results = regex_detector.detect(text, extra_patterns=patterns)
```

**Detection:**
Write tests with known API key patterns (e.g., `sk-proj-fakekey123`) and verify they produce detection results with the correct entity type and confidence score.

**Phase to address:** Phase 4.1

---

### Pitfall 3: License Check Implemented Inside Route Handlers

**What goes wrong:**
License validation logic is copied into each gated route handler or called as a helper method. New routes are added without the check. Some routes check, others don't. The license gate has holes.

**Why it happens:**
It's the most obvious approach — "call `LicenseValidator.has_feature()` at the top of the handler." Developers working on new features may not know about the license requirement or forget to add it.

**Consequences:**
- Unlicensed users access Appliance-tier features
- Revenue leakage for commercial licensing model
- Patchwork of checks that's hard to audit
- Each new route requires manual license integration

**Prevention:**
Use FastAPI's dependency injection system. Define a dependency factory once, apply at the **router** level (not per-handler):

```python
# WRONG — per-handler:
@router.get("/admin/evidence")
async def get_evidence(request: Request):
    if not await LicenseValidator.has_feature("compliance_monitoring"):
        raise HTTPException(402)
    ...

# RIGHT — router-level dependency:
router = APIRouter(
    prefix="/v1/admin",
    dependencies=[
        Depends(auth_context),
        Depends(require_license("compliance_monitoring")),
    ]
)
```

**Detection:**
Review each `include_router()` call in `main.py`. Any route that should be gated must have the license dependency at the router level, not in individual handler signatures.

**Phase to address:** Phase 4.3

---

### Pitfall 4: Phone-Home License Validation

**What goes wrong:**
License validator makes an HTTP request to an external licensing server to verify the license key. When the server is unreachable (network partition, DNS failure, maintenance, air-gapped deployment), all gated features become unavailable. In the worst case, the core anonymization pipeline could also be blocked if the license check is in the wrong place.

**Why it happens:**
SaaS licensing models are the default expectation. "How will you validate licenses without calling home?" is the first question asked. Phone-home feels natural.

**Consequences:**
- Air-gapped and sovereign deployments cannot use Appliance-tier features
- Network blips cause license validation failures and 402 errors
- Single point of failure for enterprise deployments
- Deployment complexity increases (needs egress to licensing server)

**Prevention:**
HMAC-SHA256 symmetric signing with a local key. The license payload (org, tier, features, expiry) is signed with a secret known to both the license generator and the AnonReq instance. Validation is pure computation — no network calls:

```python
# WRONG — phone-home:
async def validate():
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://license.anonreq.dev/verify", json={"key": key})
        return resp.json()

# RIGHT — local HMAC:
def validate(payload: str, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

**Detection:**
`strace` or network logging shows no outbound connections during license validation. Deploy in air-gapped network — license validation still works.

**Phase to address:** Phase 4.3

---

### Pitfall 5: PII Leaked in Trust Center Responses

**What goes wrong:**
Trust Center `/v1/trust/status` includes tenant-level SLO breakdowns, session counts, or other data that could identify individual usage patterns. The Trust Center becomes a PII liability.

**Why it happens:**
The SLO engine stores data per `tenant_id`. It's easy to iterate over all tenants and return per-tenant breakdowns — that's the simplest query path. The SLO data includes operational details that could be used to infer usage.

**Consequences:**
- PII/data protection violation
- Trust Center no longer safe for public access
- May need auth or data redaction, defeating purpose
- Regulatory compliance exposure

**Prevention:**
- Use `get_all_compliance("*")` with a wildcard tenant ID → returns aggregated metrics
- Do NOT iterate over tenants or return tenant-specific breakdowns
- Only return aggregate counters (total requests, overall uptime, global compliance rate)
- For Prometheus metrics, use `REGISTRY.get_sample_value()` for aggregate counters, not per-label breakdown
- Add a test that validates no tenant_id field appears in any Trust Center response

```python
# WRONG — exposes tenant data:
async def get_status():
    tenants = list_tenants()
    return {t: await slo_engine.get_all_compliance(t) for t in tenants}

# RIGHT — aggregate only:
async def get_status():
    compliance = await slo_engine.get_all_compliance("*")
    # Return summary stats, not per-tenant breakdown
    return {
        "overall_compliance": calculate_average(compliance),
        "window_count": len(compliance),
    }
```

**Detection:**
Search Trust Center response models for any field containing `tenant_id` or similar identifiers.

**Phase to address:** Phase 2

---

## Moderate Pitfalls

### Pitfall 6: Translation Files Drift From Source English

**What goes wrong:**
`docs/en/getting-started.md` is updated with new content. `docs/fr/getting-started.md` still shows old content. Prospects reading the French docs see outdated or incorrect information.

**Prevention:**
Maintain `docs/TRANSLATION_MANIFEST.md` with per-file per-language status (`draft` / `reviewed` / `published` / `—`). Add a CI step that checks translation status when source files change.

**Phase to address:** Phase 3

### Pitfall 7: Trust Center Not Rate Limited

**What goes wrong:**
Public endpoints with no rate limiting. An attacker hits `/v1/trust/status` at high volume, causing SLO engine reads from Valkey and Prometheus metric scraping to degrade request processing for the main gateway.

**Prevention:**
Add IP-based rate limiting (60 RPM per IP) using Valkey with sliding window. This is the same Valkey instance used for cache — no new infrastructure.

**Phase to address:** Phase 2

### Pitfall 8: License Check Slowing Down Request Processing

**What goes wrong:**
Every gated route call reads the license file from disk, parses the license key, and recomputes the HMAC. Adds 10-50ms to every gated request.

**Prevention:**
Validate and parse the license at startup (in the `lifespan` context manager). Store the parsed `LicensePayload` on `app.state`. Per-request check is a single `has_feature()` call checking an in-memory set — O(1), no I/O.

**Phase to address:** Phase 4.3

## Minor Pitfalls

### Pitfall 9: Config File Path Assumptions

**What:** `config/trust_center.yaml` hardcoded as `config/trust_center.yaml` but Docker deploys might use a different config mount path.
**Prevention:** Accept config path as an environment variable (`ANONREQ_TRUST_CENTER_CONFIG_PATH`) with a sensible default. Follow existing pattern from `POLICY_CONFIG_PATH`.

### Pitfall 10: Arabic Doc Rendering

**What:** Arabic docs in `docs/ar/` render with left-to-right text alignment, making them unreadable.
**Prevention:** Add RTL note to README. Use appropriate HTML/Bidi markers if needed. Verify with a browser before publishing.

### Pitfall 11: Duplicate License Validation on Admin Route

**What:** License admin endpoint (`GET /v1/admin/license`) is itself license-gated, creating a catch-22 where you can't check license status without a license.
**Prevention:** The license admin endpoint must NOT be behind `require_license()`. It should only require auth (`Depends(auth_context)`). This is the debugging/status endpoint.

## "Looks Done But Isn't" Checklist

- [ ] **Trust Center:** Tested WITHOUT auth header — returns 200, not 401
- [ ] **Trust Center:** Tested WITH config toggle disabled — returns 404
- [ ] **Trust Center:** Response JSON scanned — no `tenant_id` field present
- [ ] **Custom recognizers:** Known API key patterns (`sk-...`, `AKIA...`, `ghp_...`) detected correctly
- [ ] **Custom recognizers:** Pipeline detection tests pass with recognized keys in request text
- [ ] **License gate:** Core pipeline (`POST /v1/chat/completions`) works WITHOUT any license
- [ ] **License gate:** Gated features return 402 WITH missing/expired license
- [ ] **License gate:** Gated features work WITH valid license
- [ ] **License admin:** `GET /v1/admin/license` accessible with auth (not behind license gate)
- [ ] **Translation manifest:** All 6 languages have entries for all source files
- [ ] **Docker:** `ANONREQ_LICENSE_SECRET` and `ANONREQ_LICENSE_KEY` documented in `.env.example`

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Trust Center behind auth | Phase 2 | Test without auth header |
| Custom recognizers through Presidio | Phase 4.1 | Test known patterns produce detections |
| License check in handler body | Phase 4.3 | Code review — router-level dependencies |
| Phone-home license validation | Phase 4.3 | Verify no HTTP calls during license check |
| PII in Trust Center | Phase 2 | Test response contains no tenant_id |
| Translation drift | Phase 3 | CI step checks manifest vs source |
| Trust Center rate limiting | Phase 2 | Load test — >60 RPM returns 429 |
| License check overhead | Phase 4.3 | Benchmark — per-request check <1µs |
| Config path assumptions | Phase 2, 4 | Docker test with non-default config path |
| Arabic rendering | Phase 3 | Visual verification in browser |
| License admin gate catch-22 | Phase 4.3 | Test admin/license without license |

## Sources

- `src/anonreq/main.py` — Existing router registration pattern (auth on all routers)
- `src/anonreq/pipeline/detection.py` — Custom regex integration via AtomicConfigRegistry
- `src/anonreq/detection/presidio_client.py` — Presidio HTTP API (no custom recognizer support)
- `.planning/v1.5-SPEC.md` — License mechanism, config gates, rate limiting requirements
- Python stdlib docs: `hmac.compare_digest()` for constant-time comparison (timing attack prevention)
- Common pitfalls observed in: air-gapped deployments, license enforcement patterns, public API design

---
*Pitfalls research for: AnonReq v1.5 Enterprise Hardening*
*Researched: 2026-07-07*
