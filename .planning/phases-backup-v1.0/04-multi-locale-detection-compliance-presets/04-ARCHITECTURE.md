# Phase 4 Architecture: Multi-Locale Detection + Compliance Presets

## Pipeline Integration

Phase 4 does not change the core pipeline. It extends the Detection stage:

```
Existing Pipeline (Phase 2):

Ingress → Classification → Detection → Tokenization → ForwardingGuard → Provider → Restoration → Cleanup
                              │
                          [DetectionProvider receives TextNode → Presidio Analyzer → Detection[]]

Phase 4 adds locale-aware recognizer selection BEFORE Detection:

Ingress → Classification → LocaleNegotiation → Detection → Tokenization → ForwardingGuard → Provider → Restoration → Cleanup
                              │                    │
                          [LocaleNegotiator    [DetectionProvider receives
                           resolves:           merged recognizer set from
                           header → locales →   LocaleNegotiator +
                           merge recognizers    universal recognizers]
                           → unified set]

Compliance Preset validation runs at startup:
  Base Config → CompliancePreset → Customer Overrides → Merge → Validate
                                                              ↓
                                                          Hard fail or start
```

## LocaleNegotiator

```
X-AnonReq-Locale: de-DE, fr-FR
    ↓
HeaderParser
    ↓
  ["de-DE", "fr-FR"]
    ↓
LocaleRegistry.resolve(["de-DE", "fr-FR"])
    ↓
  [LocaleBundle(de-DE), LocaleBundle(fr-FR)]
    ↓
RecognizerMerger.merge(universal + de-DE + fr-FR)
    ↓
  Unified RecognizerSet (deduplicated by entity type, highest confidence)
    ↓
DetectionProvider receives Unified RecognizerSet
    ↓
DetectionProvider scans TextNode(s) with merged recognizer set
```

## LocaleRegistry

```
startup:
  for file in config/locales/*.yaml:
    code = parse_locale_code(file)
    bundle = LocaleBundle.parse(file)
    LocaleRegistry.register(code, bundle)

  ChecksumValidatorRegistry:
    for bundle with checksum config:
      validator = ChecksumValidatorFactory.create(bundle.checksum_type)
      ChecksumValidatorRegistry.register(bundle.locale_code, validator)
```

## CompliancePresetEngine

```
startup:
  for preset in config/compliance/presets:
    engine.register(preset)

  active_presets = config.compliance.active_presets  # list from YAML

  effective = engine.merge(
    base=BaseDetectorConfig,
    presets=[base_presets[p] for p in active_presets],
    overrides=CustomerOverrides
  )

  violations = engine.validate(effective)
  if violations:
    print("Compliance preset violations:")
    for v in violations: print(f"  - {v}")
    sys.exit(1)
```

## Checksum Validation Flow

```
DetectionEngine produces Detection (locale_id, confidence)
    ↓
If entity_type has checksum validation:
    validator = ChecksumValidatorRegistry.get(entity_type)
    if validator and not validator.validate(detection.value):
        → DROP the detection
    else:
        → KEEP the detection (confidence unchanged)
If no checksum validator configured:
    → KEEP the detection (pass-through)
```

## Domain Model

```python
@dataclass
class LocaleBundle:
    code: str
    entity_types: list[EntityTypeConfig]
    checksum: ChecksumConfig | None = None
    metadata: LocaleMetadata | None = None

@dataclass
class EntityTypeConfig:
    name: str
    tier: RecognizerTier          # REGEX | NER | BOTH
    confidence_threshold: float = 0.7
    patterns: list[str] | None = None       # regex patterns (tier=REGEX)
    presidio_entities: list[str] | None = None  # presidio entity types (tier=NER)

class RecognizerTier(str, Enum):
    REGEX = "REGEX"
    NER = "NER"
    BOTH = "BOTH"

@dataclass
class ChecksumConfig:
    algorithm: str                # iso7064_mod11_2, luhn, verhoeff, custom
    validator_id: str             # key into ChecksumValidatorRegistry

@dataclass
class LocaleMetadata:
    name: str
    version: int
    maintainer: str

@dataclass
class CompliancePreset:
    id: str
    name: str
    description: str
    jurisdictions: list[str]
    mandatory_entity_types: list[str]
    thresholds: dict[str, float]
    minimum_tiers: dict[str, list[RecognizerTier]]   # entity → [REGEX, NER]
    requires_checksum: list[str]                      # entity types that need checksum validation

@dataclass
class PresetMergeResult:
    merged_entity_types: dict[str, RecognizerTier]
    merged_thresholds: dict[str, float]
    merged_minimum_tiers: dict[str, list[RecognizerTier]]
    source_presets: list[str]
    has_customer_overrides: bool
```
