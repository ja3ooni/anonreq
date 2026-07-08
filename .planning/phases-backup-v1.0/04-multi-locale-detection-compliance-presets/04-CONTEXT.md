# Phase 4: Multi-Locale Detection + Compliance Presets - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

PII detection in 8 locales via `X-AnonReq-Locale` header with locale-specific regex recognizer bundles and checksum validation for national IDs. Per-jurisdiction compliance presets enforce mandated entity detection at startup.

Locale bundles are drop-in YAML files. Compliance presets are overlays (not full config snapshots). Merge order: Base Config → Compliance Preset → Customer Overrides.

No new pipeline stages that touch streaming or non-streaming data — locale negotiation and compliance preset merging are pre-detection concerns.
</domain>

<decisions>
## Implementation Decisions

### Architectural Guardrails
- **AG-13:** Locale Determinism — same input + same locale header = same detection output. Locale resolution is deterministic and order-independent (for multi-locale merges).
- **AG-14:** Presets Cannot Weaken Security — a compliance preset never disables a broader recognition than the base config would provide. Presets only add/strengthen, never remove/weaken default detection.

### Locale Bundle Structure
- **D-110:** One YAML file per locale in `config/locales/{locale_code}.yaml`. Adding a locale = dropping a file in the directory.
- **D-111:** Each bundle defines: locale code, entity types with patterns, recognizer tier (regex/NER), confidence threshold overrides, national ID checksum config (if applicable), and human-readable metadata (name, version, maintainer).
- **D-112:** Language codes use standard format (de-DE, fr-FR, nl-NL, es, it-IT, ar, pt-BR, en). Generic codes (es, ar) preferred for language-wide patterns; country-specific (de-DE) for jurisdictional ID formats.
- **D-113:** No hard cap at 8 locales. Eight is the MVP content count. `LocaleRegistry` auto-discovers bundles at startup.

### Locale Negotiation Strategy
- **D-114:** `X-AnonReq-Locale` header parsed as comma-separated locale codes. Whitespace trimmed. Priority: first listed = primary locale, rest = secondary.
- **D-115:** Recognizer union *before* detection — not union of results. All locale-specific + universal recognizers are merged into a single recognizer set before scanning text.
- **D-116:** Missing locale (code not found in registry) → fall back to `en` universal recognizers + logged warning.
- **D-117:** Malformed/unknown locale → HTTP 400 with list of supported locales. Single unknown in a multi-locale list → drop that entry, continue with rest, log warning.
- **D-118:** No locale header → universal recognizers (en defaults) only + log entry (LOCL-04).
- **D-119:** `locale` field in audit log. Multi-locale requests: comma-separated list. Fallbacks: lists all locales used.

### National ID Checksum Validation
- **D-120:** Generic `ChecksumValidator` framework — separate validator per country ID format (Steuer-ID DE, BSN NL, NIR FR, CPF/CNPJ BR, Codice Fiscale IT). Each implements a `validate(digits: str) → bool` interface.
- **D-121:** On checksum failure: detection is **dropped** — not downgraded, not flagged. If the ID format fails checksum validation, it is not a valid detection.
- **D-122:** Checksum validators registered alongside locale bundles in the same YAML config. See LOCL-07.
- **D-123:** Property-based test (TEST-05): invalid checksum IDs never flagged as valid detections.

### Compliance Preset Architecture
- **D-124:** Presets are overlays — entity-type lists with confidence thresholds and required recognizer tiers. Not full config snapshots. Base config provides the full recognizer registry; presets add mandatory entity types, override thresholds, and enforce minimum recognizer tiers.
- **D-125:** Merge order: Base Config → Compliance Preset → Customer Overrides. Each layer can add entity types or raise thresholds, never remove. Precedence: customer overrides > preset > base.
- **D-126:** Conflict resolution between multiple active presets: union of entity types, highest confidence threshold per entity type. Presets never weaken detection (AG-14).
- **D-127:** Preset enforces minimum recognizer tiers (e.g., GDPR requires regex + NER for PERSON detection, not just regex).
- **D-128:** `compliance_preset` field in audit log (COMP-03). Multi-preset: comma-separated.

