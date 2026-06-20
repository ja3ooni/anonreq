# Phase 4 Test Plan

## Test Tiers

### Tier 1: Unit Tests

| Test | Scope | Plan |
|------|-------|------|
| LocaleBundle parsing | 8 YAML files parse to valid LocaleBundle models | 04-01 |
| LocaleRegistry | Startup auto-discovery, duplicate detection, validation | 04-01 |
| Checksum validators | Each validator (Steuer-ID, BSN, NIR, CPF, CNPJ, Codice Fiscale) with valid/invalid inputs | 04-01 |
| Detection drop on checksum failure | Checksum-failed detection is dropped, not downgraded | 04-01 |
| Header parsing | Single locale, multi-locale, whitespace, malformed | 04-02 |
| Multi-locale merge | Recognizer union, deduplication, highest confidence | 04-02 |
| Fallback behavior | Missing locale → en default; unknown in multi → drop+continue | 04-02 |
| Audit locale field | Correct format for single, multi, and fallback scenarios | 04-02 |
| Preset loading | 6 YAML presets parse to valid CompliancePreset models | 04-03 |
| Preset merge | Base → Preset → Overrides; union+highest threshold | 04-03 |
| Multi-preset merge | Two+ active presets, AG-14 non-weakening invariant | 04-03 |
| Startup validation | All violation types (missing entity, low threshold, missing tier) | 04-03 |
| GET /v1/compliance/presets | Returns configured presets, correct schema | 04-03 |

### Tier 2: Integration Tests

| Test | Scenario | Verification |
|------|----------|-------------|
| Locale detection e2e | Send request with `X-AnonReq-Locale: de-DE` | German-specific entities detected, checksums validated |
| Multi-locale detection e2e | `X-AnonReq-Locale: de-DE, fr-FR` | Both locale recognizers active, merged results |
| Fallback e2e | Unknown locale → falls back to en | Detection uses en recognizers, audit logs fallback |
| No-locale e2e | No header → universal only | Only universal recognizers active, audit log entry |
| Compliance startup fail | Config disables entity mandated by active preset | Gateway exits with code 1, clear error message |
| Compliance startup pass | Clean config with active preset | Gateway starts, `compliance_preset` in audit log |
| Checksum integration | Valid vs invalid national ID in text | Valid: detected. Invalid: dropped (no detection) |

### Tier 3: Property-Based Tests (Hypothesis)

| Test | Invariant | Plan |
|------|-----------|------|
| TEST-05 (from Phase 6) | Invalid checksum IDs never flagged as valid detections | 04-01 |
| LOCALE-01 | Same input + same locale header = same detection output (AG-13 determinism) | 04-02 |
| LOCALE-02 | Multi-locale merge is order-independent — `de-DE, fr-FR` = `fr-FR, de-DE` | 04-02 |
| LOCALE-03 | Adding a locale never reduces detection coverage — union property | 04-02 |
| COMP-01 | Preset merge never removes entity types from base config (AG-14) | 04-03 |
| COMP-02 | Merge(merge(a, b), c) == merge(a, merge(b, c)) — associativity | 04-03 |
| COMP-03 | Combined preset + customer overrides never disable preset-mandated types | 04-03 |

## Coverage Targets

- Locale module (bundle, registry, negotiator, merger): 95%+
- Checksum validators: 100% (security-critical — every validator must be fully exercised)
- Compliance module (preset, engine, merge, validation): 90%+
- Overall Phase 4: 85%+

## Invariants (must pass before Phase 4 closes)

1. Same input + same locale header = same detection output (AG-13)
2. Multi-locale merge is order-independent
3. Compliance preset never weakens detection (AG-14)
4. Invalid checksum IDs never appear as valid detections
5. Gateway hard-fails at startup if active preset's mandatory types are disabled
6. Adding a locale never reduces detection coverage (union property)
