# Product Requirements Document: AnonReq

**Product Name:** AnonReq — AI Security Gateway for Regulated Enterprises
**Version:** 1.0
**Status:** Draft
**Last Updated:** 2026-06-26

---

## Table of Contents

1. Executive Summary
2. Problem Statement
3. Target Audience and Personas
4. User Stories
5. Functional Requirements
6. Non-Functional Requirements
7. Use Cases
8. Out of Scope
9. Success Metrics
10. Release Criteria
11. Appendix: Requirement Traceability

---

## 1. Executive Summary

AnonReq is a self-hosted anonymization gateway that sits between enterprise applications and external LLM APIs. It intercepts outbound requests, detects and replaces personally identifiable information (PII), protected health information (PHI), and financial identifiers with context-preserving placeholder tokens, forwards only sanitized data to supported LLM providers (OpenAI, Anthropic, Gemini, Ollama), and restores original values in responses -- all within the customer's secure perimeter. No raw sensitive data ever crosses the network boundary.

The core value proposition: enterprises can safely use external AI systems without exposing sensitive data, without modifying application code (beyond changing a `base_url`), and without trusting the LLM provider with regulated data.

**Target market:** Regulated enterprises across Europe, Asia-Pacific, Africa, South America, and Canada -- including law firms, accounting firms, financial institutions, insurers, healthcare organizations, and government agencies operating under GDPR, LGPD, PDPA, POPIA, PIPEDA, DORA, NIS2, EU AI Act, and financial-sector regulations.

**Commercial model:** Apache 2.0 open-source core with enterprise and appliance commercial tiers. The open-source core delivers the fundamental anonymization pipeline; enterprise and appliance tiers add SSO/RBAC, policy engine, admin portal, advanced DLP, AI firewall, SIEM/CASB/RAG/voice connectors, governance reporting, and regulated-industry evidence packages.

**Release stages:**
- Stage 1 (MVP): Deployment-ready gateway with core anonymization, streaming, multi-provider, multi-locale, and compliance presets.
- Stage 2 (Enterprise): Enterprise platform with rate limiting, multimodal anonymization, AI firewall, governance, financial services compliance, and advanced DLP.
- Stage 3 (Appliance): Universal AI traffic governance with transparent proxy, agent governance, CASB, SIEM integration, and sovereign AI control plane.

---

## 2. Problem Statement

### 2.1 The AI Data Leakage Crisis

Enterprise adoption of large language models (LLMs) has created a fundamental data security problem: employees and internal applications routinely send sensitive data to external AI providers as part of normal workflow. A legal associate pastes contract language into ChatGPT for summarization. A financial analyst asks an AI to analyze a spreadsheet containing client PII. A developer uses an AI coding assistant on proprietary source code. In each case, regulated data crosses the enterprise network boundary to an external provider's infrastructure -- often in a different jurisdiction -- without the organization's knowledge or consent.

### 2.2 Shadow IT and Unauthorized AI Usage

Surveys indicate that the majority of enterprise AI usage occurs through personal accounts and unapproved channels. Employees use consumer-grade AI tools for work tasks because they are frictionless and immediately available. IT and security teams lack visibility into which AI services are being used, by whom, and with what data. This creates uncontrolled data exfiltration risk and regulatory exposure that security teams cannot audit or remediate after the fact.

### 2.3 Regulatory Risk

Regulated enterprises face significant legal exposure when sensitive data reaches external AI providers:

- **GDPR Article 28** requires data processors to implement appropriate technical measures. Sending personal data to LLM providers without anonymization violates the data minimization principle (Article 5) and may constitute an unlawful transfer (Chapter V).
- **EU AI Act** imposes obligations on deployers of AI systems, including risk management, human oversight, and transparency requirements.
- **DORA (Digital Operational Resilience Act)** requires financial entities to manage ICT third-party risk, including AI service providers.
- **SEC Rule 10b-5** and equivalent regulations prohibit the disclosure of material non-public information (MNPI). An analyst using an external AI tool with MNPI-containing prompts may violate securities laws.
- **HIPAA, LGPD, PIPEDA, POPIA, and other data protection laws** impose similar restrictions on cross-border data flows and require technical safeguards for regulated data.

### 2.4 Existing Solutions Are Inadequate

Existing approaches to AI data protection fall into three categories, each with significant limitations:

1. **Block-and-pray:** Firewall rules that block AI API domains -- ineffective because users bypass them with personal devices and VPNs, and productive AI use is blocked entirely.
2. **SaaS proxy services:** Third-party anonymization services -- require trusting another external provider with sensitive data and create additional third-party risk exposure.
3. **Custom in-house solutions:** Bespoke regex filtering built by internal teams -- fragile, language-specific, detection-incomplete, and expensive to maintain across multiple provider schemas and streaming protocols.

### 2.5 The Gap

No self-hosted, production-grade, multi-provider, multi-locale anonymization gateway exists that:
- Sits within the customer's perimeter (no data leaves the customer's infrastructure)
- Provides a single OpenAI-compatible wire protocol (one integration for all providers)
- Supports streaming responses with real-time token restoration
- Detects PII across 8 locales with hybrid regex + NER pipeline
- Provides per-jurisdiction compliance presets
- Emits verifiable, metadata-only audit logs
- Fails secure under all error conditions (never forwards unsanitized data)

AnonReq fills this gap.

---

## 3. Target Audience and Personas

### 3.1 Primary Personas

#### Chief Information Security Officer (CISO)
- **Organization:** Enterprise with 1,000+ employees
- **Goals:** Eliminate data exfiltration risk via AI channels; provide evidence to regulators that sensitive data never leaves the perimeter; maintain productivity benefits of AI while enforcing security policy.
- **Pain points:** Shadow AI usage is invisible; existing controls (DLP, firewalls) are not AI-aware; cannot prove to regulators that data is protected.
- **Key requirements:** Fail-secure architecture (Req 2), AI firewall (Req 36, 52), data classification (Req 41), DLP (Req 49), SOC integration (Req 56).

#### Data Protection Officer (DPO) / Compliance Officer
- **Organization:** Enterprise subject to GDPR, LGPD, HIPAA, or equivalent
- **Goals:** Ensure AI data processing complies with applicable regulations; produce audit evidence for regulatory examinations; enforce jurisdiction-specific PII detection.
- **Pain points:** Cannot verify that an LLM provider is GDPR-compliant; manual audit processes are expensive; regulatory landscape varies by jurisdiction.
- **Key requirements:** Multi-locale detection (Req 8), compliance presets (Req 9), metadata-only audit logs (Req 10), governance framework (Req 27), conformity assessment (Req 35), record retention (Req 45).

#### Platform Operator / DevOps Engineer
- **Organization:** IT operations team supporting 10-500+ developers
- **Goals:** Deploy and operate the gateway with minimal overhead; ensure high availability and performance; manage configuration changes without downtime.
- **Pain points:** Complex deployment procedures; lack of observability; configuration drift across environments.
- **Key requirements:** Docker Compose deployment (Req 12), metrics (Req 13), SLO tracking (Req 24), config audit trail (Req 25), rate limiting (Req 22), custom rules (Req 11).

#### Enterprise Developer
- **Organization:** Development team building AI-powered applications
- **Goals:** Use any LLM provider without vendor lock-in; maintain productivity with streaming; avoid code changes to existing integrations.
- **Pain points:** Each provider has a different API schema; changing providers requires code changes; streaming responses break with naive proxy implementations.
- **Key requirements:** OpenAI-compatible API (Req 1), multi-provider support (Req 7), SSE streaming (Req 6), SDK examples (Req 15).

### 3.2 Secondary Personas

#### AI Governance Manager
- **Organization:** Enterprise AI center of excellence
- **Goals:** Maintain an inventory of approved AI models and providers; enforce lifecycle governance; track fairness and bias metrics.
- **Key requirements:** AI lifecycle management (Req 31), model risk management (Req 39), bias monitoring (Req 32), third-party supplier governance (Req 33).

#### Model Risk Officer (Financial Services)
- **Organization:** Regulated bank or asset manager
- **Goals:** Govern AI models under SR 11-7; maintain model inventory with approval status; enforce review cycles.
- **Key requirements:** Model risk management (Req 39), financial services compliance (Req 37), MNPI protection (Req 38).

#### Security Operations Center (SOC) Analyst
- **Organization:** Enterprise SOC team
- **Goals:** Monitor AI security events through existing SIEM; correlate AI-related threats with broader security telemetry; respond to AI incidents.
- **Key requirements:** SIEM integration (Req 56), AI firewall events (Req 52), security event generation (Req 36).

#### Legal Counsel / Privacy Officer
- **Organization:** Legal department
- **Goals:** Respond to data subject access requests; manage legal holds; ensure eDiscovery readiness.
- **Key requirements:** Record retention (Req 45), data lineage (Req 44), legal hold (Req 45), data subject rights (Req 16 compliance).

---

## 4. User Stories

### 4.1 Must Have (MVP -- Stage 1)

