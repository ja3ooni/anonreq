# AnonReq Security-First Architecture Roadmap

## Purpose

This document supersedes feature-first planning and establishes the architectural guardrails for AnonReq.

The goal is to ensure AnonReq is built as a security platform rather than a collection of AI gateway features.

---

# Core Product Definition

AnonReq is not:

* A reverse proxy
* A Presidio wrapper
* A token replacement engine
* An OpenAI compatibility layer

AnonReq is:

> A security gateway that guarantees sensitive enterprise information never leaves the trust boundary while preserving AI usability.

All technical decisions must support this outcome.

---

# Security Invariants

Security invariants are the product.

Features exist to enforce them.

Every phase, requirement, test, and implementation decision must map to one or more invariants.

## INV-001: No Raw PII Leaves The Gateway

Raw PII must never cross the provider boundary.

Verification:

* Property tests
* Integration tests
* Fail-secure validation

---

## INV-002: Restoration Is Lossless

For every request:

```text
anonymize -> forward -> restore
```

must produce:

```text
original == restored
```

byte-for-byte.

Verification:

* Hypothesis property testing
* Round-trip testing

---

## INV-003: Tenant Isolation Is Absolute

No request may access mappings, policies, logs, caches, or configuration belonging to another tenant.

Verification:

* Isolation tests
* Cache namespace tests
* Audit validation

---

## INV-004: Failures Must Fail Closed

When any security-critical subsystem fails:

* Detection
* Cache
* Restoration
* Provider routing
* Classification

the request must be blocked.

Verification:

```text
0 bytes forwarded upstream
```

---

## INV-005: Logs Never Contain PII

Logs must contain metadata only.

Verification:

* Property tests
* Log scanning
* Security review

---

## INV-006: Token Ownership Is Unique

A token may restore to exactly one value.

Verification:

* Property testing
* Mapping validation

---

# Architecture Principles

## Principle 1: ProcessingContext Everywhere

Every stage receives the same ProcessingContext.

Example:

```python
ctx = ProcessingContext(...)
```

No stage may bypass ProcessingContext.

No stage may create hidden state.

---

## Principle 2: Stage Registry Architecture

Pipeline execution uses:

```text
PipelineManager
    ↓
StageRegistry
    ↓
Stages
```

Each stage is independently testable.

Stages register themselves.

PipelineManager controls execution order.

---

## Principle 3: ForwardingGuard Is Mandatory

ForwardingGuard executes immediately before ProviderStage.

Nothing reaches an external provider unless:

```text
classification passed
detection completed
tokenization completed
all invariants satisfied
```

---

## Principle 4: Security Before Features

The following are features:

* Streaming
* Providers
* Locales
* Compliance presets
* Governance
* SIEM integrations

The following are products:

* Fail-secure operation
* Tenant isolation
* PII protection
* Correct restoration

Product concerns always take precedence.

---

# Recommended Execution Order

## Stage 0 — Security Foundations

### Phase 0A: Threat Model

Create:

```text
docs/threat-model.md
```

Define:

* Assets
* Threat actors
* Trust boundaries
* Attack paths
* Security assumptions

---

### Phase 0B: Security Invariants

Create:

```text
SECURITY_INVARIANTS.md
```

All future requirements reference invariant IDs.

---

# Stage 1 — Trust Boundary MVP

Goal:

Prove that enterprise data can safely interact with external LLM providers.

---

## Phase 1

Foundation

Deliver:

* Docker
* Auth
* Logging
* Health checks
* Fail-secure error handling

---

## Phase 2

Classification + Detection

Deliver:

* Classification engine
* Regex detection
* Presidio integration
* Valkey mapping
* Property tests

Lock decisions:

* ProcessingContext
* YAML capability registry
* Classification-before-detection
* UUIDv7 internal request IDs

---

## Phase 3

Pipeline Engine

Deliver:

```text
PipelineManager
StageRegistry
ProcessingContext
ForwardingGuard
```

Before streaming.

Before additional providers.

Before enterprise features.

---

## Phase 4

Tokenization & Restoration Validation

Focus exclusively on:

* Token generation
* Mapping integrity
* Restoration correctness
* Deduplication
* Property testing

Success metric:

```text
100% round-trip correctness
```

---

## Phase 5

Streaming

Deliver:

* SSE
* TailBuffer FSM
* Stream restoration
* Streaming property tests

---

## Phase 6

Provider Layer

Deliver:

* OpenAI
* Anthropic
* Gemini
* Ollama

Success metric:

Provider becomes a pluggable adapter.

---

# MVP Definition

MVP ends after Phase 6.

Required outcomes:

* Secure forwarding
* Classification
* Detection
* Restoration
* Streaming
* Multi-provider support

Not required:

* Governance
* SIEM
* CASB
* Compliance reporting
* Agent controls

---

# Enterprise Expansion

After MVP validation:

## Phase 7

Rate Limiting & Cost Controls

---

## Phase 8

Multi-Tenant Platform

Deliver:

* Tenant isolation
* Tenant policies
* Tenant keys
* Tenant audit

---

## Phase 9

Observability

Deliver:

* Prometheus
* OpenTelemetry
* Audit analytics

---

## Phase 10

Classification Policies

Deliver:

```text
Public
Internal
Confidential
Restricted
```

Policy engine becomes foundation for future DLP.

---

## Phase 11

AI Security Firewall

Deliver:

* Prompt injection protection
* Jailbreak detection
* Output inspection

---

## Phase 12

Financial Services Compliance

Target:

* Banking
* Insurance
* Healthcare

Primary enterprise revenue phase.

---

# Moat Development

After enterprise adoption:
## Phase 13 – AI Risk Intelligence Engine

Goal:
Provide semantic understanding and risk scoring without participating in enforcement decisions.

Principles:
- Advisory only
- Never blocks traffic
- Never overrides deterministic policy decisions
- Explainable outputs
- Fully auditable

Capabilities:

### Semantic Data Classification
Detect business context beyond PII:

- Source Code
- Trade Secrets
- M&A Discussions
- Financial Forecasts
- Legal Documents
- HR Information
- Customer Data
- Intellectual Property

Output:

classification:
  label: CONFIDENTIAL
  confidence: 0.92

### Risk Scoring

Generate risk score:

risk_score: 87
risk_level: HIGH

Factors:
- Data sensitivity
- Volume
- Destination model
- Tenant policy
- User role

### Policy Recommendations

Examples:

"Recommend ROUTE_LOCAL"

"Recommend BLOCK"

"Recommend additional anonymization"

Recommendations only.
Policy engine remains authoritative.

### Incident Summarization

Convert audit events into executive summaries:

- What happened
- Why it happened
- What data was involved
- Recommended action

### Security Copilot

Natural language interface:

"What was blocked yesterday?"

"Which users generated the highest risk score?"

"Show all requests involving financial data."

### Architecture

Request
    ↓
Deterministic Security Layer
    ↓
Forwarding Guard
    ↓
AI Risk Intelligence Layer
    ↓
Provider

The AI layer never participates in:
- BLOCK decisions
- ALLOW decisions
- ROUTE decisions
- ANONYMIZE decisions

Those remain deterministic.

## Phase 14

Secure RAG

---

## Phase 15

Agent Governance

---

## Phase 16

CASB & Shadow AI

---

## Phase 17

SIEM Integrations

---

## Phase 18

Endpoint Agent

---

## Phase 19

Universal AI Gateway

---

## Phase 20

Sovereign Routing

Examples:

```text
Public        -> OpenAI
Internal      -> Claude EU
Confidential  -> Local Llama
Restricted    -> Block
```

---

## Phase 21

Governance Platform

---

## Phase 22

AI Security Operating System

Long-term vision:

Single control plane for all enterprise AI traffic.

---

# Phase Exit Rule

A phase is complete only when:

1. Code is implemented
2. Unit tests pass
3. Property tests pass
4. Security invariants remain satisfied
5. No invariant regression is introduced

Feature completion alone does not close a phase.

---

# Guidance For GSD

When making implementation decisions:

1. Prefer invariant preservation over developer convenience.
2. Prefer fail-secure behavior over availability.
3. Prefer deterministic behavior over optimization.
4. Prefer explicit architecture over hidden magic.
5. Prefer testable components over clever abstractions.

If a feature conflicts with a security invariant, the invariant wins.
