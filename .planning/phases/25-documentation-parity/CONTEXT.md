# Phase 25 — Documentation Parity: Context

## Phase Scope

Multi-language documentation: translate 6 core docs into FR, ES, PT, IT, AR, NL
(8 total languages with existing EN/DE). No code changes.

## Decisions

### D1. Source Documents
**Decision:** 6 documents from `docs/en/` + 3 from root: `getting-started.md`, `installation.md`,
`deployment.md`, `api-reference.md`, `compliance.md`, `faq.md`, architecture prose summary,
security policy, operations guide.
**Rationale:** SPEC §3.2. Architecture uses prose summary per language (not mmd diagrams).

### D2. Translation Method
**Decision:** Machine translation with human review. Each language directory gets translated
markdown files. Technical terms (fail-secure, tokenization, Presidio) kept as proper nouns
with glossary reference.
**Rationale:** SPEC §3.4. Consistency of technical terminology across languages.

### D3. Translation Manifest
**Decision:** `docs/TRANSLATION_MANIFEST.md` tracking per-file: source → target mapping, date,
reviewer, status (draft/reviewed/published).
**Rationale:** SPEC §3.3. DOCS-02 requirement.

### D4. Arabic RTL
**Decision:** Arabic docs include RTL rendering guidance note in README explaining that
markdown renderers must support RTL text direction.
**Rationale:** SPEC §3.4. Deferred to v2 for full RTL verification.

### D5. Link Validation
**Decision:** All markdown links validated within each language directory. Existing
`docs-nightly.yml` workflow handles link checking.
**Rationale:** SPEC §3.4. Use existing CI infrastructure.

### D6. Glossary
**Decision:** Create `docs/GLOSSARY.md` with English terms → translations across all 8 languages.
**Rationale:** Ensures consistent technical terminology across all translations.

### D7. What NOT to translate
**Decision:** Code examples, configuration blocks, command-line snippets remain in English.
Only surrounding prose is translated. Filenames and anchors remain English.
**Rationale:** Code in translated languages breaks copy-paste workflows and tool compatibility.

## Dependencies
- **Depends on:** Phase 23 (for CI — no code dependency)
- **Depended by:** Nothing