| ID | Persona | Story |
|----|---------|-------|
| US-01 | Developer | As an enterprise developer, I want to route my existing LLM API calls through AnonReq by changing only the `base_url`, so that my application automatically operates within regulatory compliance without any other code changes. |
| US-02 | CISO | As a Chief Information Security Officer, I want a cryptographic guarantee that raw sensitive data can never reach an external LLM provider even if an internal component fails, so that I can present AnonReq to our regulators as a data sovereignty enforcement layer rather than a best-effort filter. |
| US-03 | DPO | As a Data Protection Officer, I want the gateway to detect both structured PII (IBANs, tax IDs, credit card numbers) and unstructured PII (names, addresses, relationships) in a single pipeline, so that detection coverage is comprehensive and verifiable against our data inventory. |
| US-04 | Developer | As an enterprise developer, I want PII to be replaced with labeled placeholders that preserve the entity type and unique index, so that the LLM can reason about the structure of the prompt without seeing the raw values. |
| US-05 | Security Architect | As a security architect, I want the token-to-value mapping to exist only in RAM during a single request-response lifecycle and to be provably deleted afterward, so that a server seizure or disk forensics investigation cannot recover any sensitive values. |
| US-06 | Developer | As an enterprise developer, I want streaming responses to work transparently through the gateway so that time-to-first-token latency is preserved for interactive applications, and tokens are restored in the stream before reaching the client. |
| US-07 | Platform Engineer | As an enterprise infrastructure engineer, I want to configure AnonReq once and route traffic to OpenAI, Anthropic, Gemini, or a local Ollama instance without changing application code, so that our provider strategy remains flexible and vendor lock-in is avoided. |
| US-08 | Compliance Officer | As a compliance officer at a European financial institution, I want AnonReq to detect PII in German, French, Dutch, Spanish, Italian, Arabic, Portuguese/Brazilian, and English prompts, so that our multilingual workforce can use LLM tooling without creating GDPR exposure across any language we operate in. |
| US-09 | Legal Counsel | As a legal counsel advising a financial institution operating in multiple jurisdictions, I want to select a compliance preset that automatically enables the entity types and detection thresholds required by the applicable data protection regulation, so that AnonReq deployment decisions are defensible during regulatory audit. |
| US-10 | DPO | As a Data Protection Officer, I want structured audit logs that prove the gateway anonymized sensitive entities on every request, without the logs themselves becoming a PII liability, so that I can satisfy regulatory audit requirements under GDPR Article 30 without creating a secondary data store that needs its own protection measures. |
| US-11 | Platform Engineer | As a platform engineer at a financial services firm, I want to define custom regex patterns for our internal identifiers (employee IDs, account numbers, fund codes) and maintain an exclusion list for product names and system terms, so that AnonReq covers our domain-specific PII without generating false positives on business terminology. |
| US-12 | DevOps Engineer | As a DevOps engineer, I want to bring up a fully functional AnonReq gateway with a single `docker compose up` command that starts all required services with correct networking, so that we can deploy to a pilot customer's VPC in under 30 minutes. |
| US-13 | Compliance Officer | As a compliance officer, I want assurance that no residual tokens remain in the delivered response even if partial restoration fails, so that end users never see raw placeholder artifacts that could signal a gateway misconfiguration. |
| US-14 | Principal Engineer | As a principal engineer responsible for certifying AnonReq for production use, I want a property-based test suite that proves the anonymization guarantees hold across arbitrary inputs, so that correctness is demonstrated by generative proof rather than manually selected test cases. |
| US-15 | Developer | As a developer at a European or Brazilian financial institution, I want to read the integration guide in my primary language and find working code examples for my stack, so that I can evaluate and deploy AnonReq within a single business day without requiring a sales call or professional services engagement. |

### 4.2 Should Have (Enterprise -- Stage 2)

| ID | Persona | Story |
|----|---------|-------|
| US-16 | Platform Operator | As a platform operator, I want per-tenant rate limits and spend controls enforced at the gateway, so that no single tenant can exhaust provider capacity or exceed approved budgets, and clients receive standard HTTP signals they can act on programmatically. |
| US-17 | Platform Engineer | As a platform engineer, I want the anonymization pipeline to cover all content types that can carry sensitive data -- not just chat text -- so that tool outputs, JSON payloads, and file metadata are protected by the same guarantees as plain messages. |
| US-18 | SRE | As an SRE responsible for AnonReq in production, I want a comprehensive observability stack -- structured logs, metrics, and SLO tracking -- so that I can detect degradation before it causes compliance failures and demonstrate adherence to published SLOs. |
| US-19 | Security Officer | As a security officer, I want every administrative configuration change recorded in an immutable, queryable audit trail, so that I can reconstruct the configuration state at any point in time and provide evidence to auditors. |
| US-20 | Security Engineer | As a security engineer responsible for software supply chain integrity, I want a machine-readable inventory of every dependency in every AnonReq release, so that I can assess exposure when a new CVE is published and satisfy procurement security questionnaires. |
| US-21 | Board Member | As a board member, I want clear accountability for AI systems operated by our organization, so that governance responsibilities are assigned, measurable, and auditable under ISO/IEC 42001:2023 and the EU AI Act. |
| US-22 | CISO | As a CISO, I want the gateway to detect and block prompt injection attempts, jailbreak patterns, and policy-violating outputs as a baseline capability, so that AI misuse risks are mitigated at the infrastructure layer before the full Appliance tier is deployed. |
| US-23 | Compliance Officer (Financial) | As a compliance officer at a regulated financial institution, I want AnonReq aligned with financial-sector regulatory obligations, so that deployment can be approved by internal risk and compliance teams without a bespoke gap analysis. |
| US-24 | Hedge Fund CISO | As a hedge fund or asset manager, I want AnonReq to detect and protect MNPI in AI prompts, so that trading desks using LLM tooling cannot inadvertently disclose material information in violation of securities laws. |
| US-25 | Model Risk Officer | As a Model Risk Officer at a regulated financial institution, I want every AI model used through the Gateway governed under the firm's model risk framework, so that AnonReq deployments are defensible under SR 11-7 guidance and equivalent international frameworks. |
| US-26 | InfoSec Officer | As an information security officer at a financial institution, I want every request classified by sensitivity level before transmission to an AI provider, so that information handling policies are enforced consistently and classification decisions are auditable. |
| US-27 | Financial Crime Officer | As a financial crime compliance officer, I want the Gateway to detect and flag financial-crime-relevant identifiers in AI prompts, so that analysts using LLM tooling cannot inadvertently expose case details to external models. |
| US-28 | Legal Counsel | As legal counsel, I want records under litigation hold to be protected from deletion regardless of retention schedule, and want configurable retention policies for all record types, so that AnonReq meets eDiscovery and regulatory record-keeping obligations. |
| US-29 | Hedge Fund CISO | As a hedge fund CISO, I want AI access controls that segregate trading desks, research teams, operations, compliance, and risk functions, so that information barriers are maintained even within a single AnonReq deployment. |

### 4.3 Could Have (Appliance -- Stage 3)

| ID | Persona | Story |
|----|---------|-------|
| US-30 | Enterprise Architect | As an enterprise architect, I want all AI interactions across every application and user surface routed through a single enforcement point, so that governance policies are applied consistently regardless of which AI service or interface an employee uses. |
| US-31 | CISO | As a CISO, I want AI-specific DLP controls that classify and enforce policy on sensitive data across all AI traffic types, so that data exfiltration via AI channels is prevented at the infrastructure layer. |
| US-32 | Compliance Officer | As a compliance officer at a financial institution, I want voice conversations and meeting transcripts protected before they reach any AI system, so that verbal disclosure of sensitive information cannot be exfiltrated via AI meeting assistants or voice bots. |
| US-33 | AI Governance Officer | As an AI governance officer, I want all agent actions -- tool invocations, function calls, and MCP protocol messages -- inspected and governed before execution, so that autonomous agents cannot exfiltrate data or take unauthorized actions. |
| US-34 | CISO | As a CISO, I want an AI firewall layer that protects models from malicious inbound traffic and protects users from unsafe outbound responses, so that the Appliance provides active security enforcement beyond passive policy application. |
| US-35 | Security Admin | As a security administrator, I want full visibility into all AI service usage across the enterprise network, including shadow AI not routed through approved channels, so that I can enforce AI governance policy on all AI activity, not just sanctioned tools. |
| US-36 | Cloud Security Architect | As a cloud security architect, I want CASB-style governance controls applied to AI SaaS applications, so that corporate data policies are enforced on AI-assisted SaaS workflows as well as direct API usage. |
| US-37 | Data Owner | As a data owner, I want documents retrieved by RAG systems inspected and anonymized before exposure to LLMs, so that the retrieval layer cannot inadvertently include sensitive data in model context without governance controls. |
| US-38 | SOC Analyst | As a SOC analyst, I want AI security events from the Appliance integrated into the enterprise SIEM platform, so that AI-related threats are correlated with broader security telemetry and investigated through standard incident response workflows. |
| US-39 | Enterprise Architect | As an enterprise architect, I want the Appliance to intercept all outbound AI traffic seamlessly at the network level, so that any application is secured without requiring developers to change their API `base_url` configurations. |

---

## 5. Functional Requirements

### 5.1 Core Anonymization Pipeline (MVP)

#### REQ-CORE-01: POST /v1/chat/completions Endpoint
The Gateway SHALL expose a `POST /v1/chat/completions` endpoint accepting OpenAI-compatible request payloads (including `model`, `messages`, `temperature`, `max_tokens`, `stream`). Non-conforming payloads SHALL receive HTTP 400 with a structured error body.

#### REQ-CORE-02: Cross-Role Detection
The Detection_Engine SHALL scan all text content across all message roles (system, user, assistant, tool, function) before any content is forwarded to an external provider.

#### REQ-CORE-03: Fail-Secure on Detection Error
If the Detection_Engine returns an error or is unreachable, the Gateway SHALL return HTTP 500 and SHALL NOT forward any part of the original request.

#### REQ-CORE-04: Fail-Secure on Cache Error
If the Cache_Manager is unreachable when a Mapping write is attempted, the Gateway SHALL return HTTP 500 and SHALL NOT forward any part of the original request.

#### REQ-CORE-05: Tokenization Output
When tokenization completes without error, the Tokenization_Engine SHALL produce a modified request payload in which every detected entity span has been replaced by its corresponding Token, with all other payload fields preserved verbatim.

#### REQ-CORE-06: Response Restoration
When the external provider returns a response, the Restoration_Engine SHALL replace every Token in all text-bearing response fields (including `content`, `tool_calls` arguments, `refusal` fields) with its original value before delivering the response to the caller.

#### REQ-CORE-07: Unmatched Token Handling
If a Token appears in the LLM response that is not present in the current session's Mapping, the Restoration_Engine SHALL leave the Token as-is and SHALL emit a structured warning log entry containing only the Session_ID and the unmatched Token string.

