# AnonReq Gateway Architecture

This document provides a high-level prose summary of the AnonReq gateway architecture. It details the component topology, request lifecycle, and core security invariants.

## System Overview

AnonReq is a self-hosted AI security and anonymization gateway designed to sit between enterprise applications and external or local LLM (Large Language Model) providers. By acting as an intercepting proxy, it ensures that sensitive data (such as PII, PHI, PCI, or proprietary secrets) is classified, tokenized, and sanitized before crossing the trust boundary of the enterprise network.

```
┌─────────────────┐       ┌─────────────────┐       ┌───────────────────┐
│                 │       │                 │       │                   │
│   Enterprise    │──────>│ AnonReq Gateway │──────>│   LLM Providers   │
│   Application   │<──────│ (Self-Hosted)   │<──────│ (OpenAI, Gemini)  │
│                 │       │                 │       │                   │
└─────────────────┘       └─────────────────┘       └───────────────────┘
```

## Request Lifecycle

Every request sent to an external provider via AnonReq flows through a staged processing pipeline:

1. **Inbound & Content Dispatching:** The request enters the gateway. The Content-Type Dispatcher inspects the request headers and routes the payload to the appropriate analyzer (Text, JSON, or Multipart).
2. **Classification:** The Classification Engine checks the request against configured security levels. If a payload contains restricted data that is not allowed to proceed, the engine blocks the request early or determines if it needs local routing, anonymization, or direct pass-through.
3. **Detection:** The Detection Engine combines checksum/regex recognizers, Presidio client integration, and context-boosting algorithms to locate sensitive entities (e.g. Email addresses, phone numbers, credit card numbers).
4. **Tokenization:** Detected sensitive values are extracted and replaced with anonymous tokens (e.g., `[EMAIL_0]`, `[PERSON_1]`). The unique, random mappings are stored in the Valkey/Redis Cache Manager under a session-bound lifecycle.
5. **Provider Adapter:** The sanitized, tokenized request is translated by the provider adapter into the target LLM API format (e.g. converting OpenAI-compatible schema to Anthropic/Gemini) and forwarded.
6. **LLM Response:** The external LLM returns its generation containing tokenized references.
7. **Restoration:** The Restoration Engine reads the session mappings from the Cache Manager and replaces the tokens with their original values in the response payload (supporting both standard and Server-Sent Event streaming responses).
8. **Outbound:** The fully restored, natural response is returned to the client application.

## Core Components

- **Proxy/Gateway:** FastAPI application running an ASGI network loop.
- **Classification Engine:** PDP (Policy Decision Point) and PEP (Policy Enforcement Point) evaluating governance and risk policies.
- **Detection Engine:** Multi-locale entity scanner with regex recognizers and Microsoft Presidio.
- **Tokenization & Restoration Engines:** Code responsible for token substitution and replacement.
- **Cache Manager:** Ephemeral, memory-resident Valkey/Redis instance holding session maps under a strict Time-to-Live (TTL) contract.
- **Provider Adapters:** Compatibility layer translating API calls on the fly.

## Core Security Invariants

- **Zero-Exposure Invariant:** Raw PII must never cross the network boundary to external providers under any circumstances.
- **Fail-Secure/Fail-Closed Behavior:** Any runtime exception, timeout, cache unavailability, pipeline bottleneck, or classification ambiguity must result in an immediate block of outbound traffic, yielding a `503 Service Unavailable` or `403 Forbidden` response to the client application rather than leaking data.
- **No-PII Telemetry:** Logs, Prometheus metrics, and security reports are metadata-only. No raw request/response content or token keys are written to persistent stores or stdout.
- **Ephemeral Storage:** Anonymization mappings are stored only in memory-resident cache with tight TTL configurations, ensuring they are deleted immediately post-transaction and never written to durable disk storage.
