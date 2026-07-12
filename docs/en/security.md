# AnonReq Security Policy

This document outlines the security posture, data handling guarantees, and incident response procedures for the AnonReq gateway.

## Security Posture

AnonReq is built on a Zero-Trust architecture. We assume all external model endpoints and public networks are untrusted, and enforce strict, fail-secure security boundaries:

- **Minimal Privilege:** All administrative routes and configuration changes require validated authorization using high-entropy API keys.
- **Fail-Secure Defaults:** All configuration parameters default to the most restrictive state (e.g. Trust Center disabled, active presets required, default block actions).
- **Isolation:** Tenant data, policy stores, and session-based caches are strictly isolated inside the Valkey memory layer using prefix namespaces.

## Anonymization and Data Guarantees

AnonReq guarantees that plaintext sensitive information is never exposed to external networks:

1. **Outbound Data Protection:** The gateway intercepts all request text, JSON objects, and multipart forms. Plaintext matches are tokenized with format-preserving variables (e.g., `[EMAIL_N]`) prior to network transit.
2. **Ephemeral Memory Model:** Token mappings are stored exclusively in Valkey/Redis cache. They are bound by strict Time-to-Live (TTL) policies and deleted immediately after the transaction response is delivered or the timeout expires.
3. **No PII in Logs or Telemetry:** Audit trails, system logs (stdout/stderr), and Prometheus metrics contain metadata only (such as request status, latency, and rule IDs). Plaintext payloads, session keys, and individual token values are never logged.

## Incident Response Protocol

AnonReq maintains an active incident response workflow for operational, cryptographic, or sanitization anomalies. Security incidents are categorized into three severity levels:

### Severity Levels

- **Severity 1 (Critical):** Plaintext PII leak or data breach; cryptographic anchor signature verification failure on the audit trail chain. Requires containment within 1 hour.
- **Severity 2 (Major):** Service outage, container crash, or complete pipeline degradation. Requires remediation within 4 hours.
- **Severity 3 (Minor):** Non-critical operational warnings or minor performance degradation (e.g. latency threshold exceeded, database DLQ build-up). Requires investigation within 24 hours.

### Response Flow

1. **Detection:** Alerts are raised via Prometheus metrics or manual validation of the audit trail integrity endpoints.
2. **Triage:** The SRE or Security on-call engineer assesses the alert and assigns severity.
3. **Containment:** For Critical incidents, the gateway can be suspended immediately (emergency suspension), or individual tenant keys can be revoked.
4. **Remediation:** Core developers isolate the root cause, build a container patch, and push the update.
5. **Recovery:** Normal operations are restored, and the integrity of the audit chain is verified.
6. **Post-Mortem:** A formal review is conducted within 5 business days to document timeline, cause, and preventative action items.
