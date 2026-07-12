# Phase 26 — Enterprise Guardrails: Context

## Phase Scope

Advanced secret detection (4 custom Presidio recognizers), continuous compliance monitoring
evidence endpoint, HMAC-SHA256 commercial licensing with feature gating. Three requirements:
GUARD-01, GUARD-02, GUARD-03.

## Decisions

### D1. Custom Recognizer Registration
**Decision:** New file `src/anonreq/detection/recognizers/enterprise.py` containing 4
Presidio `RecognizerResult`-producing classes. Registered with `RecognizerMerger` in the
locale pipeline via a new `register_enterprise_recognizers()` function.
**Rationale:** SPEC §4.1 and brainstorming decision: route through existing
`RegexDetector` pipeline, not Presidio sidecar. Keeps detection self-contained.

### D2. Recognizer Configuration
**Decision:** `config/recognizers.yaml` with enable/disable per recognizer, internal domain list
for hostname matching, confidence thresholds.
**Rationale:** SPEC §4.1. Hot-reload via existing watchdog pattern.

### D3. Recognizer Naming
**Decision:** Distinct names to avoid dict-key collision in Presidio:
`AnonReq_APIKeyRecognizer`, `AnonReq_AWSAccessKeyRecognizer`, `AnonReq_GitHubTokenRecognizer`,
`AnonReq_InternalHostnameRecognizer`.
**Rationale:** Brainstorming decision: explicit naming to avoid dict-key collision in Presidio.

### D4. Compliance Evidence Endpoint
**Decision:** `GET /v1/admin/compliance/evidence?framework=soc2` returning structured evidence
per framework control. Sourced from SLO compliance state, audit chain entries, governance
records, and incident history.
**Rationale:** SPEC §4.2. Extends existing `AuditChainService`. Route is admin-only (requires
admin API key).

### D5. Evidence Snapshot Storage
**Decision:** JSON Lines format, stored in MinIO (when configured) with filesystem fallback.
Scheduled via configurable cron expression (default daily).
**Rationale:** SPEC §4.2. MinIO is already in the observability stack.

### D6. Licensing Mechanism
**Decision:** HMAC-SHA256 symmetric signing of license payload: org, tier, features, expiry.
Key stored in `ANONREQ_LICENSE_SECRET` env var. Validation at startup + on each gated feature
access. No phone-home. In-memory cache for application lifetime.
**Rationale:** SPEC §4.3. Brainstorming decision.

### D7. Feature Gates
**Decision:** FastAPI `Depends` dependency `require_license(feature)` returning 402 if
license missing/expired/invalid.
**Gates:** trust_center (Free), ai_firewall (Appliance), soc_integration (Appliance),
advanced_detection (Appliance), compliance_monitoring (Appliance).
**Rationale:** SPEC §4.3. Core anonymization pipeline NEVER gated.

### D8. License Config
**Decision:** `src/anonreq/license/` package with `models.py` (LicenseKey, FeatureGate,
LicenseStatus), `validator.py` (HMAC verify), `config.py` (LicenseSettings), `router.py`
(GET /v1/admin/license status).
**Rationale:** SPEC §4.3. New package, separated from Trust Center.

### D9. License Enforcement Scope
**Decision:** Gate trust_center routes (Phase 24), SOC integration routes (existing),
custom recognizer loading (only load if licensed). Core pipeline never gated.
**Rationale:** SPEC §4.4. Anonymization, detection, tokenization remain free.

### D10. License Response on Block
**Decision:** Return HTTP 402 with `{"error": "license_required", "feature": "feature_name",
"message": "A valid Appliance-tier license is required for this feature"}`.
License status endpoint returns 200 with tier, features, expiry.
**Rationale:** SPEC §4.3. 402 is semantically correct for payment-required scenarios.

## Gray Areas Resolved

| Gray Area | Resolution |
|---|---|
| Recognizer registration | Through RegexDetector pipeline, not Presidio sidecar |
| Presidio naming collision | Prefix all recognizer names with "AnonReq_" |
| License format | HMAC-SHA256 signed JSON payload |
| License transport | ANONREQ_LICENSE_SECRET env var at startup |
| Gate response code | 402 Payment Required |
| Evidence storage | MinIO (primary) / filesystem (fallback) |
| Evidence schedule | Configurable cron, default daily |

## Dependencies
- **Depends on:** Phase 23 (CI), Phase 24 (licensing gates Trust Center routes)
- **Depended by:** Nothing (final v1.5 phase)
