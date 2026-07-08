# Phase 4 Task Breakdown

## Plan 04-01: Locale Recognizer Bundles

### Tasks
1. **Define LocaleBundle schema** — Pydantic model for locale YAML files
2. **Create 8 locale YAML files** — `config/locales/{de-DE,fr-FR,nl-NL,es,it-IT,ar,pt-BR,en}.yaml`
   - Each with entity types, tier assignments, confidence thresholds, checksum config (for national IDs)
3. **Implement ChecksumValidator framework**
   - Generic `ChecksumValidator` ABC with `validate(digits: str) → bool`
   - `ISO7064Mod11_2Validator` (Steuer-ID DE)
   - `LuhnValidator` (BSN NL, CPF/CNPJ BR)
   - `NIRValidator` (NIR FR — custom algorithm)
   - `CodiceFiscaleValidator` (IT)
4. **Implement ChecksumValidatorRegistry** — keyed by entity_type, populated from locale config
5. **Implement LocaleRegistry** — auto-discover YAML files from `config/locales/`, parse, validate, register
6. **Implement Checksum validation in DetectionEngine** — post-detection check, drop on failure (D-121)
7. **Unit tests**: LocaleBundle parsing, registry startup, checksum validators, detection drop logic

### Files created
- `src/gateway/locale/bundle.py` — LocaleBundle model
- `src/gateway/locale/registry.py` — LocaleRegistry
- `src/gateway/locale/checksum.py` — ChecksumValidator framework
- `src/gateway/locale/checksums/iso7064.py`
- `src/gateway/locale/checksums/luhn.py`
- `src/gateway/locale/checksums/nir.py`
- `src/gateway/locale/checksums/codice_fiscale.py`
- `config/locales/de-DE.yaml`
- `config/locales/fr-FR.yaml`
- `config/locales/nl-NL.yaml`
- `config/locales/es.yaml`
- `config/locales/it-IT.yaml`
- `config/locales/ar.yaml`
- `config/locales/pt-BR.yaml`
- `config/locales/en.yaml`
- `tests/unit/locale/test_bundle.py`
- `tests/unit/locale/test_checksum.py`
- `tests/unit/locale/test_registry.py`
- `tests/property/test_locale_checksum.py`

---

## Plan 04-02: Locale Negotiation

### Tasks
1. **Implement LocaleNegotiator** — parse `X-AnonReq-Locale` header, resolve to LocaleBundle list, merge recognizers
2. **Implement RecognizerMerger** — union of universal + locale-specific recognizers, deduplicate by entity type, highest confidence wins
3. **Implement fallback logic** — missing locale → `en` fallback + log; malformed multi-locale → drop the bad entry, log, continue
4. **Update ProcessingContext.audit_metadata** — add `locale` field
5. **Integrate LocaleNegotiator into pipeline** — new stage before Detection
6. **Update DetectionStage** — accept merged RecognizerSet from LocaleNegotiator
7. **Update DetectionProvider** — use extended recognizer set for Presidio calls
8. **Unit tests**: header parsing, multi-locale merge, fallback, error handling, audit field
9. **Integration test**: end-to-end with locale header → locale-specific detection

### Files modified
- `src/gateway/locale/negotiator.py` — LocaleNegotiator
- `src/gateway/locale/merger.py` — RecognizerMerger
- `src/gateway/detection/provider.py` — accept RecognizerSet
- `src/gateway/pipeline/stages.py` — add LocaleNegotiation stage
- `src/gateway/pipeline/context.py` — audit_metadata locale field
- `tests/unit/locale/test_negotiator.py`
- `tests/unit/locale/test_merger.py`
- `tests/integration/test_locale_detection.py`

---

## Plan 04-03: Compliance Preset Engine

### Tasks
1. **Define CompliancePreset model** — Pydantic with mandatory types, thresholds, minimum tiers
2. **Create 6 preset YAML files** — `config/compliance/gdpr.yaml`, `lgpd.yaml`, `pdpa.yaml`, `popia.yaml`, `privacy_act.yaml`, `pipeda.yaml`
3. **Implement PresetEngine** — load from YAML, merge (Base → Preset → Overrides), validate
4. **Implement startup validation** — hard fail on violations, collect all errors, exit with code 1
5. **Implement merge logic** — union entity types, highest threshold, minimum tier enforcement
6. **Implement multi-preset merge** — union of types, highest threshold, AG-14 (never weaken)
7. **Add `compliance_preset` field to audit log** — comma-separated list of active presets
8. **Implement `GET /v1/compliance/presets`** — list configured presets with metadata
9. **Add `compliance_preset` to health check** — include active presets in health response
10. **Unit tests**: preset loading, merge, validation, startup fail, multi-preset, audit field
11. **Integration test**: startup with violations → fail; startup clean → serve

### Files created/modified
- `src/gateway/compliance/preset.py` — CompliancePreset model
- `src/gateway/compliance/engine.py` — PresetEngine
- `src/gateway/compliance/merge.py` — merge logic
- `src/gateway/compliance/validation.py` — startup validation
- `config/compliance/gdpr.yaml`
- `config/compliance/lgpd.yaml`
- `config/compliance/pdpa.yaml`
- `config/compliance/popia.yaml`
- `config/compliance/privacy_act.yaml`
- `config/compliance/pipeda.yaml`
- `src/gateway/routes/compliance.py` — GET /v1/compliance/presets
- `src/gateway/main.py` — startup hook for validation
- `tests/unit/compliance/test_preset.py`
- `tests/unit/compliance/test_engine.py`
- `tests/unit/compliance/test_merge.py`
- `tests/unit/compliance/test_validation.py`
- `tests/integration/test_compliance_startup.py`

---

## File Manifest

```
config/
├── locales/
│   ├── en.yaml
│   ├── de-DE.yaml
│   ├── fr-FR.yaml
│   ├── nl-NL.yaml
│   ├── es.yaml
│   ├── it-IT.yaml
│   ├── ar.yaml
│   └── pt-BR.yaml
└── compliance/
    ├── gdpr.yaml
    ├── lgpd.yaml
    ├── pdpa.yaml
    ├── popia.yaml
    ├── privacy_act.yaml
    └── pipeda.yaml

src/gateway/
├── locale/
│   ├── __init__.py
│   ├── bundle.py
│   ├── registry.py
│   ├── negotiator.py
│   ├── merger.py
│   └── checksum.py
│   └── checksums/
│       ├── __init__.py
│       ├── iso7064.py
│       ├── luhn.py
│       ├── nir.py
│       └── codice_fiscale.py
├── compliance/
│   ├── __init__.py
│   ├── preset.py
│   ├── engine.py
│   ├── merge.py
│   └── validation.py
├── detection/
│   ├── provider.py     (modified)
├── pipeline/
│   ├── stages.py       (modified)
│   └── context.py      (modified)
├── routes/
│   └── compliance.py   (new)
└── main.py             (modified)

tests/
├── unit/locale/
│   ├── test_bundle.py
│   ├── test_checksum.py
│   ├── test_registry.py
│   ├── test_negotiator.py
│   └── test_merger.py
├── unit/compliance/
│   ├── test_preset.py
│   ├── test_engine.py
│   ├── test_merge.py
│   └── test_validation.py
├── property/
│   └── test_locale_checksum.py
└── integration/
    ├── test_locale_detection.py
    └── test_compliance_startup.py
```