#### REQ-CORE-08: Post-Response Cache Cleanup
When response delivery is complete, the Cache_Manager SHALL delete the Mapping for the current Session_ID within 100ms of the response being fully written to the client connection.

#### REQ-CORE-09: Processing Overhead Budget
The Gateway SHALL enforce a processing overhead (from request receipt to first byte forwarded to external provider) of no more than 100ms at P95 for prompts containing 1,000 words or fewer.

#### REQ-CORE-10: Round-Trip Correctness
The Gateway SHALL accept valid request payloads and produce valid anonymized-and-restored responses, ensuring that every Token inserted by the Tokenization_Engine has been replaced by its original value in the delivered response.

#### REQ-CORE-11: Fail-Secure on Restoration Cache Miss
If the Cache_Manager is unreachable when a Mapping read is attempted during restoration, the Gateway SHALL return HTTP 500 and SHALL NOT deliver any partial response containing unreplaced Tokens.

### 5.2 Hybrid PII Detection Engine (MVP)

#### REQ-DET-01: Regex Recognizer Tier
The Detection_Engine SHALL support a regex-based recognizer tier with Luhn or format-checksum validation where applicable, detecting: email address, phone number (E.164 and national formats), credit card number (Luhn validated), IBAN (format and country prefix validated), IPv4 address, IPv6 address, URL, date of birth, national identification numbers (per active locale), SWIFT/BIC code, and cryptocurrency wallet address.

#### REQ-DET-02: NER Recognizer Tier
The Detection_Engine SHALL support an NER-based recognizer tier detecting: person name, organization name, street address, city/region name, and job title.

#### REQ-DET-03: Regex-NER Conflict Resolution
When both the regex tier and the NER tier produce overlapping entity spans, the Detection_Engine SHALL resolve by retaining the regex result and discarding the NER result for the entire overlapping region.

#### REQ-DET-04: Configurable Confidence Thresholds
The Detection_Engine SHALL apply a configurable Confidence_Threshold (0.0-1.0, default 0.7) per entity type. Detections below threshold SHALL be excluded.

#### REQ-DET-05: Exclusion List
The Detection_Engine SHALL load an Exclusion_List from configuration at startup. Case-folded, whitespace-stripped exact matches SHALL be excluded from detection.

#### REQ-DET-06: Custom Pattern Support
Where a custom regex pattern is defined in configuration for a named entity type, the Detection_Engine SHALL apply that pattern in addition to built-in recognizers for that type.

#### REQ-DET-07: Full Payload Coverage
The Detection_Engine SHALL scan all text fields in the request payload, including system message content, user message content, assistant message content, tool/function call arguments, and tool result content.

### 5.3 Context-Preserving Tokenization (MVP)

#### REQ-TOK-01: Token Format
The Tokenization_Engine SHALL replace each detected entity span with a Token of the form `[TYPE_N]`, where TYPE is an uppercase ASCII string of 1-20 characters and N is a positive integer.

#### REQ-TOK-02: Deduplication
When the same raw entity value (Unicode NFC normalized, byte-for-byte) appears more than once in a request payload, the Tokenization_Engine SHALL assign the same Token to all occurrences.

#### REQ-TOK-03: Distinct Tokens for Distinct Values
When two different entity values of the same type appear in a request, the Tokenization_Engine SHALL assign different Tokens with distinct indices (e.g., `[NAME_1]` and `[NAME_2]`).

#### REQ-TOK-04: Reverse-Offset Replacement
The Tokenization_Engine SHALL perform entity replacement in reverse character-offset order (highest start position first) to prevent position drift.

#### REQ-TOK-05: Formatting Preservation
The Tokenization_Engine SHALL preserve all whitespace, punctuation, and formatting immediately adjacent to replaced spans exactly as received.

#### REQ-TOK-06: Mapping Storage
The Tokenization_Engine SHALL store the complete Mapping as a hash keyed by `anonreq:{Session_ID}` in the Cache_Manager with TTL [60, 3600] seconds (default 300), before forwarding the request to the external provider.

#### REQ-TOK-07: No-Entity Passthrough
When a request contains no detected entities, the Tokenization_Engine SHALL forward the request unchanged and SHALL NOT create a Mapping entry.

#### REQ-TOK-08: Cross-Request Randomization
When a new Session_ID is created, the Tokenization_Engine SHALL derive token index offsets from a cryptographically random seed per session, using `secrets.token_bytes(16)`.

### 5.4 Ephemeral Mapping Store (MVP)

#### REQ-CACHE-01: Persistence Disabled
The Cache_Manager SHALL store all Mappings in Valkey configured with `save ""`, no AOF, no RDB snapshots.

#### REQ-CACHE-02: Memory Management
The Cache_Manager SHALL configure `maxmemory` of at least 256 MB with `allkeys-lru` eviction policy.

#### REQ-CACHE-03: Monitoring Commands Disabled
The Cache_Manager SHALL disable `MONITOR`, `SLOWLOG`, and keyspace notifications.

#### REQ-CACHE-04: Post-Response DEL (Non-Streaming)
When a non-streaming response has been fully written, the Cache_Manager SHALL issue an async `DEL` for `anonreq:{Session_ID}`. On failure, rely on TTL-based eviction (no retry).

#### REQ-CACHE-05: Post-Stream DEL
When a streaming response reaches terminal event (`[DONE]` or connection close), the Cache_Manager SHALL issue an async `DEL` within 100ms.

#### REQ-CACHE-06: TTL Extension for Long Streams
While a streaming response is in progress and elapsed time exceeds 80% of configured TTL, the Cache_Manager SHALL extend the key's TTL by the Session TTL value.

#### REQ-CACHE-07: Health Check
The Cache_Manager SHALL expose a health check verifying: reachable within 200ms, test key write/read, persistence disabled (`CONFIG GET save` returns empty string), AOF disabled (`CONFIG GET appendonly` returns `no`).

### 5.5 SSE Streaming Support (MVP)

#### REQ-SSE-01: Streaming Passthrough
When `stream: true`, the Gateway SHALL forward a streaming request to the external provider and return `text/event-stream` without buffering the complete response.

#### REQ-SSE-02: Pre-Fetch Mapping
The Restoration_Engine SHALL pre-fetch the complete Mapping via a single `HGETALL` at stream start, performing all subsequent lookups against the local in-memory copy.

#### REQ-SSE-03: Tail_Buffer for Split Tokens
When a Token is split across two consecutive SSE chunks, the Restoration_Engine SHALL buffer the incomplete Token suffix using a Tail_Buffer (max 512 characters) and complete the replacement when the remainder arrives.

#### REQ-SSE-04: Case-Insensitive Matching
The Restoration_Engine SHALL apply case-insensitive Token matching so that `[name_1]` or `[Name_1]` are correctly resolved.

#### REQ-SSE-05: Bracket-Optional Matching
The Restoration_Engine SHALL apply bracket-optional Token matching so that `NAME_1` bounded by word boundaries is correctly resolved.

#### REQ-SSE-06: Tail_Buffer Flush
When a Tail_Buffer contains a partial Token prefix not completed after 50 consecutive chunks or 500ms (whichever is shorter), the Restoration_Engine SHALL emit a structured log entry and yield buffered content as-is.

#### REQ-SSE-07: Anti-Buffering Headers
The Gateway SHALL propagate `Cache-Control: no-cache`, `X-Accel-Buffering: no`, and `Connection: keep-alive` on all streaming responses.

#### REQ-SSE-08: Final Flush on Stream End
When a streaming response reaches terminal event or connection close, the Restoration_Engine SHALL flush any remaining Tail_Buffer content before closing.

### 5.6 Multi-Provider LLM Support (MVP)

#### REQ-PROV-01: OpenAI-Compatible Passthrough
The Gateway SHALL support OpenAI-compatible providers (including Azure OpenAI) by forwarding requests in OpenAI's native JSON schema with only the `Authorization` header replaced by the gateway-managed API key.

#### REQ-PROV-02: Anthropic Translation
When routed to Anthropic Claude, the Provider_Adapter SHALL translate the OpenAI `messages` array into Anthropic's Messages API format for both streaming and non-streaming modes.

#### REQ-PROV-03: Gemini Translation
When routed to Google Gemini, the Provider_Adapter SHALL translate the OpenAI payload into Gemini's `contents[]` format with `generationConfig` parameter mapping for both streaming and non-streaming modes.

#### REQ-PROV-04: Ollama Support
The Gateway SHALL support Ollama by forwarding requests to a configurable base URL using OpenAI-compatible message format.

#### REQ-PROV-05: Model Alias Routing
When a request's `model` field matches a configured model alias, the Provider_Adapter SHALL route to the corresponding upstream provider and translate the model name.

#### REQ-PROV-06: Provider API Key Injection
The Gateway SHALL inject the upstream provider's API key from environment variables or a secrets file, ensuring client applications never store provider keys.

#### REQ-PROV-07: GET /v1/models
The Gateway SHALL expose `GET /v1/models` returning the list of configured model aliases and their target providers.

#### REQ-PROV-08: Error Forwarding Safety
When the upstream provider returns an HTTP error, the Gateway SHALL forward the status with only a generic error message and SHALL NOT include provider API keys, internal URLs, raw prompt content, or Token values.

#### REQ-PROV-09: Unrecognized Model Handling
If a request's `model` field does not match any configured alias, the Gateway SHALL return HTTP 400.

#### REQ-PROV-10: Fail-Secure Translation
If the Provider_Adapter fails to translate the request payload, the Gateway SHALL return HTTP 500 and SHALL NOT forward any content.

### 5.7 Multi-Locale Detection (MVP)

#### REQ-LOCL-01: Locale-Specific Recognizers
The Detection_Engine SHALL support locale-specific regex recognizers for 8 locales, including locale-specific national IDs (SSN, Steuer-ID, NIR, BSN, DNI, Codice Fiscale, GCC IDs, CPF/CNPJ), phone formats, and document identifiers.

