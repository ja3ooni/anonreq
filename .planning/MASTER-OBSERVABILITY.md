# AnonReq Master Observability

## Metrics

Prometheus metrics cover request totals, provider statuses, detection latency, tokenization/restoration overhead, entities detected, fail-secure events, audit failures, residual tokens, rate/spend limit hits, active sessions, policy decisions, DLP/firewall events, auth events, connector delivery, SLO status, and release gates.

## Logs

Operational logs are structured JSON with strict field allowlists. Audit logs are metadata-only and include session, tenant, provider, model, entity counts, classification, locale, compliance preset, latency, action codes, and failure classes. Raw prompts, responses, tokens, entity values, secrets, and internal URLs are forbidden.

## Traces

OpenTelemetry spans measure component timing and error boundaries. Span attributes use IDs, counts, policy codes, and component names only. Payload bodies and token mappings are never attached to spans.

## SLOs

Published SLOs are request success rate at least 99.9 percent over 1 hour, P95 processing overhead at most 100ms for prompts up to 1,000 words, fail-secure event rate at most 0.1 percent over 24 hours, and audit log write success at least 99.99 percent over 24 hours.
