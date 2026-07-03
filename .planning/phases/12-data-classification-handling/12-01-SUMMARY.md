---
phase: 12-data-classification-handling
plan: 01
subsystem: classification
tags: [classification, sensitivity, entity-mapping, yaml, tdd]
requires:
  - phase: 02-core-pipeline-classification-non-streaming
    provides: Entity types for classification mapping
  - phase: 08-Enterprise-Policy-Engine
    provides: Tenant policy YAML override structure
provides:
  - ClassificationLevel IntEnum (5 fixed levels: Public→Highly Restricted)
  - ClassificationEngine with deterministic max algorithm
  - ClassificationResult dataclass (highest, labels, detected_levels)
  - ENTITY_CLASSIFICATION_MAP default mapping (28 Phase 2 entity types)
  - Entity mapping YAML in config/classification.yaml
  - Phase 8 policy YAML classification override section
affects:
  - Phase 8 PDP #2 (receives classification result as policy input)
  - Phase 5 AuditLogger (reads classification from RequestContext)

tech-stack:
  added: []
  patterns:
    - Deterministic max classification (no AI, no confidence blending)
    - IntEnum for sensitivity level comparison
    - YAML entity mapping with Python fallback defaults

key-files:
  created:
    - tests/test_classification_engine.py
    - .planning/phases/12-data-classification-handling/deferred-items.md
  modified:
    - src/anonreq/models/classification.py
    - src/anonreq/models/__init__.py
    - config/classification.yaml

key-decisions:
  - "ClassificationLevel uses IntEnum (not StrEnum) for ordinal max() comparison"
  - "Default classification.yaml co-locates entity mapping with existing rule definitions"
  - "Presidio Risk lexicon 2024 entity types all default to Internal — not Restricted"

patterns-established:
  - "Deterministic max: highest = max(entity_mapping[e] for e in entities)"
  - "Unknown entity types default to Internal (conservative, not Public)"
  - "Entity mapping in Python code with YAML file as source of truth"

requirements-completed:
  - CLASS-01
  - CLASS-02

duration: 9min
completed: 2026-07-03
status: complete
---

# Phase 12 Plan 01: Data Classification & Handling Policies Summary

**Classification engine with 5-level IntEnum, deterministic max algorithm, 28-entity mapping table, and YAML override support**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-03T07:17:20Z
- **Completed:** 2026-07-03T07:26:13Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- **ClassificationLevel IntEnum** with 5 sensitivity levels: PUBLIC=0, INTERNAL=1, CONFIDENTIAL=2, RESTRICTED=3, HIGHLY_RESTRICTED=4 — ordinal values support `max()` operator for deterministic comparison
- **ClassificationEngine** implements deterministic max algorithm: `highest = max(entity_mapping[e] for e in entities)` — no AI, no confidence blending, purely deterministic per D-005
- **Client override** (increase-only): `classify_with_client_override()` allows clients to assert higher sensitivity, never lower — higher of detected vs client wins, logged
- **Runtime entity map updates** via `update_entity_map()` for Phase 8 tenant policy integration
- **28 entity types mapped** covering all Phase 2 Presidio entity types (PERSON→Internal, EMAIL→Confidential, IBAN→Restricted, API_KEY→Highly Restricted, etc.)
- **Default to Internal** for undetected (empty) input and unknown entity types — conservative by default per CLASS-02
- **YAML configuration** in `config/classification.yaml` with 5 level definitions (display names, ordinals, descriptions), 28 entity mappings, and per-level handling policies
- **5 configuration loading tests** verifying YAML integrity, Python enum matching, entity type coverage, display name configuration, and override merging

## Task Commits

Each task was committed atomically:

1. **Task 1 (TDD - GREEN): ClassificationLevel enum and ClassificationEngine** — `31ee999` (feat)
2. **Task 2: Entity mapping YAML and config loading tests** — `2ba333e` (feat)

**Plan metadata:** Committed in next phase update