#### REQ-LOCL-02: X-AnonReq-Locale Header
When a request includes `X-AnonReq-Locale` with a supported locale, the Detection_Engine SHALL activate that locale's recognizer bundle in addition to universal recognizers.

#### REQ-LOCL-03: Unsupported Locale Handling
If the locale header contains an unsupported or malformed code, the Detection_Engine SHALL return HTTP 400.

#### REQ-LOCL-04: Missing Locale Fallback
If no locale header is provided, universal recognizers only SHALL be applied, with a structured log entry indicating locale detection was skipped.

#### REQ-LOCL-05: Multi-Locale Merging
The Detection_Engine SHALL support up to 10 comma-separated locale codes, running all specified recognizers and merging results (higher confidence wins; on tie, earlier in list wins).

#### REQ-LOCL-06: Extensible Architecture
The Detection_Engine SHALL be extensible -- new locale recognizer bundles can be added by placing a configuration file in the recognizers directory without modifying source code.

#### REQ-LOCL-07: Checksum Validation
The Detection_Engine SHALL validate checksums before flagging: German Steuer-ID (modulo-11), Dutch BSN (modulo-11), French NIR (Luhn variant), Brazilian CPF (modulo-11), Brazilian CNPJ (modulo-11), Italian Codice Fiscale (official algorithm). Invalid checksums SHALL NOT be flagged.

### 5.8 Compliance Presets (MVP)

#### REQ-COMP-01: Named Presets
The Gateway SHALL provide named compliance presets for: GDPR, LGPD, PDPA, POPIA, Privacy Act (Australia), and PIPEDA. Each defines mandatory entity types, minimum confidence thresholds, and applicable locales.

#### REQ-COMP-02: Preset Enforcement at Startup
When a compliance preset is active, the Detection_Engine SHALL enforce the minimum entity type set. Configuration disabling a preset-mandated entity type SHALL be rejected at startup.

#### REQ-COMP-03: Preset in Audit Log
The Audit_Logger SHALL include `compliance_preset` (preset identifier or null) in every audit log entry.

#### REQ-COMP-04: Merged Presets
If multiple presets are active simultaneously, a merged preset SHALL be applied: union of all mandatory entity types, highest confidence threshold for each type.

#### REQ-COMP-05: GET /v1/compliance/presets
The Gateway SHALL expose `GET /v1/compliance/presets` returning each available preset with its identifier, mandatory types, thresholds, and locales.

### 5.9 Audit Logging (MVP)

#### REQ-AUDT-01: Structured JSON Log Entry
The Audit_Logger SHALL emit a structured JSON log entry to stdout for every completed request-response cycle, containing: `timestamp` (ISO 8601 UTC), `session_id` (UUID), `target_provider`, `target_model`, `entity_counts` (object, max 50 keys), `total_entities_detected`, `streaming` (boolean), `latency_ms` (object with `detection`, `tokenization`, `restoration`, `total_overhead`), `compliance_preset` (string or null), and `locale` (BCP 47 or null).

#### REQ-AUDT-02: No PII in Logs
The Audit_Logger SHALL NEVER include: raw prompt text, raw response text, token strings, original entity values, authentication credentials, or internal endpoint URLs.

#### REQ-AUDT-03: Fail-Secure Logging
If an exception occurs during audit log construction, the Audit_Logger SHALL discard the entry, preserve the HTTP response, and increment `anonreq_audit_log_failures_total`.

#### REQ-AUDT-04: Field Allowlist
The Gateway SHALL apply a structured-log field allowlist. Any log record containing a field not in the allowlist SHALL be silently stripped.

#### REQ-AUDT-05: Fail-Secure Event Logging
When a fail-secure event occurs, the Audit_Logger SHALL emit a structured entry with `failure_type` (one of `detection_error`, `cache_error`, `timeout`, `unknown`) and `http_status_returned`.

#### REQ-AUDT-06: Write-Before-Flush
The Audit_Logger SHALL write each entry to stdout before the HTTP response is flushed to the client.

### 5.10 Custom Rules and Exclusion Lists (MVP)

#### REQ-CFG-01: YAML Custom Recognizers
The Detection_Engine SHALL load custom pattern recognizers from a YAML configuration file at startup, with `name`, `entity_type`, `patterns` (list of regex), `context_words`, and `score` (0.0-1.0).

#### REQ-CFG-02: Custom Recognition Pipeline
Custom pattern matches SHALL be treated with the configured confidence score, subject to the same confidence threshold filtering as built-in recognizers.

#### REQ-CFG-03: Exclusion List Loading
The Detection_Engine SHALL load the Exclusion_List from a plain-text or YAML file.

#### REQ-CFG-04: Exact Match Suppression
Case-folded, NFKC-normalized exact matches between detected entity values and Exclusion_List entries SHALL be suppressed.

#### REQ-CFG-05: Wildcard Exclusion
The Exclusion_List SHALL support `*` as a suffix wildcard (e.g., `GraphAPI.*`).

#### REQ-CFG-06: Hot-Reload
When the custom recognizer or exclusion list file is modified on disk, the Detection_Engine SHALL perform an atomic configuration swap within 60 seconds without process restart.

#### REQ-CFG-07: Invalid Pattern Rejection
If a custom recognizer pattern contains an invalid regex, the Detection_Engine SHALL reject the configuration at startup and SHALL NOT start serving traffic with a partially loaded recognizer set.

#### REQ-CFG-08: GET /v1/config/rules
The Gateway SHALL expose `GET /v1/config/rules` (authenticated) returning active custom recognizer names, entity types, and exclusion list entry count.

### 5.11 Docker Compose Deployment (MVP)

#### REQ-DEP-01: Docker Compose Services
The Gateway SHALL ship a `docker-compose.yml` defining `anonreq`, `presidio`, and `valkey` services on an internal Docker network. No host port exposure by default.

#### REQ-DEP-02: Startup Time
`GET /health` SHALL return HTTP 200 within 60 seconds of `docker compose up` on a system with 4-core CPU, 8 GB RAM, Docker Engine 24+.

#### REQ-DEP-03: Multi-Stage Dockerfile
The Gateway SHALL implement a multi-stage Dockerfile with Python 3.12-slim base. Final stage image size SHALL NOT exceed 2 GB.

#### REQ-DEP-04: Valkey Persistence Disabled
Valkey SHALL be configured with `save ""` and bound to the internal Docker network only.

#### REQ-DEP-05: Service Health Dependencies
The anonreq service SHALL declare `depends_on` with `condition: service_healthy` for both presidio and valkey, with explicit `healthcheck` stanzas.

#### REQ-DEP-06: Environment Variable Configuration
All configurable parameters SHALL be injectable via environment variables with documented defaults. No sensitive values hardcoded in `docker-compose.yml`.

#### REQ-DEP-07: .env.example
The Gateway SHALL ship a `.env.example` documenting every supported environment variable with type, default, and description.

#### REQ-DEP-08: Missing Required Variable Handling
If a required environment variable (one with no default) is absent at startup, the Gateway SHALL exit with non-zero status and logged error identifying the missing variable.

### 5.12 Response-Side Token Verification (MVP)

#### REQ-VRFY-01: Post-Restoration Scan (Non-Streaming)
After restoration of a non-streaming response, the Restoration_Engine SHALL scan using the pattern `\[[A-Z]+_\d+\]` before delivering to the caller.

#### REQ-VRFY-02: Residual Token Warning
If unreplaced Tokens are found, the Restoration_Engine SHALL log a structured warning with `session_id` and count, increment `anonreq_tokens_unrestored_total`, and deliver the response as-is.

#### REQ-VRFY-03: Post-Stream Scan
When a streaming response reaches terminal event, the Restoration_Engine SHALL perform a post-stream verification scan on the full assembled text and log a warning if unreplaced Tokens are found.

#### REQ-VRFY-04: Prometheus Metrics
The Gateway SHALL expose `GET /metrics` with at minimum: `anonreq_requests_total`, `anonreq_detection_latency_seconds` (histogram), `anonreq_entities_detected_total`, `anonreq_tokens_unrestored_total`, `anonreq_fail_secure_events_total`, `anonreq_audit_log_failures_total`.

#### REQ-VRFY-05: Scan Error Handling
If the post-stream verification scan encounters an exception, the Restoration_Engine SHALL log a structured error and SHALL NOT surface the exception to the caller.

### 5.13 Rate Limiting and Spend Controls (Enterprise)

#### REQ-RATE-01: Per-Tenant Rate Limits
The Gateway SHALL enforce per-tenant limits on three axes: RPM, TPM, and maximum concurrent in-flight requests.

#### REQ-RATE-02: RPM/TPM Exceeded
When RPM or TPM limit is exceeded, HTTP 429 with `Retry-After` header SHALL be returned.

#### REQ-RATE-03: Concurrent Limit Exceeded
When concurrent request limit is exceeded, HTTP 429 with `reason: concurrent_limit_exceeded`.

#### REQ-RATE-04: Per-Tenant Spend Controls
The Gateway SHALL support per-tenant daily and monthly spend budgets in USD or configured currency.

#### REQ-RATE-05: Budget Exceeded
When spend would exceed budget, HTTP 402 with structured error body containing `budget_type`, `current_spend`, `budget_limit`, and `currency`.

#### REQ-RATE-06: Budget Reset
Daily counters reset at 00:00 UTC; monthly at 00:00 UTC on 1st. Budget resets emit `budget_reset` audit events.

#### REQ-RATE-07: Usage Query
`GET /v1/admin/tenants/{tenant_id}/usage` (operator/administrator role) returns current RPM, TPM, concurrent count, daily and monthly spend.

#### REQ-RATE-08: Fail Closed on Cache Miss
If rate-limit or spend state cannot be read from cache, return HTTP 503 (fail closed).

### 5.14 Multimodal Document Anonymization (Enterprise)

#### REQ-MULTI-01: Content Type Coverage
The Detection_Engine SHALL apply the full pipeline to: tool call arguments, tool call results, JSON documents (recursively scan string-valued leaf nodes), and multimodal request metadata (image descriptions, file names).