### Preset Startup Validation
- **D-129:** Hard fail at gateway startup — gateway won't serve traffic if a compliance preset is configured but its mandatory entity types are disabled in the effective config.
- **D-130:** Validation rules:
  - Every entity type mandated by active preset(s) must have at least one enabled recognizer
  - Confidence thresholds must meet or exceed preset minimums
  - Mandatory recognizer tiers must be present (regex, NER, or both)
- **D-131:** Startup validation runs after merge (Base → Preset → Overrides). Error message lists all violations with preset name, entity type, and resolution.
- **D-132:** Preset config is fixed at startup — no runtime reload in MVP.

### Extensibility Model
- **D-133:** `LocaleRegistry` auto-discovers YAML bundles from `config/locales/` at startup. No code changes needed to add a locale.
- **D-134:** Locale bundle schema is extensible: new entity types with patterns, checksum config, threshold overrides. No code changes.
- **D-135:** Adding a locale in v1: drop `{locale_code}.yaml` → restart → gateway picks it up. No registration, no config changes elsewhere.

### Audit Fields
- **D-136:** `locale` field: the effective locale(s) used (comma-separated for multi). Hidden: the raw header.
- **D-137:** `compliance_preset` field: active preset(s). Hidden: preset internals (thresholds, entity lists) — only the name is logged.

### From Prior Phases (carried forward)
- D-01 to D-53 from Phases 1 and 2 apply fully — error model, logging, config, tenant isolation, Valkey HASH, pipeline orchestration, ForwardingGuard, detection/classification strategies
- D-54 to D-109 from Phase 3 apply fully — StreamEvent model, TailBuffer FSM, ProviderAdapter contract, model alias routing, cleanup session, architectural guardrails AG-01 to AG-12
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — LOCL-01 to LOCL-07, COMP-01 to COMP-05
- `.planning/ROADMAP.md` § Phase 4 — Success criteria, 3 plans (04-01 to 04-03)

### Prior Phase Decisions
- `.planning/phases/01-foundation-fail-secure-auth/01-CONTEXT.md` — D-01 to D-21
- `.planning/phases/02-core-pipeline-classification-non-streaming/02-CONTEXT.md` — D-22 to D-53
- `.planning/phases/03-sse-streaming-multi-provider/03-CONTEXT.md` — D-54 to D-109, AG-01 to AG-12

### Project Decisions
- `.planning/PROJECT.md` — Python 3.12 + FastAPI, Presidio sidecar, Valkey, Docker Compose, Apache 2.0, fail-secure mandate
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 1: Config (Pydantic Settings + YAML), structured logging, error handling, auth, Docker scaffold
- Phase 2: Pipeline orchestration (ProcessingContext), TextExtractor, DetectionProvider interface, recognizer registry, Valkey cache manager
- Phase 3: ProviderAdapter interface, model alias routing, StreamEvent model

### Established Patterns
- YAML-based config for business/policy logic (D-07, D-22, D-36) — locale bundles and compliance presets follow the same pattern
- Phase 2 DetectionProvider interface — locale-aware recognizer loading extends this
- ProcessingContext-based stage pipeline with audit_metadata population

### Integration Points
- Detection stage in pipeline: locale bundle selection happens before recognizer set construction
- Audit logging: `locale` and `compliance_preset` fields added to audit metadata
- Config layer: `config/locales/` directory discovery at startup
</code_context>

<specifics>
## Specific Ideas

- One YAML per locale → `config/locales/de-DE.yaml`, `config/locales/fr-FR.yaml`, etc.
- Recognizer union before detection: `Universal + de-DE + fr-FR` → single recognizer set → scan once
- Checksum validators as pluggable functions: `SteuerIDValidator.validate("12345678901") → bool`
- Presets as overlays: `gdpr.yaml` specifies only `add: [NATIONAL_ID, PERSON]`, `threshold: {NATIONAL_ID: 0.85}` — not a full config
- Startup validation: collect all violations, print them, exit with code 1. No traffic served.
</specifics>

<deferred>
## Deferred Ideas

- Runtime preset reload — Phase 5+ config hot-reload concern
- Dynamic locale addition without restart — post-MVP
- Per-tenant locale overrides — Phase 8+ multi-tenancy
- Locale-specific NER models — post-MVP (en_core_web_md for all in MVP)
- Compliance reporting API beyond `GET /v1/compliance/presets` — Phase 14+ governance
</deferred>

---

*Phase: 4-Multi-Locale Detection + Compliance Presets*
*Context gathered: 2026-06-20*