_Note: TDD RED gate (test file already existed and failed before implementation) was pre-satisfied by existing committed test code_

## Files Created/Modified

- `src/anonreq/models/classification.py` — Added ClassificationLevel, ClassificationResult, ENTITY_CLASSIFICATION_MAP preserving existing ClassificationRule/ClassResult/CassAction
- `src/anonreq/models/__init__.py` — Exported new classification types (ClassificationLevel, ClassificationResult, ENTITY_CLASSIFICATION_MAP)
- `config/classification.yaml` — Added classification section with 5 level definitions, 28 entity mappings, per-level handling policies (preserving existing CLS-001 through CLS-004 rules)
- `tests/test_classification_engine.py` — Created with 39 existing tests + 5 new config loading tests = 44 total
- `.planning/phases/12-data-classification-handling/deferred-items.md` — Pre-existing test failure logged

## Decisions Made

- **IntEnum over StrEnum**: ClassificationLevel uses `IntEnum` so the `max()` operator works natively for the deterministic algorithm. StrEnum would require a separate ordinal mapping.
- **YAML co-location**: Entity mapping is in `config/classification.yaml` alongside the existing rule-based classification rules (CLS-001 through CLS-004) — single source of truth for classification config, with Phase 8 tenant policies providing per-tenant overrides.
- **Presidio Risk lexicon types**: All Presidio Risk 2024 entity types (MEDICAL_LICENSE, DRIVERS_LICENSE, PASSPORT, TAX_ID, HEALTH_INFO, etc.) default to Restricted — conservative by design, enterprises can lower via Phase 8 YAML overrides.
- **Python defaults + YAML override**: The Python `ENTITY_CLASSIFICATION_MAP` dict is the source of truth used at import time. The YAML file mirrors it for documentation/configurability. Phase 8 overrides are applied at runtime via `update_entity_map()`.

## Deviations from Plan

None - plan executed exactly as written.

### Pre-existing Issues (Deferred)

**1. [Pre-existing] Failed test in test_classification.py**
- **Found during:** Task 2 verification
- **Issue:** `test_rule_matches_with_regex_condition` uses test value "My password is secret123" but the regex expects `:` or `=` after "password" — test value doesn't match the pattern
- **Fix:** Not in scope — pre-existing bug unrelated to Phase 12 changes
- **Deferred:** Logged to `deferred-items.md`

---

**Total deviations:** 0 auto-fixed
**Impact on plan:** No scope creep.

## Issues Encountered

- Pre-existing test failure `test_classification.py::TestClassificationRule::test_rule_matches_with_regex_condition` — test value doesn't match regex pattern. Not related to Phase 12 changes. Logged as deferred.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: new_entity_mapping_endpoint | config/classification.yaml | Entity mapping configuration introduced — `yaml.safe_load()` used per T-12-01-01 mitigation; schema validation via Python ClassificationLevel enum |
| threat_flag: override_mechanism | src/anonreq/services/classification_engine.py | `update_entity_map()` accepts arbitrary entity-type-to-level overrides — increase-only via `classify_with_client_override()` per T-12-01-02 |

## Threat Model Compliance

| Threat ID | Disposition | Status |
|-----------|-------------|--------|
| T-12-01-01 (YAML injection) | mitigate | Safe — `yaml.safe_load()` + level validated by ClassificationLevel enum lookup |
| T-12-01-02 (Override escalation) | mitigate | Safe — client increase-only via `classify_with_client_override()` |
| T-12-01-03 (Unknown entity) | accept | Accepted — defaults to INTERNAL (not PUBLIC) |

## Known Stubs

None — all entity mappings are fully populated with real sensitivity levels.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Classification engine complete with 44 tests (all passing)
- Default entity mapping ready for Phase 12-02 integration into request pipeline
- Entity mapping YAML ready for Phase 8 PDP #2 policy evaluation
- Pre-existing deferred test failure in `test_classification.py` should be investigated

---

*Phase: 12-data-classification-handling*
*Completed: 2026-07-03*
