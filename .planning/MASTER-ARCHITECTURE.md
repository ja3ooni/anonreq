# AnonReq Master Architecture

## System Topology

AnonReq is a stateless FastAPI gateway backed by Valkey for ephemeral token mappings and PostgreSQL for durable metadata such as tenants, policy versions, governance records, audit evidence indexes, lineage records, incidents, and compliance artifacts. Presidio Analyzer and custom recognizer bundles provide hybrid detection. Provider adapters translate an OpenAI-compatible internal representation into OpenAI, Azure OpenAI, Anthropic, Gemini, Ollama, and appliance connector formats.

## Runtime Components

- Gateway API: owns request intake, authentication, tenant context, schema validation, policy enforcement, pipeline orchestration, provider routing, restoration, and response delivery.
- Detection Engine: runs regex, checksum, NER, locale bundles, custom recognizers, prompt security rules, DLP classifiers, MNPI, financial crime, and fairness-measured detection.
- Tokenization Engine: produces `[TYPE_N]` placeholders, deduplicates exact normalized values per session, preserves offsets, and writes mappings before forwarding.
- Restoration Engine: restores tokens in non-streaming and streaming responses, supports case-insensitive and bracket-optional matching, and verifies residual tokens.
- Cache Manager: wraps Valkey with persistence-disabled checks, tenant/session key construction, TTL extension for long streams, and cleanup in all terminal states.
- Policy Engine: evaluates tenant, classification, region, provider, model, spend, rate, DLP, firewall, human oversight, and business-unit policies.
- Audit and Evidence Center: emits metadata-only operational audit logs, immutable durable compliance records, lineage records, config history, exports, and evidence packages.
- Admin and Governance Plane: exposes secure UI/API for policy, tenant, RBAC, oversight, incidents, risk assessments, lifecycle, and reports.
- Connector Runtime: integrates secrets managers, SIEM, CASB, RAG stores, voice/meeting systems, agent frameworks, and transparent proxy modes.

## Request Path

1. Authenticate principal and resolve tenant.
2. Validate OpenAI-compatible request schema or connector-native schema.
3. Load tenant policy and evaluate pre-forward controls.
4. Detect sensitive content across messages, tool calls, JSON leaves, metadata, RAG chunks, or transcripts.
5. Classify request and resolve DLP/policy action.
6. Tokenize or redact as required; write mappings before provider forwarding.
7. Translate provider payload and forward sanitized content only.
8. Restore response tokens within the perimeter.
9. Run output policy and residual-token verification.
10. Emit audit, metrics, lineage, transparency, and cleanup events.

## Fail-Secure Boundaries

ForwardingGuard is the only component allowed to send upstream traffic. It requires a signed `SanitizedEnvelope` containing tenant ID, session ID, policy decision, detection result checksum, tokenization result checksum, provider route, and cache write confirmation. Any missing or invalid field blocks forwarding.