#### REQ-MULTI-02: JSON Structural Validity
Anonymized JSON SHALL remain parseable by a standard JSON parser with all non-entity content unchanged.

#### REQ-MULTI-03: Unsupported Content Type
If a request contains an unsupported content type, HTTP 415 SHALL be returned.

#### REQ-MULTI-04: Restoration Across Content Types
The Restoration_Engine SHALL restore Tokens within all anonymized content types using the same Mapping.

#### REQ-MULTI-05: Property-Based Test
Test suite SHALL include a property-based test confirming byte-for-byte identity after anonymize-restore for well-formed JSON documents containing at least one detectable entity.

### 5.15 AI Security Firewall (Enterprise)

#### REQ-FW-01: Prompt Injection Detection
The Gateway SHALL inspect every inbound prompt for direct injection, indirect injection, and role-confusion attacks at configurable threshold (default 0.85).

#### REQ-FW-02: Injection Blocking
When injection is detected with confidence >= threshold, block with HTTP 400 and `reason: prompt_injection_detected`.

#### REQ-FW-03: Jailbreak Detection
Jailbreak attempt patterns detected via configurable YAML rule set with actions: `block` (HTTP 400), `flag_and_forward`, or `monitor`.

#### REQ-FW-04: Output Policy Inspection
The Gateway SHALL inspect outbound responses for policy-violating content. On violation, suppress with HTTP 451 and `reason: output_policy_violation`.

#### REQ-FW-05: Audit Logging
All prompt security enforcement actions SHALL be logged with `event_type`, `session_id`, `tenant_id`, `confidence_score`, and `rule_id` (no raw content).

#### REQ-FW-06: Prometheus Counter
`anonreq_prompt_security_events_total` labeled by `event_type` and `tenant_id`.

#### REQ-FW-07: Rules Query
`GET /v1/admin/prompt-security/rules` listing active rules with `rule_id`, `category`, `action`, and `enabled`.

#### REQ-FW-08: Atomic Hot-Reload
Rule set hot-reload within 60 seconds without restart.

### 5.16 Data Classification and Handling Policies (Enterprise)

#### REQ-CLASS-01: Five Classification Levels
The Gateway SHALL support `Public`, `Internal`, `Confidential`, `Restricted`, `Highly Restricted`.

#### REQ-CLASS-02: Auto-Classification
Detection_Engine SHALL assign Classification_Level based on highest-sensitivity detected entity type. Undetected defaults to `Internal`.

#### REQ-CLASS-03: Client Assertion Override
Clients MAY supply `X-AnonReq-Classification` header. Higher of client vs detected wins. Overrides logged.

#### REQ-CLASS-04: Per-Level Handling Policies
Per-level policies: `allow_and_anonymize` (<= Confidential), `anonymize_and_flag` (Restricted), `block` (Highly Restricted). Block returns HTTP 451.

#### REQ-CLASS-05: Audit Field
Classification_Level in every audit log entry.

### 5.17 AI Governance Framework (Enterprise)

#### REQ-GOV-01: Governance Records
The Gateway SHALL maintain structured governance records per tenant with named owners (governance, risk, compliance, security). Set during provisioning, updatable only by administrators.

#### REQ-GOV-02: Governance Approval
Config changes affecting compliance presets, mandatory entity types, or provider routing require governance approval entries.

#### REQ-GOV-03: Governance Status Endpoint
`GET /v1/governance/status` returns per-tenant owner assignments, last/next review dates, pending approval count.

#### REQ-GOV-04: Review Cycle Enforcement
Configurable governance review cycle (default 90 days). Overdue reviews emit `governance_review_overdue` events.

#### REQ-GOV-05: Append-Only Governance Log
Governance approval entries in a dedicated append-only log, retained for minimum 7 years.

#### REQ-GOV-06: Governance Export
`GET /v1/admin/governance/export` returns governance records as JSON Lines.

### 5.18 Financial Services Compliance (Enterprise)

#### REQ-FIN-01: Compliance Mapping Document
Ship `docs/compliance/financial-services-mapping.md` mapping controls to DORA, NIS2, GDPR, ISO 27001, ISO 42001, EBA, FCA, SEC, FINRA.

#### REQ-FIN-02: MNPI Recognizer Bundle
Support MNPI detection: ticker symbols, deal code names, transaction identifiers, acquisition target names, investment thesis code words.

#### REQ-FIN-03: MNPI Handling Policies
Four configurable policies: `anonymize_and_forward`, `anonymize_flag_and_forward`, `block`, `quarantine`.

#### REQ-FIN-04: Model Risk Management
Model inventory with risk classification, approval status, review cycles. Approval gating blocks unapproved models.

#### REQ-FIN-05: Financial Crime Controls
Financial crime recognizer bundle, context-word confidence boosting (+0.15 within 50 chars), AML webhook integration.

#### REQ-FIN-06: DORA Resilience
Critical service classification, resilience testing procedures, ICT third-party register export.

### 5.19 Universal AI Traffic Gateway (Appliance)

#### REQ-APPL-01: Inline Inspection
Support inline inspection of: text prompt interfaces, voice bots, meeting assistant transcripts, agent frameworks, MCP clients, RAG flows, tool calls, email AI, CRM AI, note-taking AI.

#### REQ-APPL-02: Deployment Topologies
Reverse proxy, transparent proxy (TLS interception with tenant-managed CA cert), virtual appliance, physical appliance.

#### REQ-APPL-03: TLS Interception
Transparent proxy SHALL perform TLS interception with tenant-managed CA certificate and TLS re-origination.

#### REQ-APPL-04: Block Unintercepted AI
Configurable `block-all-unintercepted-AI` policy for traffic that cannot be intercepted (e.g., certificate pinning).

#### REQ-APPL-05: Proxy-Only Overhead
P95 inline processing overhead <= 5ms for proxy-only mode (policy evaluation, no detection pipeline).

### 5.20 Agent and Tool Call Governance (Appliance)

#### REQ-AGENT-01: MCP Protocol Inspection
Inspect MCP protocol traffic and OpenAI/Anthropic tool call/result payloads.

#### REQ-AGENT-02: Per-Tool Permission Policies
Per-tool policies: `allow`, `allow_with_audit`, `require_human_approval`, `block`.

#### REQ-AGENT-03: Tool Parameter Anonymization
Tool call parameters anonymized for external API targets; tool results inspected for sensitive data.

#### REQ-AGENT-04: Human Approval Suspension
Agent execution suspended for tools requiring human approval; routed through oversight queue.

### 5.21 SIEM and SOC Integration (Appliance)

#### REQ-SIEM-01: Structured Security Events
Generate events for: firewall violations, DLP actions, shadow AI detection, MNPI detection, prompt security events.

#### REQ-SIEM-02: SIEM Platform Sinks
Support Splunk (HEC), IBM QRadar (syslog CEF), Microsoft Sentinel (DCR API), Elastic (Bulk API), Datadog (Logs API).

#### REQ-SIEM-03: MITRE Mapping
Every forwarded event includes `mitre_technique_id` mapped to MITRE ATT&CK or ATLAS.

#### REQ-SIEM-04: Event Structure
Events include: `severity`, `event_type`, `tenant_id`, `session_id`, `timestamp`, `gateway_version`, `appliance_instance_id`. No raw prompt content.

#### REQ-SIEM-05: Sink Health
`GET /v1/admin/soc/integration/status` returns health status of each configured SIEM sink.

#### REQ-SIEM-06: Local Buffering
If SIEM sink unreachable, buffer up to 10,000 events in-memory with exponential backoff retry. On overflow, discard oldest (never block processing).

### 5.22 Network Discovery and CASB (Appliance)

#### REQ-DISC-01: AI Traffic Identification
Identify AI API traffic to 8+ providers by hostname/IP.

#### REQ-DISC-02: Shadow AI Detection
Detect shadow AI traffic via network flow/DNS analysis, emit `shadow_ai_detected` event.

#### REQ-DISC-03: AI Asset Inventory
Maintain inventory: `service_name`, `first_seen`, `last_seen`, `request_count`, `sanctioned`, `policy_status`.

#### REQ-CASB-01: AI SaaS Classification
Classify AI applications as sanctioned / tolerated / unsanctioned with per-app policies.

#### REQ-CASB-02: Per-App Policies
Policy entries define application, risk score (0-100), allowed user groups, enforcement action (allow/alert/block).

### 5.23 Secure RAG Pipeline Protection (Appliance)

#### REQ-RAG-01: Retrieval Injection Point Inspection
Intercept RAG pipeline traffic at retrieval injection point. Apply full detection pipeline to retrieved content.

#### REQ-RAG-02: Vector DB Integration
Support integration with Pinecone, Weaviate, Chroma, pgvector, and file-system document repositories.

#### REQ-RAG-03: RAG Restoration
Restore Tokens in RAG-anonymized content within LLM response so original values are returned inside the enterprise perimeter.

### 5.24 Governance, Bias, and Compliance Reporting (Enterprise)

#### REQ-GOVBIAS-01: Fairness Testing Datasets
Maintain fairness testing datasets per locale (200+ labeled examples per demographic group). CI/CD bias assessment on every release: recall disparity across groups <= 0.05.

#### REQ-GOVBIAS-02: Third-Party Supplier Governance
Provider inventory with contract/risk/review status. Provider review cycle (default 365 days).

#### REQ-GOVBIAS-03: Post-Deployment Monitoring
Collect detection quality drift, fail-secure frequency, SLO compliance. Incident classification (S1/S2/S3).

#### REQ-GOVBIAS-04: Data Lineage
Immutable Lineage_Records per session with HMAC-SHA256 integrity tags. No API to modify or delete.

#### REQ-GOVBIAS-05: Record Retention
Configurable retention policies per record type. Legal_Hold support suspends deletion.

#### REQ-GOVBIAS-06: Executive Reporting
Executive governance reports via `GET /v1/admin/reports/executive` with regulatory posture summary, provider exposure summary.

---

## 6. Non-Functional Requirements

