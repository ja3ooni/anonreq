# AnonReq Master Security Model

## Trust Boundaries

The primary boundary is the customer perimeter. Raw sensitive content may exist only inside inbound request memory, detection memory, tokenization memory, and ephemeral Valkey mappings. External providers receive sanitized payloads only. Durable systems receive metadata, hashes, counters, classifications, HMAC tags, and evidence references, never raw prompt values or token mappings.

## Control Objectives

- Prevent unsanitized forwarding under all known failure modes.
- Prevent raw PII, PHI, PCI, MNPI, secrets, tokens, provider credentials, and internal URLs from appearing in logs, metrics, traces, UI payloads, exports, or error bodies.
- Enforce tenant isolation structurally through context-derived keys and authorization filters.
- Require strong authentication and RBAC for all administrative and governance actions.
- Preserve auditability with append-only evidence and HMAC-protected lineage records.
- Enforce TLS 1.3 and mTLS where configured, with secrets loaded from approved managers.

## Threat Model

Key threats include detection bypass, provider translation leak, cache outage, cache persistence misconfiguration, tenant confusion, log injection, prompt injection, jailbreaks, output policy violations, SIEM connector leakage, transparent proxy certificate misuse, IdP outage, stale policy bundles, and administrative overreach. Each threat is controlled through deny-biased policy resolution, startup preflight, runtime health gates, field allowlists, HMAC integrity, RBAC, immutable audit, and security acceptance gates.

## Security Release Gates

Every phase must prove: zero provider forwards on fail-secure scenarios, no raw sensitive values in logs/UI/exports, tenant isolation under concurrent load, required audit events emitted, metrics exposed, and all new administrative endpoints covered by authz matrix tests.
