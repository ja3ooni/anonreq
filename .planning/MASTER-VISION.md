# AnonReq Master Vision

AnonReq is the self-hosted AI security gateway for regulated enterprises. It sits between enterprise applications and AI providers, detects sensitive content, replaces it with context-preserving tokens, forwards only sanitized data, and restores original values inside the customer's perimeter. The product goal is not a best-effort privacy filter; it is an enforceable sovereignty boundary for AI traffic.

## Mission

Protect enterprise users from sending PII, PHI, PCI, MNPI, secrets, regulated records, source code, trade secrets, and intellectual property to AI providers while preserving developer usability, streaming latency, provider choice, and auditability.

## Product Pillars

1. Fail secure by design: Detection, policy, cache, authentication, provider translation, and restoration errors block forwarding.
2. No PII in logs: Logs, metrics, traces, reports, and evidence packages are metadata-only and field-allowlisted.
3. Streaming first: SSE restoration, Tail_Buffer handling, and stream cleanup are first-class paths, not bolt-ons.
4. Ephemeral mapping: Token mappings live only in Valkey memory and are deleted at terminal response states.
5. Enterprise control plane: Tenant isolation, RBAC, SSO, governance workflows, policy enforcement, evidence export, and compliance reporting are core product surfaces.
6. Appliance expansion: Transparent proxy, AI DLP, AI firewall, CASB, RAG protection, voice protection, and SOC integration turn the gateway into a universal AI governance enforcement point.

## Release Shape

The master architecture supports three stages: MVP gateway, enterprise platform, and appliance moat. Phases 08-21 complete the enterprise and GA path by adding policy, identity, tenancy, audit/compliance, DLP, connectors, admin UX, deployment profiles, performance proof, DR, trust center, SDK ecosystem, audit readiness, and GA release controls.