### 6.1 Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-PERF-01 | Detection overhead (P95) | <= 100ms for prompts <= 1,000 words |
| NFR-PERF-02 | Proxy-only mode overhead (P95) | <= 5ms (no detection pipeline) |
| NFR-PERF-03 | Post-response cache cleanup | Within 100ms of response write |
| NFR-PERF-04 | Stream TTL extension trigger | At 80% of configured TTL |
| NFR-PERF-05 | Tail_Buffer maximum size | 512 characters |
| NFR-PERF-06 | Audio stream processing latency (P99) | <= 150ms |
| NFR-PERF-07 | AI Firewall evaluation budget | <= 20ms per request |

### 6.2 Fail-Secure Guarantees

| ID | Requirement |
|----|-------------|
| NFR-FAIL-01 | Any error -> HTTP 5xx, never forward unsanitized data |
| NFR-FAIL-02 | Detection engine failure -> HTTP 500, zero forward |
| NFR-FAIL-03 | Cache manager failure -> HTTP 500, zero forward |
| NFR-FAIL-04 | Detection timeout -> HTTP 504, zero forward |
| NFR-FAIL-05 | Provider translation failure -> HTTP 500, zero forward |
| NFR-FAIL-06 | Rate-limit/spend cache miss -> HTTP 503, zero forward |
| NFR-FAIL-07 | Startup pre-flight: refuse to bind until all components healthy |
| NFR-FAIL-08 | Exit on missing required env vars |

### 6.3 No-PII-in-Logs

| ID | Requirement |
|----|-------------|
| NFR-LOG-01 | No raw prompt text, response text, token strings, entity values, credentials, or internal URLs in any log |
| NFR-LOG-02 | Structured-log field allowlist enforced; non-allowlisted fields stripped |
| NFR-LOG-03 | Audit log written before response flush |
| NFR-LOG-04 | Fail-secure event logs contain metadata only |

### 6.4 Ephemeral Cache

| ID | Requirement |
|----|-------------|
| NFR-CACHE-01 | Persistence disabled (save "", no AOF, no RDB) |
| NFR-CACHE-02 | TTL range [60, 3600] seconds, default 300 |
| NFR-CACHE-03 | DEL on all terminal states (response written, stream [DONE], connection close) |
| NFR-CACHE-04 | TTL-based eviction as fallback |
| NFR-CACHE-05 | maxmemory 256 MB, allkeys-lru eviction |
| NFR-CACHE-06 | Monitoring commands (MONITOR, SLOWLOG, keyspace notifications) disabled |

### 6.5 Streaming

| ID | Requirement |
|----|-------------|
| NFR-STREAM-01 | No full-response buffering before forwarding |
| NFR-STREAM-02 | Mapping pre-fetched via single HGETALL at stream start |
| NFR-STREAM-03 | Tail_Buffer for split tokens across chunk boundaries |
| NFR-STREAM-04 | Case-insensitive + bracket-optional token matching |
| NFR-STREAM-05 | Anti-buffering headers on all streaming responses |
| NFR-STREAM-06 | Client disconnect: cancel upstream, delete mapping, log event |

### 6.6 Tenant Isolation

| ID | Requirement |
|----|-------------|
| NFR-TENANT-01 | Cache keys namespaced by tenant: `anonreq:{tenant_id}:{session_id}` |
| NFR-TENANT-02 | Audit logs, metrics, and governance records tenant-scoped |
| NFR-TENANT-03 | Tenant A cannot read or infer Tenant B mappings, metrics, config, audit records, or evidence |
| NFR-TENANT-04 | Business unit segregation via X-AnonReq-BU header with Chinese Wall enforcement |
| NFR-TENANT-05 | Per-tenant compliance presets, rate limits, spend budgets, and handling policies |

### 6.7 Availability and Durability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-AVAIL-01 | Request success rate (1-hour window) | >= 99.9% |
| NFR-AVAIL-02 | Audit log write success rate (24-hour window) | >= 99.99% |
| NFR-AVAIL-03 | Fail-secure event rate (24-hour window) | <= 0.1% |
| NFR-AVAIL-04 | Governance/audit/lineage record retention | 7 years minimum |
| NFR-AVAIL-05 | Legal Hold overrides retention schedule |
| NFR-AVAIL-06 | Config change audit trail: append-only, immutable |

### 6.8 Security

| ID | Requirement |
|----|-------------|
| NFR-SEC-01 | All admin endpoints require authentication and RBAC |
| NFR-SEC-02 | API keys: minimum 256-bit entropy, CSPRNG-generated |
| NFR-SEC-03 | TLS 1.3 for all external communications |
| NFR-SEC-04 | Provider API keys injected at network boundary, never stored in application code |
| NFR-SEC-05 | SBOM per release, container image SBOM, Dependabot weekly scans |
| NFR-SEC-06 | Responsible disclosure process defined in SECURITY.md |
| NFR-SEC-07 | Hot-reload configuration: atomic swap, no partial load window |
| NFR-SEC-08 | Lineage_Records protected by HMAC-SHA256 integrity tags |

---

## 7. Use Cases

### Use Case 1: Non-Streaming LLM Request Anonymization (MVP)

**Actor:** Enterprise developer integrating an LLM-powered feature
**Preconditions:** Gateway deployed and healthy; Detection_Engine, Cache_Manager responsive; provider API key configured for target model
**Trigger:** Client application sends `POST /v1/chat/completions` with `stream: false` to the Gateway

**Flow:**
1. Gateway authenticates request (bearer token validation)
2. Gateway validates payload against OpenAI-compatible schema; returns HTTP 400 if invalid
3. Gateway resolves tenant context from `X-AnonReq-Tenant-ID` header (or default tenant)
4. Classification engine evaluates payload against BLOCK / ROUTE_LOCAL rules (Stage 2+: classification policy)
5. Detection_Engine scans all message content across all roles using regex tier (built-in + custom) and NER tier (Presidio), applying active locale bundles, exclusion list, and confidence thresholds
6. Tokenization_Engine receives detected entities, creates `[TYPE_N]` tokens with deduplication and reverse-offset replacement
7. Tokenization_Engine writes Mapping to Cache_Manager (`anonreq:{tenant_id}:{session_id}`) with configured TTL
8. Provider_Adapter translates sanitized payload to target provider's schema (OpenAI passthrough, Anthropic/Gemini/Ollama translated)
9. ForwardingGuard verifies SanitizedEnvelope; forwards sanitized request to upstream provider
10. Provider returns response; Restoration_Engine replaces all Tokens with original values from Mapping
11. Post-restoration scan verifies no residual Tokens
12. Response delivered to caller; async DEL issued for Mapping
13. Audit_Logger writes metadata-only entry to stdout
14. Prometheus counters updated

**Postconditions:** Client receives fully restored response; Mapping deleted or TTL-bound; no raw PII transmitted externally

**Alternate Flows:**
- Detection error -> HTTP 500, zero forward (fail-secure)
- Cache write failure -> HTTP 500, zero forward
- Provider translation error -> HTTP 500, zero forward
- No entities detected -> passthrough without Mapping creation
- Block rule matched (Stage 2+) -> HTTP 403 / 451

### Use Case 2: SSE Streaming Request with Token Restoration (MVP)

**Actor:** Developer using streaming chat interface
**Preconditions:** Same as Use Case 1
**Trigger:** Client sends `POST /v1/chat/completions` with `stream: true`

**Flow:**
1-8: Same as Use Case 1 (anonymization, tokenization, mapping write, provider translation)
9. Gateway initiates streaming connection to upstream provider
10. Restoration_Engine pre-fetches complete Mapping via `HGETALL` (single network round-trip)
11. Gateway forwards each SSE chunk from provider to client through Tail_Buffer FSM:
    a. Chunk appended to Tail_Buffer
    b. Tail_Buffer scanned for Token patterns (case-insensitive, bracket-optional)
    c. Completed Token matches replaced with original values from local Mapping copy
    d. Flushed content sent to client with anti-buffering headers
12. On `[DONE]` or connection close: Tail_Buffer flushed, async DEL issued
13. Post-stream verification scan on assembled text
14. Audit log entry written; metrics updated

**Postconditions:** Client receives fully restored streaming response; no per-chunk cache round-trips

### Use Case 3: Multi-Provider Routing via Model Alias (MVP)

**Actor:** Developer configuring provider strategy
**Preconditions:** Provider adapters configured; model aliases defined in configuration
**Trigger:** Client sends request with `model: "claude-sonnet"` (configured alias)

**Flow:**
1. Gateway resolves `model` field against configured aliases
2. Matches `claude-sonnet` -> routes to Anthropic Claude with model identifier `claude-3-5-sonnet-20241022`
3. Provider_Adapter selects Anthropic translator
4. Detection and tokenization proceed as Use Case 1
5. Sanitized payload translated to Anthropic Messages API format
6. Response received, restored, delivered to caller

**Postconditions:** Client called OpenAI-compatible API; request routed to Anthropic; response restored

### Use Case 4: Multi-Locale Detection with Compliance Preset (MVP)

**Actor:** Compliance officer at German financial institution
**Preconditions:** `gdpr` compliance preset active; `de-DE` locale bundle installed
**Trigger:** Request with `X-AnonReq-Locale: de-DE` containing German PII

**Flow:**
1. Detection_Engine activates German locale recognizers (Steuer-ID modulo-11 checksum, Personalausweis, German IBAN, German phone)
2. GDPR preset enforces minimum entity types; startup config validated
3. German-specific entities detected with checksum validation
4. Entities tokenized; audit entry includes `compliance_preset: gdpr`, `locale: de-DE`
5. Forwarding and restoration proceed normally

**Postconditions:** German PII detected and tokenized; GDPR compliance maintained

### Use Case 5: MNPI Detection and Blocking (Enterprise)

**Actor:** Hedge fund compliance officer
**Preconditions:** MNPI recognizer bundle active; `mnpi.block_on_detection: true` for tenant
**Trigger:** Request containing a ticker symbol matching a restricted list entry

