# Phase 12 Context: DLP and Advanced Detection

References: [MASTER-ARCHITECTURE.md](../../.planning/MASTER-ARCHITECTURE.md), [MASTER-SECURITY-MODEL.md](../../.planning/MASTER-SECURITY-MODEL.md), [MASTER-TEST-STRATEGY.md](../../.planning/MASTER-TEST-STRATEGY.md)

## Goal

Phase 12 extend detection beyond generic PII into PHI, PCI, MNPI, trade secrets, source code, financial records, customer data, prompt security, and output policy categories. The work is scoped as a production enterprise capability, not a prototype. It must preserve the core AnonReq guarantees: fail secure, no PII in logs, ephemeral mappings, streaming correctness, OpenAPI as source of truth, tenant isolation, and measurable security acceptance.

## Scope

In scope:
- Requirements: Req 23, Req 32, Req 36, Req 38, Req 41, Req 42, Req 49, Req 52, Req 55.
- Components: DLPClassifier, AdvancedRecognizerRegistry, PromptSecurityEngine, OutputPolicyScanner, MNPIRecognizer, FinancialCrimeRecognizer, FairnessDatasetRunner.
- API surface: GET /v1/admin/dlp/policies, PUT /v1/admin/dlp/policies/{policy_id}, GET /v1/admin/prompt-security/rules, GET /v1/admin/fairness/report.
- Metrics: anonreq_dlp_actions_total, anonreq_prompt_security_events_total, anonreq_firewall_events_total, anonreq_detection_quality_score.
- Audit events: dlp_action_applied, prompt_injection_blocked, jailbreak_flagged, output_policy_violation, mnpi_detected, financial_crime_entity_detected.

Out of scope:
- Relaxing ForwardingGuard requirements.
- Persisting token mappings, raw prompts, raw responses, raw transcript text, or original entity values.
- Adding unauthenticated administrative routes.
- Provider-specific shortcuts that bypass the internal OpenAI-compatible envelope.

## Business Value

This phase moves AnonReq from a privacy gateway toward an enterprise AI control plane. It gives security, compliance, platform, and SRE teams enforceable controls they can operate, audit, and explain during procurement, regulator review, and incident response.

## Dependencies

The phase assumes the Stage 1 gateway pipeline exists: request context, detection, tokenization, Valkey mapping, provider routing, restoration, audit logging, health checks, metrics, and property tests. It also depends on the master security model's rule that all forwarding flows through ForwardingGuard after a sanitized envelope is produced.

## Success Criteria

- All new behavior is tenant-scoped and role-protected.
- All new failures are fail-secure and produce controlled 4xx/5xx responses.
- Required metrics and audit events are emitted with metadata only.
- Tests listed in the phase test plan pass in CI.
- Documentation and OpenAPI updates are complete before implementation is marked done.
