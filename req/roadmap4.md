# Roadmap: AnonReq

## Vision

AnonReq is the AI Security Gateway for regulated enterprises.

It sits between employees, AI applications, agents, copilots, note-taking systems, meeting assistants, and AI providers, enforcing data classification, anonymization, governance, and routing policies before data reaches external models.

Core Principle:

> Sensitive data must never leave the enterprise boundary unless explicitly permitted by policy.

The roadmap is organized into three stages:

* Stage 1: Prove the Problem
* Stage 2: Build the Enterprise Platform
* Stage 3: Build the Moat

Each phase delivers a working product that can be deployed and sold independently.

---

# Stage 1: Prove the Problem

Goal:

Demonstrate that enterprises can safely use external AI systems without exposing sensitive data.

This stage creates the first paying customers.

---

## Phase 1: Foundation & Fail-Secure

Goal:

Build a secure foundation where no error condition can leak sensitive data.

Deliverables:

* FastAPI gateway
* Docker Compose deployment
* Structured audit logging
* Global exception handling
* Health endpoints
* Startup validation
* Fail-secure architecture

Success Criteria:

* No request content appears in logs
* No stack traces appear in API responses
* Service fails closed under dependency failure
* Docker deployment completes with a single command

---

## Phase 2: Classification & Anonymization MVP

Goal:

Protect employee AI usage through classification and anonymization.

Deliverables:

* Content classification engine
* Public / Internal / Confidential / Restricted classification
* PII detection
* Tokenization
* Restoration
* OpenAI-compatible API
* OpenAI provider integration
* Property-based validation

Routing Rules:

Public
→ Pass

Internal
→ Anonymize

Confidential
→ Anonymize

Restricted
→ Block

Success Criteria:

* Round-trip restoration is correct
* Restricted content is blocked
* Sensitive data never reaches provider
* First pilot deployment possible

---

## Phase 3: Multi-Provider Gateway

Goal:

Support enterprise model flexibility.

Deliverables:

* OpenAI
* Anthropic
* Gemini
* Ollama

Features:

* Provider abstraction layer
* Model aliases
* Routing policies
* Streaming support
* Tail Buffer restoration

Success Criteria:

* Provider can be switched without application changes
* Streaming restoration works reliably
* Multi-provider routing policy enforced

---

# Stage 2: Build the Enterprise Platform

Goal:

Transform the gateway into an enterprise security product.

---

## Phase 4: Policy Engine & Governance

Goal:

Move from anonymization to governance.

Deliverables:

* Policy engine
* Department policies
* Tenant policies
* Model restrictions
* Jurisdiction restrictions
* Approval workflows

Examples:

Finance
→ Claude EU only

Engineering
→ OpenAI + Claude

Legal
→ Local model only

Success Criteria:

* Policies centrally managed
* Routing decisions fully auditable
* Governance evidence generated

---

## Phase 5: AI Security Firewall

Goal:

Protect against AI-native attacks.

Deliverables:

* Prompt injection detection
* Jailbreak detection
* Data exfiltration detection
* System prompt extraction detection
* Output inspection
* Security event generation

Success Criteria:

* AI attack patterns detected
* Security alerts generated
* Dangerous requests blocked

---

## Phase 6: Observability & Compliance

Goal:

Provide visibility for security and compliance teams.

Deliverables:

* Metrics
* Dashboards
* Compliance reports
* Audit explorer
* Evidence exports

Standards:

* GDPR
* NIS2
* ISO 27001
* ISO 42001

Success Criteria:

* Compliance team can review AI activity
* Audit evidence export available
* Regulator-ready reports generated

---

# Stage 3: Build the Moat

Goal:

Become the enterprise control plane for AI.

---

## Phase 7: Agent & MCP Governance

Goal:

Control agentic AI systems.

Deliverables:

* MCP inspection
* Tool-call governance
* Agent permissions
* Human approval workflows
* Tool risk scoring

Success Criteria:

* Agent actions auditable
* Tool access controlled
* High-risk actions require approval

---

## Phase 8: Endpoint Visibility

Goal:

Protect AI usage outside managed applications.

Deliverables:

* Windows agent
* macOS agent
* Local traffic inspection
* AI application discovery

Supported Applications:

* Cursor
* Claude Desktop
* ChatGPT Desktop
* VS Code extensions
* Copilot

Success Criteria:

* Shadow AI usage discovered
* Endpoint visibility established

---

## Phase 9: Appliance Deployment

Goal:

Provide enterprise deployment options.

Deliverables:

* Virtual appliance
* On-prem deployment
* Kubernetes deployment
* Air-gapped deployment

Success Criteria:

* Deployable inside regulated environments
* No Internet dependency required

---

## Phase 10: Sovereign AI Control Plane

Goal:

Control where enterprise data is processed.

Deliverables:

* Local model routing
* GPU inference integration
* vLLM integration
* Model registry
* Sovereign deployment policies

Routing Examples:

Public
→ OpenAI

Internal
→ Claude EU

Confidential
→ Local Llama

Restricted
→ Block

Success Criteria:

* Enterprise can choose where every prompt executes
* Data sovereignty policies enforced
* Hybrid AI architecture supported

---

# Product Evolution

Phase 1–3
= AI Protection Gateway

Phase 4–6
= Enterprise AI Security Platform

Phase 7–10
= AI Governance & Sovereign AI Control Plane

---

# Commercial Milestones

After Phase 3:
Target Customers:

* Law Firms
* Accounting Firms
* Financial Advisors
* Mid-Market Enterprises

After Phase 6:
Target Customers:

* Banks
* Insurance Companies
* Asset Managers
* Healthcare Providers
* Government Agencies

After Phase 10:
Target Customers:

* Global Enterprises
* Sovereign Cloud Providers
* Regulated Industries
* National Infrastructure Operators