**Flow:**
1. Detection_Engine identifies ticker symbol via MNPI pattern
2. Entity value matched against tenant's restricted-names list
3. Entity classified as MNPI type; session Classification_Level set to Restricted
4. MNPI handling policy configured as `block`; Gateway returns HTTP 451
5. Audit entry: `event_type: mnpi_detected`, no raw value
6. Prometheus counter incremented

**Postconditions:** Request blocked; MNPI never left the perimeter; compliance team notified

### Use Case 6: Prompt Injection Detection and Blocking (Enterprise)

**Actor:** SOC analyst monitoring AI security events
**Preconditions:** AI Firewall rules active
**Trigger:** Malicious end user sends jailbreak attempt to corporate chatbot

**Flow:**
1. AI Firewall layer inspects inbound prompt before detection pipeline
2. Structural analysis matches known jailbreak pattern at confidence >= threshold
3. Action configured as `block`; Gateway returns HTTP 400 with `reason: prompt_injection_detected`
4. High-severity security event emitted to SIEM via configured sink
5. Audit entry: `event_type: prompt_injection_blocked`, confidence score, rule ID
6. Prometheus counter `anonreq_prompt_security_events_total` incremented

**Postconditions:** Malicious prompt blocked; no provider spend incurred; SOC alerted

### Use Case 7: Transparent Proxy AI Traffic Interception (Appliance)

**Actor:** Enterprise architect deploying network-level protection
**Preconditions:** Appliance deployed in transparent proxy mode; tenant-managed CA cert installed; network routing rules active
**Trigger:** Desktop application makes HTTPS call to `api.openai.com`

**Flow:**
1. Network routing (iptables/eBPF/DNS) redirects outbound traffic to Appliance
2. Appliance performs TLS interception using tenant-managed CA certificate
3. TLS session re-originated to upstream `api.openai.com`
4. Request body inspected; parsed against supported AI API schemas
5. Standard detection/tokenization/forwarding pipeline executed
6. Response restored; sent back to client application over intercepted TLS session

**Postconditions:** Application received fully restored response; no code changes needed; all AI traffic governed

### Use Case 8: Agent Tool Call Governance (Appliance)

**Actor:** AI governance officer monitoring autonomous agents
**Preconditions:** Appliance deployed in agent governance mode; MCP protocol inspection active
**Trigger:** Autonomous agent generates a tool call to `execute_sql_query`

**Flow:**
1. Appliance intercepts tool call payload in agent-LLM communication
2. Tool permission policy evaluated: `execute_sql_query` requires human approval
3. Tool call parameters scanned for injection attempts
4. Agent execution suspended; tool invocation routed to human oversight queue
5. Security officer reviews via `GET /v1/oversight/pending` (metadata only)
6. Officer approves or rejects via `POST /v1/oversight/{request_id}/approve` or `/reject`
7. On approval: tool executes; tool result scanned for sensitive data before returning to LLM
8. On rejection: agent receives error; audit entry logged

**Postconditions:** Agent actions governed per-tool; sensitive database queries require human approval; full audit trail

### Use Case 9: Voice Stream Sanitization (Appliance)

**Actor:** Compliance officer at financial institution using AI meeting assistant
**Preconditions:** Voice/meeting channel configured; local STT engine deployed
**Trigger:** Meeting participant mentions a client account number during virtual meeting

**Flow:**
1. Meeting assistant audio stream intercepted via SIP/WebRTC integration
2. Audio chunks routed to local STT engine for real-time transcription
3. Sliding-window text buffer scanned by Detection_Engine
4. Account number detected; Token generated with audio timeline timestamp
5. Outbound text payload to AI provider: token replaces account number
6. AI response received; token restored before text-to-speech synthesis
7. Raw audio never transmitted externally (per `voice.block_external_audio: true`)

**Postconditions:** Verbal PII protected; meeting assistant receives sanitized transcript; audio stays on-premises

---

## 8. Out of Scope

The following capabilities are explicitly deferred from the current product scope:

### Stage 1 (MVP) Deferred

| Item | Rationale | Future Stage |
|------|-----------|--------------|
| Enterprise authentication (OAuth/JWT/mTLS, RBAC, OIDC/SAML) | Static bearer token sufficient for MVP; full auth adds architectural complexity | Stage 2 |
| Secrets management (HashiCorp Vault, AWS/Azure/GCP secret stores, mTLS between components) | Environment variables sufficient for MVP deployment | Stage 2 |
| Multi-tenant isolation (tenant namespacing, per-tenant config, provisioning API) | MVP assumes single-tenant deployment with hardcoded defaults | Stage 2 |
| High availability (Valkey Sentinel/Cluster, Kubernetes Helm chart, HA deployment) | Docker Compose single-instance sufficient for MVP pilots | Stage 2 |
| Data sovereignty / geographic routing | MVP operates as single-instance; geographic routing requires multi-region deployment | Stage 2 |

### Stage 2 (Enterprise) Deferred

| Item | Rationale | Future Stage |
|------|-----------|--------------|
| Admin Portal UI | API-only admin interface for Stage 2; GUI deferred to reduce frontend complexity | Stage 3 |
| Advanced semantic DLP models | Rule-based + regex DLP sufficient for initial enterprise deployments | Stage 3 |
| Hardware HSM integration | Software-based key management sufficient; HSM integration adds hardware dependency | Post-GA |
| Customer-managed evidence storage | Gateway-managed evidence storage sufficient; customer-managed option adds complexity | Post-GA |
| Additional locales beyond 8 | 8 locales cover target markets; expansion deferred based on customer demand | Post-GA |
| Additional SIEM sinks beyond 5 | 5 sinks cover major SIEM platforms; others deferred based on demand | Post-GA |
| Managed control-plane federation | Multi-gateway management requires federation protocol design | Post-GA |

### Stage 3 (Appliance) Deferred

| Item | Rationale |
|------|-----------|
| Physical appliance hardware | Virtual appliance sufficient for enterprise pilots; physical hardware requires manufacturing partnership |
| Desktop endpoint agents (Windows/macOS) | Requires native development in C++/Swift; virtual appliance proxy mode covers most use cases initially |
| Sovereign AI control plane with GPU inference | Depends on Stage 3+ network topology; requires vLLM/Ollama integration maturity |

### Always Out of Scope

| Item | Rationale |
|------|-----------|
| LLM model training or fine-tuning | AnonReq is a proxy/gateway, not a model provider |
| Data storage or data warehousing | All data ephemeral; no data written to disk by design |
| Client-side agents or browser extensions | Enterprise deployment requires infrastructure-layer enforcement, not endpoint agents (except Stage 3 desktop agents) |
| Managed cloud/SaaS offering | Product is self-hosted by design; managed offering would conflict with core value proposition |
| LLM output content filtering for non-PII policy (toxicity, hate speech, etc.) | AnonReq focuses on PII/PHI/MNPI/PCI data protection, not general content moderation |

---

## 9. Success Metrics

### 9.1 Product Adoption Metrics

| Metric | MVP Target | Enterprise Target |
|--------|------------|-------------------|
| Active deployments | 10 pilot customers | 100+ enterprise customers |
| Requests processed/day | 100,000 | 10,000,000 |
| PII tokens generated/day | 500,000 | 50,000,000 |
| Supported providers | 4 (OpenAI, Anthropic, Gemini, Ollama) | 8+ including Azure, AWS Bedrock, Mistral |
| Supported locales | 8 | 16+ |
| Docker pulls | 1,000/month | 50,000/month |
| GitHub stars | 500 | 5,000 |

### 9.2 Security and Correctness Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Round-trip correctness | 100% of property tests pass | CI/CD gate per release |
| Fail-secure events | <= 0.1% of requests (24hr window) | `anonreq_fail_secure_events_total` / `anonreq_requests_total` |
| Residual tokens in responses | 0 | Post-restoration scan |
| PII in logs | 0 occurrences | Automated log scanning in CI |
| Cross-request token collision | P(duplicate) >= 1 - 2^(-32) | Property test with 1,000+ session pairs |
| Tenant isolation violations | 0 | Simultaneous tenant load test |
| CVSS 9.0+ vulnerabilities | 0 open | Dependabot + weekly scan |

### 9.3 Performance Metrics

| Metric | MVP Target | Enterprise Target | Appliance Target |
|--------|------------|-------------------|------------------|
| P95 detection overhead (<= 1,000 words) | <= 100ms | <= 80ms | <= 50ms |
| P95 proxy-only overhead | N/A | N/A | <= 5ms |
| P99 audio latency | N/A | N/A | <= 150ms |
| AI Firewall evaluation budget | N/A | <= 20ms | <= 10ms |
| Cache DEL latency (post-response) | <= 100ms | <= 50ms | <= 50ms |
| Startup time (docker compose up) | <= 60s | <= 30s | <= 30s |
| Concurrent streaming sessions | 50 | 500 | 5,000 |

### 9.4 SLO Targets

| SLO | Target | Window |
|-----|--------|--------|
| Request success rate | >= 99.9% | 1 hour |
| P95 processing overhead | <= 100ms | 1 hour (prompts <= 1,000 words) |
| Fail-secure event rate | <= 0.1% | 24 hours |
| Audit log write success | >= 99.99% | 24 hours |

### 9.5 Business Metrics

| Metric | Target |
|--------|--------|
| Time to first successful anonymization (developer) | < 5 minutes |
| Time to Docker Compose deployment | < 30 minutes |
| Time to Kubernetes Helm deployment | < 60 minutes |
| Downstream application code changes required | 0 (change base_url only) |
| False positive rate (out-of-the-box config) | < 5% on standard PII types |
| False negative rate (out-of-the-box config) | < 1% on mandatory entity types per active compliance preset |

### 9.6 Security Acceptance Gates

