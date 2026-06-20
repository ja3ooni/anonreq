# Phase 4 Discussion Log

**Gathered:** 2026-06-20

## Areas Discussed

### Locale Bundle Structure
- **Options presented:** Per-locale YAML files / Single mega-config / Hybrid shared+per-locale
- **Decision:** One YAML per locale. Adding a locale = dropping a file in `config/locales/`.
- **Merge order:** Base Config → Compliance Preset → Customer Overrides
- **Fallback:** Missing locale → default locale; unknown locale → HTTP 400

### Locale Negotiation Strategy
- **Decision:** Header-driven. Recognizer *union* before detection (not union of results).
- **Multi-locale:** Union of recognizers from all requested locales, dedup by entity type, highest confidence wins.
- **Error handling:** Unknown locale → HTTP 400 with supported list. Multi-locale with one bad entry → drop that entry, continue, log.

### National ID Checksum Validation
- **Decision:** Generic `ChecksumValidator` framework — separate validator per country ID format.
- **On failure:** Drop the detection entirely (not downgrade, not flag).
- **Registration:** Checksum validators registered alongside locale bundles in YAML.

### Compliance Preset Architecture
- **Decision:** Presets are overlays (entity-type lists + thresholds + tier requirements), not full config snapshots.
- **Merge sequence:** Base Config → Compliance Preset → Customer Overrides
- **Multi-preset merge:** Union of entity types, highest confidence threshold. Never weakens (AG-14).

### Preset Startup Validation
- **Decision:** Hard fail at gateway startup — exit with code 1, clear error message listing all violations.
- **Validated:** Mandatory entity types enabled, thresholds met, required recognizer tiers present.

### Extensibility Model
- **Decision:** `LocaleRegistry` auto-discovers YAML bundles from `config/locales/`. No code changes.
- **No hard cap:** 8 locales is MVP content only, not an architecture limit.

## Architectural Guardrails Added

- **AG-13:** Locale Determinism — same input + same locale = same output
- **AG-14:** Presets Cannot Weaken Security — presets only add/strengthen, never remove/weaken

## Documents Generated

- `04-CONTEXT.md` — All decisions (D-110 through D-137)
- `04-ARCHITECTURE.md` — Architecture document with pipeline diagrams and domain model
- `04-TASK-BREAKDOWN.md` — 3 plans, file manifest
- `04-TEST-PLAN.md` — 3-tier test strategy with property tests

## Deferred Ideas

- Runtime preset reload — Phase 5+
- Dynamic locale addition without restart — post-MVP
- Per-tenant locale overrides — Phase 8+
- Locale-specific NER models — post-MVP
- Compliance reporting API beyond `GET /v1/compliance/presets` — Phase 14+