| Gate | Criteria |
|------|----------|
| Zero provider forwards on fail-secure scenarios | All fail-secure property tests pass |
| No raw sensitive values in logs/UI/exports | Automated PII-in-log scanning passes |
| Tenant isolation under concurrent load | Simultaneous request test from two tenants produces zero cross-tenant data |
| Required audit events emitted | All audit event types verified present in integration tests |
| Metrics exposed | All required Prometheus metrics present in `/metrics` endpoint |
| All admin endpoints covered by authz matrix tests | Role-permission matrix verified per endpoint |

---

## 10. Release Criteria

### 10.1 MVP Release Gate (Stage 1 Complete)

**Definition:** Gateway is deployable, functional, and verifiable by enterprise developers and security teams.

| Category | Criteria |
|----------|----------|
| **Core Pipeline** | POST /v1/chat/completions works for non-streaming requests; detection across all message roles; tokenization with deduplication and reverse-offset; restoration in responses. |
| **Fail-Secure** | Detection error -> HTTP 500; cache error -> HTTP 500; timeout -> HTTP 504; startup pre-flight blocks unhealthy gateway; health endpoint. |
| **Streaming** | SSE streaming with Tail_Buffer; case-insensitive + bracket-optional matching; anti-buffering headers; client disconnect handling. |
| **Multi-Provider** | OpenAI, Anthropic, Gemini, Ollama support via model aliases; GET /v1/models; provider error forwarding without data leak. |
| **Multi-Locale** | 8 locale bundles active; checksum validation; multi-locale merging; unsupported locale -> HTTP 400. |
| **Compliance Presets** | 6 presets available; startup validation; merged presets; GET /v1/compliance/presets. |
| **Audit** | Metadata-only JSON logs to stdout; field allowlist; fail-secure event logging; write-before-flush. |
| **Custom Rules** | YAML custom recognizers; exclusion list with wildcards; hot-reload; GET /v1/config/rules. |
| **Deployment** | Docker Compose with health dependencies; multi-stage Dockerfile; .env.example; missing env var -> exit. |
| **Metrics** | GET /metrics with all required counters and histograms. |
| **Token Verification** | Post-restoration scan; residual token detection and logging. |
| **Property Tests** | Round-trip correctness; token uniqueness; deduplication; fail-secure; no-PII-in-logs; streaming round-trip; cross-request randomization; locale checksum validation. |
| **Documentation** | README with 13 sections; docs/en/ quickstart; SDK examples (Python, TypeScript, Go, curl); Apache 2.0 LICENSE; NOTICE; SECURITY.md; CHANGELOG.md. |

### 10.2 Enterprise Release Gate (Stage 2 Complete)

**Definition:** Product is deployable in regulated enterprise environments with governance, compliance, and operational requirements.

All MVP criteria plus:

| Category | Criteria |
|----------|----------|
| **Rate Limiting** | Per-tenant RPM/TPM/concurrent limits; daily/monthly spend budgets; HTTP 429/402; usage API. |
| **Multimodal** | Tool call arguments, JSON documents, multimodal metadata anonymized; HTTP 415 for unsupported types; property test. |
| **AI Firewall** | Prompt injection detection; jailbreak detection; output policy enforcement; rules API; hot-reload. |
| **Observability** | SLO tracking; governance status endpoint; SLO breach alerting webhook; config change audit trail. |
| **Supply Chain** | CycloneDX SBOM per release; container SBOM; OCI attestation; Dependabot weekly scans. |
| **Governance** | Governance records per tenant; governance review cycle; risk assessments; lifecycle management. |
| **Fairness** | Bias testing datasets per locale; CI/CD bias assessment (recall disparity <= 0.05). |
| **Classification** | 5 classification levels; auto-classification; client assertion override; per-level handling policies. |
| **Data Lineage** | Immutable Lineage_Records with HMAC integrity; lineage API; 7-year retention. |
| **Record Retention** | Configurable retention policies; Legal Hold; self-protecting hold records. |
| **Business Unit Segregation** | X-AnonReq-BU header; Chinese Wall enforcement; per-BU allowed models. |
| **Financial Services** | Compliance mapping document; MNPI protection; model risk management; financial crime controls; DORA resilience. |
| **Executive Reporting** | Monthly/quarterly governance reports; regulatory posture summary; provider exposure summary. |
| **Property Tests** | All MVP tests pass; additional tests for multimodal, rate limiting, classification, MNPI. |
| **Security Acceptance** | All security gates pass; vulnerability scan; SBOM validation; image signing. |

### 10.3 Appliance Release Gate (Stage 3 Complete)

**Definition:** Product functions as universal AI governance enforcement point with network-level interception and all advanced features.

All MVP and Enterprise criteria plus:

| Category | Criteria |
|----------|----------|
| **Universal Gateway** | Transparent proxy mode; TLS interception with tenant-managed CA; reverse proxy mode; virtual appliance. |
| **AI DLP** | 8 DLP categories; per-category actions (allow/anonymize/redact/quarantine/block); contextual rules with business unit + classification. |
| **Voice Protection** | Real-time audio stream interception; local STT integration; audio redaction (silence/mask tone); <= 150ms P99 latency. |
| **Agent Governance** | MCP protocol inspection; per-tool permission policies; tool parameter anonymization; human approval suspension. |
| **AI Firewall (Extended)** | Data exfiltration detection; model manipulation detection; agent abuse detection; MITRE ATLAS/ATT&CK mapping; outbound PII reconstruction detection. |
| **Network Discovery** | AI traffic identification to 8+ providers; shadow AI detection; AI asset inventory. |
| **CASB** | AI SaaS classification (sanctioned/tolerated/unsanctioned); per-application policies; user activity query. |
| **Secure RAG** | Retrieval injection point inspection; vector database connectors; RAG content audit logging. |
| **SIEM Integration** | 5 SIEM platform sinks; MITRE mapping in every event; sink health API; local event buffering. |
| **Performance** | Proxy-only P95 <= 5ms; AI Firewall <= 20ms per request. |
| **Property Tests** | All MVP + Enterprise tests pass; additional tests for transparent proxy, DLP, agent governance, voice pipeline. |
| **Documentation** | Deployment guide for all 4 topologies; runbook; SRE playbook; resilience testing procedures; DORA audit evidence procedure. |

---

## 11. Appendix: Requirement Traceability

### 11.1 Requirement ID Mapping

| PRD Section | Requirement ID | Source Req ID | Commercial Tier |
|-------------|----------------|---------------|-----------------|
| 5.1 Core Pipeline | REQ-CORE-01 to 11 | Req 1 | MVP |
| 5.2 Detection Engine | REQ-DET-01 to 07 | Req 3 | MVP |
| 5.3 Tokenization | REQ-TOK-01 to 08 | Req 4 | MVP |
| 5.4 Cache Manager | REQ-CACHE-01 to 07 | Req 5 | MVP |
| 5.5 SSE Streaming | REQ-SSE-01 to 08 | Req 6 | MVP |
| 5.6 Multi-Provider | REQ-PROV-01 to 10 | Req 7 | MVP |
| 5.7 Multi-Locale | REQ-LOCL-01 to 07 | Req 8 | MVP |
| 5.8 Compliance Presets | REQ-COMP-01 to 05 | Req 9 | MVP |
| 5.9 Audit Logging | REQ-AUDT-01 to 06 | Req 10 | MVP |
| 5.10 Custom Rules | REQ-CFG-01 to 08 | Req 11 | MVP |
| 5.11 Deployment | REQ-DEP-01 to 08 | Req 12 | MVP |
| 5.12 Token Verification | REQ-VRFY-01 to 05 | Req 13 | MVP |
| 5.13 Rate Limiting | REQ-RATE-01 to 08 | Req 22 | Enterprise |
| 5.14 Multimodal | REQ-MULTI-01 to 05 | Req 23 | Enterprise |
| 5.15 AI Firewall | REQ-FW-01 to 08 | Req 36 | Enterprise |
| 5.16 Classification | REQ-CLASS-01 to 05 | Req 41 | Enterprise |
| 5.17 Governance | REQ-GOV-01 to 06 | Req 27 | Enterprise |
| 5.18 Financial Services | REQ-FIN-01 to 06 | Req 37-43 | Enterprise |
| 5.19 Universal Gateway | REQ-APPL-01 to 05 | Req 48 | Appliance |
| 5.20 Agent Governance | REQ-AGENT-01 to 04 | Req 51 | Appliance |
| 5.21 SIEM Integration | REQ-SIEM-01 to 06 | Req 56 | Appliance |
| 5.22 Discovery/CASB | REQ-DISC-01 to 03, REQ-CASB-01 to 02 | Req 53, 54 | Appliance |
| 5.23 RAG Protection | REQ-RAG-01 to 03 | Req 55 | Appliance |
| 5.24 Governance/Bias | REQ-GOVBIAS-01 to 06 | Req 32, 33, 34, 44, 45, 47 | Enterprise |

### 11.2 Regulatory Framework Mapping

| Regulation | Applicable Requirements |
|------------|------------------------|
| GDPR (EU) | REQ-CORE, DET, TOK, AUDT, LOCL, COMP, CLASS, GOVBIAS |
| EU AI Act | REQ-GOV (27-31), FW, GOVBIAS (32, 34, 35) |
| LGPD (Brazil) | REQ-LOCL (pt-BR), COMP (lgpd), AUDT |
| POPIA (South Africa) | REQ-LOCL, COMP (popia), AUDT |
| PIPEDA (Canada) | REQ-LOCL, COMP (pipeda), AUDT |
| DORA (EU Financial) | REQ-RATE, FIN (37, 40, 43), GOVBIAS (34) |
| NIS2 (EU) | REQ-FW, APPL, SIEM |
| SR 11-7 (US Federal Reserve) | REQ-FIN (39) |
| SEC Rule 10b-5 / FINRA 4511 | REQ-FIN (38, 44) |
| ISO 27001:2022 | REQ-RATE, GOV, FW, APPL, SIEM, GOVBIAS |
| ISO 42001:2023 | REQ-GOV (27-31, 35), GOVBIAS (32, 33) |
| HIPAA (US Healthcare) | REQ-DET, MULTI, APPL-DLP |

---

*End of Product Requirements Document*
