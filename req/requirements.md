# Requirements Document

## Introduction

AnonReq is a self-hosted data anonymization gateway that intercepts outbound LLM API calls from
internal applications, detects and replaces sensitive data (PII, PHI, financial identifiers) with
context-preserving placeholder tokens, forwards the sanitized request to any supported external
LLM provider, and restores original values in the response — all within the customer's secure
perimeter. No raw sensitive data ever crosses the network boundary.

The global edition extends the core gateway with multilingual PII detection across eight primary
locales (English, German, French, Dutch, Spanish, Italian, Arabic, and Portuguese/Brazilian),
per-jurisdiction compliance presets (GDPR, LGPD, PDPA, POPIA, Privacy Act, PIPEDA), and a
commercial open-source positioning (Apache 2.0 core) designed for enterprise adoption across
Europe, Asia-Pacific, Africa, South America, and Canada.

The product is designed to be investor-ready: clean architecture, compelling developer experience,
clear differentiation from SaaS alternatives, and a fail-secure foundation that enterprise
compliance officers can verify without trusting vendor promises.

---

## Glossary

- **Appliance**: A distinct commercial product tier of AnonReq that extends the core Gateway with universal AI traffic interception, AI-aware DLP, prompt security, agent governance, and SOC integration capabilities; described fully in the enterprise requirements document.
- **Audit_Logger**: The subsystem that records metadata about anonymization events without storing raw values.
- **Cache_Manager**: The subsystem that stores and evicts per-request token-to-value mappings in an ephemeral in-memory store.
- **Classification_Level**: A named sensitivity tier (`Public`, `Internal`, `Confidential`, `Restricted`, `Highly Restricted`) assigned to a request or entity by the Detection_Engine and used by policy rules to determine handling behavior.
- **Compliance_Preset**: A named, pre-configured set of entity types and detection thresholds aligned with a specific data protection regulation.
- **Confidence_Threshold**: The minimum detection confidence score (0.0–1.0) required for an entity to be tokenized.
- **Detection_Engine**: The subsystem that identifies sensitive entities in text using a hybrid regex and NER pipeline.
- **Exclusion_List**: A configured set of terms that the Detection_Engine must never flag as PII (e.g., product names, internal system identifiers).
- **Fail_Closed**: Synonym for Fail-Secure; used interchangeably in enterprise and financial-services contexts to emphasize that the default action on any ambiguity is denial, never permissive forwarding.
- **Fail-Secure**: The property that any internal error causes the Gateway to block the request and return an error rather than forwarding unsanitized data.
- **Gateway**: The AnonReq proxy service that intercepts, sanitizes, and restores LLM API traffic.
- **Locale**: A language and jurisdiction configuration (e.g., `de-DE`, `fr-FR`, `ar-SA`) that selects locale-specific PII recognizers.
- **Mapping**: The per-request, in-memory dictionary that associates each Token with its original value.
- **mTLS**: Mutual Transport Layer Security — a TLS handshake mode in which both client and server present X.509 certificates for mutual authentication, used between internal Gateway components and optionally between client applications and the Gateway.
- **NER**: Named Entity Recognition — a machine learning technique for identifying entity types in unstructured text.
- **PHI**: Protected Health Information — a subset of PII covered by healthcare regulations (e.g., HIPAA, NHS data standards).
- **PII**: Personally Identifiable Information — any data that can identify a natural person.
- **Provider_Adapter**: A format-translation layer that converts between the Gateway's internal representation and a specific LLM provider's API schema.
- **RBAC**: Role-Based Access Control — an authorization model in which permissions are granted to named roles (`administrator`, `security_officer`, `operator`, `read_only_auditor`) and users are assigned to roles rather than receiving permissions directly.
- **Restoration_Engine**: The subsystem that substitutes placeholder tokens with original values in LLM responses.
- **Round-Trip**: The property that anonymization followed by de-anonymization returns semantically equivalent content.
- **Session_ID**: A cryptographically random UUID that scopes a Mapping to a single request-response lifecycle.
- **SSE**: Server-Sent Events — the streaming protocol used by OpenAI, Anthropic, and Gemini APIs to deliver LLM output token-by-token.
- **Tail_Buffer**: A small retained suffix of the most recently emitted SSE chunk used to handle Tokens that span chunk boundaries.
- **Tenant_ID**: An opaque string identifier, supplied via the `X-AnonReq-Tenant-ID` request header, that scopes all Gateway operations (cache namespacing, audit logs, metrics, compliance preset selection) to a single tenant within a multi-tenant deployment.
- **Token**: A context-preserving placeholder of the form `[TYPE_N]` (e.g., `[NAME_1]`, `[EMAIL_1]`) that replaces a detected entity in outbound text.
- **Tokenization_Engine**: The subsystem that replaces detected entity spans with sequential typed placeholder tokens.
- **TTL**: Time-to-live — the maximum duration (in seconds) a Mapping persists in the Cache_Manager before automatic eviction.

---

## Requirements

### Requirement 1: Core Anonymization Pipeline (Non-Streaming)

**User Story:** As an enterprise developer, I want to route my existing LLM API calls through
AnonReq by changing only the `base_url`, so that my application automatically operates within
regulatory compliance without any other code changes.

#### Acceptance Criteria

1. THE Gateway SHALL expose a `POST /v1/chat/completions` endpoint that accepts an
   OpenAI-compatible request payload including `model`, `messages`, `temperature`, `max_tokens`,
   and `stream` fields, and SHALL return HTTP 400 with a structured error body for any request
   payload that does not conform to this schema.

2. WHEN a non-streaming request is received, THE Detection_Engine SHALL scan all text content
   across all message roles (system, user, assistant, tool, function) for sensitive entities
   before any content is forwarded to an external provider.

3. IF the Detection_Engine returns an error or is unreachable, THEN THE Gateway SHALL return
   HTTP 500 and SHALL NOT forward any part of the original request to the external provider.

4. IF the Cache_Manager is unreachable when a Mapping write is attempted, THEN THE Gateway
   SHALL return HTTP 500 and SHALL NOT forward any part of the original request to the external
   provider.

5. WHEN tokenization completes without error, THE Tokenization_Engine SHALL produce a modified
   request payload in which every detected entity span has been replaced by its corresponding
   Token, with all other payload fields preserved verbatim.

6. WHEN the external provider returns a response, THE Restoration_Engine SHALL replace every
   Token present in all text-bearing response fields (including `content`, `tool_calls`
   arguments, and `refusal` fields) with its original value retrieved from the Mapping before
   delivering the response to the caller.

7. IF a Token appears in the LLM response that is not present in the current session's Mapping,
   THEN THE Restoration_Engine SHALL leave the Token as-is in the response and SHALL emit a
   structured warning log entry containing only the Session_ID and the unmatched Token string.

8. WHEN response delivery is complete, THE Cache_Manager SHALL delete the Mapping for the
   current Session_ID within 100ms of the response being fully written to the client connection.

9. THE Gateway SHALL enforce a processing overhead — measured from request receipt to the first
   byte forwarded to the external provider — of no more than 100ms at the 95th percentile for
   prompts containing 1,000 words or fewer, where word count is determined by whitespace
   tokenization of the concatenated content of all message fields.

10. THE Gateway SHALL accept valid request payloads (as defined in Criterion 1) and produce
    valid anonymized-and-restored responses, ensuring that every Token inserted by the
    Tokenization_Engine has been replaced by its original value from the Mapping in the
    delivered response (round-trip correctness property).

11. IF the Cache_Manager is unreachable when a Mapping read is attempted during restoration,
    THEN THE Gateway SHALL return HTTP 500 to the caller and SHALL NOT deliver any partial
    response containing unreplaced Tokens.

---

### Requirement 2: Fail-Secure Architecture

**User Story:** As a Chief Information Security Officer, I want a cryptographic guarantee that
raw sensitive data can never reach an external LLM provider even if an internal component fails,
so that I can present AnonReq to our regulators as a data sovereignty enforcement layer rather
than a best-effort filter.

#### Acceptance Criteria

1. WHEN an unhandled exception propagates through the request processing pipeline, THE Gateway
   SHALL return HTTP 500 to the caller and SHALL NOT forward any content to the external
   provider.

2. WHEN the Detection_Engine fails a health probe (defined as failure to respond to a synthetic
   detect call within the configured detection timeout), THE Gateway SHALL reject all incoming
   requests with HTTP 500 and SHALL log a structured alert containing the timestamp, component
   name (`detection_engine`), and failure reason.

3. WHEN the Cache_Manager fails a health probe (defined as failure to respond to a PING command
   within 200ms), THE Gateway SHALL reject all incoming requests with HTTP 500 and SHALL log a
   structured alert containing the timestamp, component name (`cache_manager`), and failure
   reason.

4. IF a detection pipeline timeout occurs that exceeds the configured maximum detection latency
   (default 100ms, configurable), THEN THE Gateway SHALL return HTTP 504 to the caller and
   SHALL NOT forward the request.

5. THE Gateway SHALL expose a `GET /health` endpoint that returns HTTP 200 with a JSON body
   containing `{"status": "ok"}` only when all of the following components report healthy:
   Detection_Engine (NER model loaded and responsive to a synthetic probe call), and
   Cache_Manager (reachable and accepting writes within 200ms).

6. WHEN any component fails its health probe, THE `GET /health` endpoint SHALL return HTTP 503
   with a JSON body containing `{"status": "degraded", "components": {"<name>": "<reason>"}}`,
   identifying each degraded component by name and failure reason.

7. WHEN the Gateway process starts, it SHALL perform a pre-flight health probe of all required
   components and SHALL refuse to bind to its listening port and accept any traffic until all
   required components have passed their health probes, with a configurable startup timeout
   (default 60 seconds) after which the process exits with a non-zero status code.

8. THE Gateway SHALL produce either a valid anonymized-and-restored response or an HTTP error
   response (4xx or 5xx) for every request — where "raw sensitive data" means any substring
   from the original request payload that was identified as a detectable entity by the
   Detection_Engine (fail-secure completeness property).

---

### Requirement 3: Hybrid PII Detection Engine

**User Story:** As a Data Protection Officer, I want the gateway to detect both structured PII
(IBANs, tax IDs, credit card numbers) and unstructured PII (names, addresses, relationships) in
a single pipeline, so that the detection coverage is comprehensive and verifiable against our
data inventory.

#### Acceptance Criteria

1. THE Detection_Engine SHALL support a regex-based recognizer tier that detects the following
   structured entity types with Luhn or format-checksum validation where applicable (validating
   the checksum before flagging ensures that only mathematically valid instances are tokenized):
   email address, phone number (E.164 and national formats), credit card number (Luhn
   validated), IBAN (format and country prefix validated), IPv4 address, IPv6 address, URL,
   date of birth, national identification numbers (per active Locale — see Requirement 8),
   SWIFT/BIC code, and cryptocurrency wallet address.

2. THE Detection_Engine SHALL support an NER-based recognizer tier that detects the following
   unstructured entity types: person name, organization name, street address, city/region name,
   and job title.

3. WHEN both the regex tier and the NER tier produce entity spans that overlap (including
   partial overlap and containment) for the same character range, THE Detection_Engine SHALL
   resolve the conflict by retaining the regex result and discarding the NER result for the
   entire overlapping region.

4. THE Detection_Engine SHALL apply a configurable Confidence_Threshold (0.0–1.0, default 0.7)
   per entity type. WHEN a detected entity's confidence score is below the configured threshold
   for its type, THE Detection_Engine SHALL exclude that entity from the results returned to the
   Tokenization_Engine.

5. THE Detection_Engine SHALL load an Exclusion_List from configuration at startup. WHEN a
   detected entity's value, after applying case-folding and stripping leading/trailing
   whitespace, exactly matches any Exclusion_List entry, THE Detection_Engine SHALL exclude
   that entity from the results.

6. WHERE a custom regex pattern is defined in configuration for a named entity type, THE
   Detection_Engine SHALL apply that pattern in addition to built-in recognizers for that type.

7. THE Detection_Engine SHALL scan all text fields in the request payload, including `system`
   message content, `user` message content, `assistant` message content in conversation
   history, `tool` and `function` call arguments, and `tool` result content. IF the request
   payload contains additional text fields beyond those enumerated, THE Detection_Engine SHALL
   apply the same detection pipeline to those fields.

---

### Requirement 4: Context-Preserving Tokenization

**User Story:** As an enterprise developer, I want PII to be replaced with labeled placeholders
that preserve the entity type and unique index, so that the LLM can reason about the structure
of the prompt (e.g., "there are two different people mentioned") without seeing the raw values.

#### Acceptance Criteria

1. THE Tokenization_Engine SHALL replace each detected entity span with a Token of the form
   `[TYPE_N]`, where `TYPE` is an uppercase ASCII string of 1–20 characters (letters only, no
   digits or special characters) representing the entity-type abbreviation, and `N` is a
   positive integer representing the occurrence index for that type within the request.

2. WHEN the same raw entity value (compared as exact byte-for-byte string after Unicode
   normalization to NFC) appears more than once in a request payload, THE Tokenization_Engine
   SHALL assign the same Token to all occurrences of that value, ensuring consistent identity
   across the prompt.

3. WHEN two different entity values of the same type appear in a request payload, THE
   Tokenization_Engine SHALL assign different Tokens with distinct indices (e.g., `[NAME_1]`
   and `[NAME_2]`), preserving entity distinctness for LLM reasoning.

4. THE Tokenization_Engine SHALL perform entity replacement in reverse character-offset order
   (highest start position first) to prevent position drift when tokens of different lengths
   replace the original text spans.

5. THE Tokenization_Engine SHALL preserve all whitespace, punctuation, and formatting
   immediately adjacent to replaced spans exactly as received.

6. THE Tokenization_Engine SHALL store the complete Mapping for the request as a hash keyed by
   `anonreq:{Session_ID}` in the Cache_Manager, with a TTL in the range [60, 3600] seconds
   (default 300 seconds), before forwarding the request to the external provider. IF the
   Cache_Manager write fails, THE Tokenization_Engine SHALL return an error and SHALL NOT
   forward the request.

7. FOR ALL inputs containing N distinct entity values (compared as exact byte-for-byte strings)
   of the same type, THE Tokenization_Engine SHALL produce exactly N distinct Tokens of that
   type with indices 1 through N in order of first appearance (uniqueness invariant).

8. FOR ALL inputs where the same entity value (byte-for-byte) appears K times, THE
   Tokenization_Engine SHALL use exactly one Token for that value in the Mapping (deduplication
   invariant).

9. WHEN a request payload contains no detected entities, THE Tokenization_Engine SHALL forward
   the request to the external provider unchanged and SHALL NOT create a Mapping entry in the
   Cache_Manager.

10. WHEN a new Session_ID is created, THE Tokenization_Engine SHALL derive token index offsets
    from a cryptographically random seed per session, so that the same entity value produces
    different Token strings across different requests (cross-request token randomization
    property). The random seed SHALL be generated using the platform's cryptographically secure
    pseudorandom number generator (e.g., `secrets.token_bytes(16)` in Python) and SHALL NOT be
    stored in the Mapping or any persistent store.

---

### Requirement 5: Ephemeral Mapping Store

**User Story:** As a security architect, I want the token-to-value mapping to exist only in
RAM during a single request-response lifecycle and to be provably deleted afterward, so that
a server seizure or disk forensics investigation cannot recover any sensitive values.

#### Acceptance Criteria

1. THE Cache_Manager SHALL store all Mappings in a Valkey (or Redis-compatible) instance
   configured with persistence disabled (`save ""`, no AOF, no RDB snapshots) so that no
   Mapping data is ever written to disk.

2. THE Cache_Manager SHALL configure the in-memory store with a `maxmemory` value of at least
   256 MB and the `allkeys-lru` eviction policy so that orphaned Mappings are evicted under
   memory pressure.

3. THE Cache_Manager SHALL disable monitoring commands (`MONITOR`, `SLOWLOG`, keyspace
   notifications) in the in-memory store configuration to prevent Mapping data from leaking
   into operational tooling.

4. WHEN a non-streaming response has been fully written to the caller, THE Cache_Manager SHALL
   issue an asynchronous `DEL` command for the `anonreq:{Session_ID}` key. If the DEL command
   fails on the first attempt, THE Cache_Manager SHALL rely on TTL-based eviction as the
   fallback and SHALL NOT retry the DEL command.

5. WHEN a streaming response reaches its terminal event (`[DONE]` or connection close),
   THE Cache_Manager SHALL issue an asynchronous `DEL` command for the `anonreq:{Session_ID}`
   key within 100ms of the terminal event being forwarded to the caller.

6. WHILE a streaming response is in progress and the elapsed time since Session_ID creation
   exceeds 80% of the configured TTL (Session TTL), THE Cache_Manager SHALL extend the key's
   TTL by the value of the Session TTL to prevent premature eviction during long-running
   streams.

7. IF the `DEL` command fails after response delivery, THEN the TTL-based eviction SHALL serve
   as the fallback deletion mechanism, ensuring no Mapping persists beyond the configured TTL
   under any failure condition.

8. THE Cache_Manager SHALL expose a health check that verifies: the in-memory store is
   reachable within 200ms, a test key can be written and read, persistence is disabled
   (confirmed via `CONFIG GET save` returning an empty string), and AOF is disabled (confirmed
   via `CONFIG GET appendonly` returning `no`). The health check SHALL return a pass/fail
   boolean with a failure reason string.

---

### Requirement 6: SSE Streaming Support

**User Story:** As an enterprise developer, I want streaming responses to work transparently
through the gateway so that time-to-first-token latency is preserved for interactive
applications, and tokens are restored in the stream before reaching the client.

#### Acceptance Criteria

1. WHEN a request is received with `stream: true`, THE Gateway SHALL forward a streaming
   request to the external provider and return a `text/event-stream` response to the caller
   that delivers each SSE event as it is received from the provider, without buffering the
   complete response before forwarding.

2. WHEN streaming a response, THE Restoration_Engine SHALL pre-fetch the complete Mapping from
   the Cache_Manager at the start of the stream (via a single `HGETALL` command) and SHALL
   perform all subsequent Token lookups against the local in-memory copy, eliminating
   per-chunk network round-trips to the Cache_Manager.

3. WHEN a Token is split across two consecutive SSE chunks (e.g., `[NAME_` in chunk N and `1]`
   in chunk N+1), THE Restoration_Engine SHALL buffer the incomplete Token suffix using a
   Tail_Buffer (maximum 512 characters) and complete the replacement when the remainder arrives
   in the next chunk.

4. THE Restoration_Engine SHALL apply case-insensitive Token matching so that LLM-mutated
   variants such as `[name_1]` or `[Name_1]` are correctly resolved to their mapped values.

5. THE Restoration_Engine SHALL apply bracket-optional Token matching so that un-bracketed
   variants such as `NAME_1` bounded by word boundaries are correctly resolved to their mapped
   values.

6. WHEN a Tail_Buffer contains a partial Token prefix that is not completed after 50 consecutive
   chunks or 500ms of stream time (whichever is shorter), THE Restoration_Engine SHALL emit a
   structured log entry with fields `session_id` and `tail_buffer_flushed_bytes` (integer), and
   SHALL immediately yield the buffered content to the caller as-is.

7. THE Gateway SHALL propagate the headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`,
   and `Connection: keep-alive` on all streaming responses to prevent intermediate proxies and
   reverse proxies from buffering the stream.

8. FOR ALL streaming responses, every Token that was inserted by THE Tokenization_Engine SHALL
   appear in the final assembled response (defined as the concatenation of all SSE `data` field
   values received from the provider) as its original value (streaming round-trip property).

9. WHEN a streaming response reaches its terminal event (`[DONE]` or connection close), THE
   Restoration_Engine SHALL flush any remaining content in the Tail_Buffer to the caller before
   closing the response stream.

---

### Requirement 7: Multi-Provider LLM Support

**User Story:** As an enterprise infrastructure engineer, I want to configure AnonReq once and
route traffic to OpenAI, Anthropic, Gemini, or a local Ollama instance without changing
application code, so that our provider strategy remains flexible and vendor lock-in is avoided.

#### Acceptance Criteria

1. THE Gateway SHALL support OpenAI-compatible providers (including Azure OpenAI) by forwarding
   requests in OpenAI's native JSON schema with only the `Authorization` header replaced by the
   gateway-managed API key.

2. WHEN a request is routed to Anthropic Claude, THE Provider_Adapter SHALL translate the
   OpenAI `messages` array into Anthropic's Messages API format, including `system` prompt
   extraction, role mapping, and content block construction, for both streaming and
   non-streaming modes.

3. WHEN a request is routed to Google Gemini, THE Provider_Adapter SHALL translate the OpenAI
   payload into Gemini's `contents[]` format with `generationConfig` parameter mapping for
   both streaming and non-streaming modes.

4. THE Gateway SHALL support Ollama (self-hosted) by forwarding requests to a configurable
   base URL using OpenAI-compatible message format, enabling fully air-gapped deployments.

5. WHEN a request's `model` field matches a configured model alias, THE Provider_Adapter SHALL
   route the request to the corresponding upstream provider and translate the model name to the
   provider's native model identifier.

6. THE Gateway SHALL inject the upstream provider's API key from environment variables or a
   secrets file at the network boundary, ensuring that client applications never receive,
   transmit, or store provider keys.

7. THE Gateway SHALL expose a `GET /v1/models` endpoint that returns the list of configured
   model aliases and their target providers, enabling client libraries and frameworks such as
   LangChain and LlamaIndex to enumerate available models.

8. WHEN the upstream provider returns an HTTP error (4xx or 5xx), THE Gateway SHALL forward the
   error status to the caller with a response body that contains only the provider's HTTP status
   code and a generic error message, and SHALL NOT include provider API keys, internal endpoint
   URLs, raw prompt content, or Token values in the error payload.

9. IF a request's `model` field does not match any configured model alias, THEN THE Gateway
   SHALL return HTTP 400 with a structured error body identifying the unrecognized model value
   and SHALL NOT forward any content to an external provider.

10. IF the Provider_Adapter fails to translate the request payload into the target provider's
    format (due to schema mismatch, missing required fields, or an unhandled exception), THEN
    THE Gateway SHALL return HTTP 500 and SHALL NOT forward any content to the external
    provider (fail-secure translation property).

---

### Requirement 8: Multilingual PII Detection

**User Story:** As a compliance officer at a European financial institution, I want AnonReq to
detect PII in German, French, Dutch, Spanish, Italian, Arabic, Portuguese/Brazilian, and English
prompts, so that our multilingual workforce can use LLM tooling without creating GDPR exposure
across any language we operate in.

#### Acceptance Criteria

1. THE Detection_Engine SHALL support locale-specific regex recognizers for at least the
   following PII types per locale:
   - `en-*` (English): SSN, US passport, US driver's license, US phone (NANP)
   - `de-DE` (German): Steuer-ID (11-digit modulo-11), Personalausweis, German IBAN, German
     phone (national format)
   - `fr-FR` (French): NIR (15+2 digit INSEE), French passport, French phone
   - `nl-NL` (Dutch): BSN (9-digit modulo-11), Dutch phone, Dutch IBAN
   - `es-*` (Spanish): DNI (8 digits + letter), NIE (letter + 7 digits + letter), Spanish phone
   - `it-IT` (Italian): Codice Fiscale (16-character alphanumeric, validated per the official
     Italian fiscal code algorithm), Italian VAT (partita IVA), Italian phone
   - `ar-*` (Arabic): GCC national ID formats (UAE Emirates ID 784-YYYY-NNNNNNN-C, Saudi
     Iqama/Hawiya 1/2XXXXXXXXX, Kuwaiti Civil ID 1YYYYNNNNNNN), Arabic-script name patterns
   - `pt-BR` (Brazilian Portuguese): CPF (11-digit modulo-11), CNPJ (14-digit modulo-11),
     Brazilian phone

2. WHEN a request payload includes a `X-AnonReq-Locale` header with a supported locale code,
   THE Detection_Engine SHALL activate the locale-specific recognizer bundle for that locale in
   addition to the universal recognizers.

3. IF the `X-AnonReq-Locale` header contains an unsupported or malformed locale code, THEN THE
   Detection_Engine SHALL return HTTP 400 with a structured error body identifying the
   unsupported locale value and SHALL NOT process the request.

4. IF no `X-AnonReq-Locale` header is provided, THEN THE Detection_Engine SHALL apply
   universal recognizers only (email, IBAN, credit card, phone E.164, URL, IP) and SHALL emit
   a structured log entry with fields `session_id` and `locale_detection_skipped: true`.

5. THE Detection_Engine SHALL support multi-locale detection by accepting up to 10
   comma-separated locale codes in the `X-AnonReq-Locale` header, running all specified locale
   recognizers, and merging results. WHEN two locale recognizers of the same tier (both regex
   or both NER) produce overlapping spans, THE Detection_Engine SHALL retain the span with the
   higher confidence score; if scores are equal, it SHALL retain the span produced by the
   locale listed first in the header.

6. THE Detection_Engine SHALL be extensible so that new locale recognizer bundles can be added
   by placing a configuration file in the recognizers directory without modifying application
   source code.

7. THE Detection_Engine SHALL validate checksums before flagging the following locale-specific
   entity types: German Steuer-ID (modulo-11), Dutch BSN (modulo-11), French NIR (Luhn
   variant), Brazilian CPF (modulo-11), Brazilian CNPJ (modulo-11), and Italian Codice Fiscale
   (official fiscal code algorithm). Digit sequences of the correct length that fail checksum
   validation SHALL NOT be flagged as detected entities (locale checksum validation property).

---

### Requirement 9: Per-Jurisdiction Compliance Presets

**User Story:** As a legal counsel advising a financial institution operating in multiple
jurisdictions, I want to select a compliance preset that automatically enables the entity types
and detection thresholds required by the applicable data protection regulation, so that AnonReq
deployment decisions are defensible during regulatory audit.

#### Acceptance Criteria

1. THE Gateway SHALL provide a named compliance preset for each of the following frameworks,
   with each preset defining: the set of mandatory entity types to detect, the minimum
   Confidence_Threshold (0.0–1.0) per entity type, and the applicable Locale(s):
   - `gdpr` — European Union General Data Protection Regulation (GDPR Art. 4)
   - `lgpd` — Brazilian Lei Geral de Proteção de Dados Pessoais
   - `pdpa` — Personal Data Protection Act (Thailand/Singapore variant)
   - `popia` — Protection of Personal Information Act (South Africa)
   - `privacy-act-au` — Australian Privacy Act 1988 / Privacy Principles
   - `pipeda` — Canadian Personal Information Protection and Electronic Documents Act

2. WHEN a compliance preset is activated in configuration, THE Detection_Engine SHALL enforce
   the minimum entity type set defined by that preset. IF a custom rule disables an entity type
   that the active preset mandates, THEN THE Gateway SHALL reject the configuration at startup
   with an error message that identifies the disabled entity type and the preset that mandates
   it.

3. THE Audit_Logger SHALL include the active compliance preset name as the `compliance_preset`
   field (preset identifier string, or `null` if no preset is active) in every audit log entry,
   enabling log aggregation systems to filter and report compliance events by regulatory
   framework.

4. IF a deployment has multiple compliance presets active simultaneously, THEN THE Gateway
   SHALL apply a merged preset that is the union of all mandatory entity types from each active
   framework, with the highest Confidence_Threshold across all active presets applied for each
   entity type.

5. THE Gateway SHALL expose a `GET /v1/compliance/presets` endpoint that returns a JSON object
   listing each available preset with its identifier, mandatory entity types, minimum
   Confidence_Threshold per entity type, and applicable locales, enabling compliance teams to
   document their configuration during audit preparation.

6. IF no compliance preset is active, THEN THE Detection_Engine SHALL operate with its default
   built-in recognizer set and default Confidence_Thresholds, and THE Audit_Logger SHALL record
   `compliance_preset: null` in every audit log entry.

---

### Requirement 10: Metadata-Only Audit Logging

**User Story:** As a Data Protection Officer, I want structured audit logs that prove the
gateway anonymized sensitive entities on every request, without the logs themselves becoming a
PII liability, so that I can satisfy regulatory audit requirements under GDPR Article 30
without creating a secondary data store that needs its own protection measures.

#### Acceptance Criteria

1. THE Audit_Logger SHALL emit a structured JSON log entry to stdout for every completed
   request-response cycle, containing exactly the following fields: `timestamp` (ISO 8601 UTC),
   `session_id` (UUID), `target_provider`, `target_model`, `entity_counts` (object mapping
   entity type names to integer counts, maximum 50 keys), `total_entities_detected`
   (non-negative integer), `streaming` (boolean), `latency_ms` (object with `detection`,
   `tokenization`, `restoration`, and `total_overhead` as non-negative integer fields, each
   capped at 999,999), `compliance_preset` (string matching the preset identifier, maximum
   64 characters, or null), and `locale` (BCP 47 locale string or null). The log entry SHALL
   be written to stdout before the HTTP response is flushed to the client.

2. THE Audit_Logger SHALL NEVER include in any log entry: raw prompt text, raw response text,
   anonymization placeholder token strings (the substituted stand-in values used in place of
   detected entities), original entity values, authentication credentials including API keys
   and bearer tokens, or internal endpoint URLs.

3. IF an exception occurs during audit log entry construction or emission, THEN THE
   Audit_Logger SHALL discard the log entry, preserve the HTTP response status, headers, and
   body exactly as they would have been delivered without the exception, and increment the
   `anonreq_audit_log_failures_total` Prometheus counter.

4. THE Gateway SHALL apply a structured-log field allowlist so that no middleware, exception
   handler, or framework-level logging can inadvertently include raw message content in log
   output; any log record containing a field not in the allowlist SHALL be silently stripped
   before writing.

5. WHEN a fail-secure event occurs (detection failure, cache failure, or timeout), THE
   Audit_Logger SHALL emit a structured log entry containing: `timestamp` (ISO 8601 UTC),
   `session_id`, `failure_type` (one of `detection_error`, `cache_error`, `timeout`, or
   `unknown` where `unknown` applies when the failure cannot be classified as any of the
   preceding types), and `http_status_returned` (integer in range 400–599), with no raw
   content.

6. THE Audit_Logger SHALL write each audit log entry to stdout before the corresponding HTTP
   response is flushed to the client, ensuring that a process crash immediately after response
   delivery does not result in a missing audit record.

---

### Requirement 11: Custom Detection Rules and Exclusion Lists

**User Story:** As a platform engineer at a financial services firm, I want to define custom
regex patterns for our internal identifiers (employee IDs, account numbers, fund codes) and
maintain an exclusion list for product names and system terms, so that AnonReq covers our
domain-specific PII without generating false positives on business terminology.

#### Acceptance Criteria

1. THE Detection_Engine SHALL load custom pattern recognizers from a YAML configuration file at
   startup, where each entry defines: `name` (string), `entity_type` (string), `patterns`
   (list of regex strings), `context_words` (optional list of strings that boost confidence
   when present near the match), and `score` (float 0.0–1.0).

2. WHEN a custom pattern recognizer's regex matches a text span, THE Detection_Engine SHALL
   treat the match with the confidence score defined in the configuration, subject to the same
   Confidence_Threshold filtering as built-in recognizers.

3. THE Detection_Engine SHALL load the Exclusion_List from a plain-text or YAML file at
   startup, where each entry is a string term.

4. WHEN a detected entity value, after applying NFKC Unicode normalization and case-folding,
   exactly matches any Exclusion_List entry (also normalized to NFKC and case-folded), THE
   Detection_Engine SHALL suppress that detection.

5. THE Exclusion_List SHALL support wildcard matching using `*` as a suffix wildcard (e.g.,
   `GraphAPI.*` suppresses any detection starting with `GraphAPI.`).

6. WHEN the custom recognizer configuration file or the Exclusion_List file is modified on
   disk, THE Detection_Engine SHALL perform an atomic configuration swap (replacing the active
   recognizer set in a single operation) within 60 seconds of the file modification timestamp
   changing, without requiring a process restart and without any window where the configuration
   is partially loaded.

7. IF a custom recognizer pattern contains an invalid regex, THEN THE Detection_Engine SHALL
   reject the configuration at startup with an error identifying the invalid pattern string and
   SHALL NOT start serving traffic with a partially loaded recognizer set.

8. IF the custom recognizer YAML configuration file is missing at startup, THEN THE
   Detection_Engine SHALL start with built-in recognizers only and SHALL log a structured
   warning identifying the expected file path.

9. IF the Exclusion_List file is missing at startup, THEN THE Detection_Engine SHALL start
   with an empty Exclusion_List and SHALL log a structured warning identifying the expected
   file path.

10. THE Gateway SHALL expose a `GET /v1/config/rules` endpoint (authenticated) that returns the
    names and entity types of all active custom recognizers and the count of Exclusion_List
    entries, enabling operators to verify that configuration was loaded correctly.

---

### Requirement 12: Docker Compose Deployment

**User Story:** As a DevOps engineer, I want to bring up a fully functional AnonReq gateway
with a single `docker compose up` command that starts all required services with correct
networking, so that we can deploy to a pilot customer's VPC in under 30 minutes.

#### Acceptance Criteria

1. THE Gateway SHALL ship a `docker-compose.yml` that defines at minimum the following services:
   `anonreq` (the FastAPI proxy), `presidio` (the Presidio Analyzer as an independent service),
   and `valkey` (the ephemeral cache), all connected via an internal Docker network. Host port
   exposure SHALL only be enabled by supplying a Docker Compose override file that adds a
   `ports` mapping; the default `docker-compose.yml` SHALL NOT expose any service port to the
   host network.

2. WHEN `docker compose up` is executed in the project root on a system meeting the minimum
   specifications (4-core CPU, 8 GB RAM, Docker Engine 24+), THE `GET /health` endpoint SHALL
   return HTTP 200 within 60 seconds of the command completing.

3. THE Gateway SHALL implement a multi-stage Dockerfile with a Python 3.12-slim base image,
   where stage 1 downloads and installs NLP models and stage 2 copies only application code
   and pre-built model artifacts. The final stage image size SHALL NOT exceed 2 GB.

4. THE Gateway SHALL configure the Valkey service with `save ""` (no RDB snapshots) and SHALL
   bind Valkey to the internal Docker network only (no host port binding) in the default
   configuration.

5. THE Gateway service SHALL declare a `depends_on` condition `service_healthy` for both the
   `presidio` service and the `valkey` service, and both dependency services SHALL define
   explicit `healthcheck` stanzas in the `docker-compose.yml` specifying the test command,
   interval, timeout, and retries.

6. ALL configurable parameters (provider API keys, TTL, Confidence_Threshold defaults, active
   compliance preset, locale, custom rules paths) SHALL be injectable via environment variables
   with documented defaults, and SHALL NOT have sensitive values hardcoded in the
   `docker-compose.yml` file.

7. THE Gateway SHALL ship a `.env.example` file documenting every supported environment
   variable, its type, default value, and a one-sentence description, enabling operators to
   configure the gateway without reading source code.

8. IF a required environment variable (one with no default value) is absent at startup, THEN
   THE Gateway SHALL exit with a non-zero status code and SHALL log a structured error
   identifying the missing variable name before terminating.

---

### Requirement 13: Response-Side Token Verification

**User Story:** As a compliance officer, I want assurance that no residual tokens remain in the
delivered response even if partial restoration fails, so that end users never see raw
placeholder artifacts that could signal a gateway misconfiguration.

#### Acceptance Criteria

1. WHEN a non-streaming response has been restored by THE Restoration_Engine, THE
   Restoration_Engine SHALL perform a post-restoration verification scan using the token
   pattern `\[[A-Z]+_\d+\]` on the full response body before delivering it to the caller.

2. IF the post-restoration scan finds any unreplaced Tokens in a non-streaming response, THEN
   THE Restoration_Engine SHALL log a structured warning with the `session_id` and the count of
   unreplaced Tokens (not the Token values), SHALL increment the
   `anonreq_tokens_unrestored_total` Prometheus counter, and SHALL deliver the response as-is
   without altering the HTTP status code.

3. WHEN a streaming response reaches its terminal event (the stream-end sentinel or connection
   close), THE Restoration_Engine SHALL perform a post-stream verification scan on the full
   assembled text of the stream and SHALL log a structured warning with the `session_id` and
   the count of unreplaced Tokens if any are found.

4. THE Gateway SHALL expose a Prometheus-compatible `GET /metrics` endpoint that includes at
   minimum: `anonreq_requests_total` (counter, labeled by provider and status),
   `anonreq_detection_latency_seconds` (histogram), `anonreq_entities_detected_total` (counter,
   labeled by entity type), `anonreq_tokens_unrestored_total` (counter, labeled by session
   outcome), `anonreq_fail_secure_events_total` (counter, labeled by failure type), and
   `anonreq_audit_log_failures_total` (counter).

5. IF the post-stream verification scan (Criterion 3) encounters an exception, THEN THE
   Restoration_Engine SHALL log a structured error with the `session_id` and exception type and
   SHALL NOT surface the exception to the caller or alter the already-delivered streaming
   response.

---

### Requirement 14: Commercial Open-Source Positioning

**User Story:** As an investor evaluating AnonReq, I want to see a clear open-source licensing
strategy and a commercial differentiation path, so that I can assess the defensibility of the
business model and the governance structure.

#### Acceptance Criteria

1. THE Gateway source code SHALL be released under the Apache License 2.0, providing enterprise
   users with patent protection, sublicensing rights, and compatibility with commercial
   redistribution without copyleft obligations.

2. THE Gateway README SHALL include a section titled "License and Commercial Use" that states:
   the Apache 2.0 SPDX identifier (`Apache-2.0`), that the open-source core may be self-hosted
   without restriction, the email contact for commercial support inquiries, and a brief
   description of the commercial differentiation path (e.g., professional support tiers,
   compliance add-ons, or managed deployment services).

3. THE Gateway SHALL ship a `NOTICE` file as required by Apache 2.0 listing all third-party
   dependencies with the following per-entry fields: dependency name, version, and SPDX license
   identifier, so that enterprise legal teams can complete open-source license reviews without
   manual dependency auditing.

4. THE Gateway repository SHALL include a `SECURITY.md` file that defines: a responsible
   disclosure contact email, a target initial response time of no more than 5 business days for
   reports describing unauthenticated remote code execution, authentication bypass, or sensitive
   data exposure, and the scope of what qualifies as an in-scope security report.

5. THE Gateway README SHALL include a "Roadmap" or "Commercial Features" section that
   describes at least one planned commercial differentiation feature (e.g., compliance
   dashboard, SLA-backed support, enterprise SSO integration), providing investors with a
   concrete path from open-source adoption to commercial revenue.

---

### Requirement 15: Developer Experience and Multilingual Documentation

**User Story:** As a developer at a European or Brazilian financial institution, I want to read
the integration guide in my primary language and find working code examples for my stack, so
that I can evaluate and deploy AnonReq within a single business day without requiring a sales
call or professional services engagement.

#### Acceptance Criteria

1. THE Gateway SHALL ship a `docs/` directory containing an integration quickstart guide
   translated into at minimum English, German, French, Spanish, and Portuguese (Brazilian).
   Each guide SHALL include: a Docker Compose startup walkthrough, a `curl` example of a
   complete anonymization round-trip (request with synthetic PII and its restored response),
   and a section titled "Verifying PII Absence in Logs" that shows how to confirm no PII
   appears in stdout audit log output using a shell command.

2. THE Gateway SHALL ship SDK usage examples in the `examples/` directory for Python (using the
   `openai` SDK with `base_url` override), Node.js (using the `openai` npm package with
   `baseURL` override), and `curl` / shell, each demonstrating a complete round-trip with
   synthetic PII data. Each example SHALL include an assertion or check that the response
   contains the restored original value, not the token placeholder.

3. THE Gateway README SHALL include a "Why AnonReq" section that: describes the GDPR Article 28
   processor obligation and its implications for using US-hosted LLM APIs, explains the US
   CLOUD Act extraterritorial risk for EU data stored on US-owned infrastructure, and states
   how AnonReq's self-hosted architecture removes both risks. The section SHALL be present in
   the English README and SHALL be referenced from each translated quickstart guide.

4. THE Gateway SHALL ship a `CHANGELOG.md` following the Keep a Changelog format. The initial
   release entry SHALL document all features shipped in v1.0.0 under the "Added" section, with
   each entry describing a user-visible change.

---

### Requirement 16: Anonymization Correctness Properties

**User Story:** As a principal engineer responsible for certifying AnonReq for production use,
I want a property-based test suite that proves the anonymization guarantees hold across arbitrary
inputs, so that correctness is demonstrated by generative proof rather than manually selected
test cases.

#### Acceptance Criteria

1. THE test suite SHALL include a property-based test verifying the **round-trip correctness**
   property: WHEN a valid prompt text `T` containing detectable PII entities is anonymized to
   produce `T'` and then de-anonymized using the generated Mapping to produce `T''`, THEN `T''`
   SHALL be identical to `T` as a complete string (every character position, including
   non-entity characters, must match exactly).

2. THE test suite SHALL include a property-based test verifying the **token uniqueness
   invariant**: WHEN a prompt text contains N distinct entity values (compared as exact
   byte-for-byte strings) of type `X`, THEN THE Tokenization_Engine SHALL produce exactly N
   distinct Tokens of type `X` in the output, with no two distinct values sharing the same
   Token string.

3. THE test suite SHALL include a property-based test verifying the **deduplication invariant**:
   WHEN entity value `V` appears K ≥ 2 times in a prompt text (compared as exact byte-for-byte
   strings), THEN all K occurrences in the tokenized output SHALL contain the same Token string.

4. THE test suite SHALL include property-based tests verifying the **fail-secure invariant**,
   with each of the three failure modes tested independently: (a) WHEN the Detection_Engine is
   unavailable, THE Gateway SHALL return HTTP 500 and the forwarded request count to the
   external provider SHALL be 0; (b) WHEN the Cache_Manager is unavailable, THE Gateway SHALL
   return HTTP 500 and the forwarded request count SHALL be 0; (c) WHEN the detection pipeline
   times out, THE Gateway SHALL return HTTP 500 and the forwarded request count SHALL be 0.

5. THE test suite SHALL include a property-based test verifying the **locale checksum
   validation property**: WHEN a randomly generated digit sequence of the correct length is
   provided for each locale-specific national ID type — German Steuer-ID (11 digits), Dutch
   BSN (9 digits), Brazilian CPF (11 digits) — and the sequence does not satisfy the respective
   checksum algorithm, THEN THE Detection_Engine SHALL NOT flag it as a detected entity.

6. THE test suite SHALL include a property-based test verifying the **no-PII-in-logs property**:
   WHEN a request payload containing synthetic PII test data is processed, THEN the structured
   log output produced by THE Audit_Logger SHALL contain no substrings matching the PII values,
   determined by a case-sensitive exact substring search against the raw log output bytes.

7. THE test suite SHALL include a property-based test verifying the **streaming round-trip
   property**: WHEN a response containing Tokens is split into two SSE chunks at every possible
   split index of each Token string, THEN THE Restoration_Engine SHALL produce a final assembled
   output that is character-for-character identical to the non-streaming restoration of the
   same content.

8. THE test suite SHALL include a property-based test verifying the **cross-request token
   randomization property**: WHEN the same entity value V appears in two separate requests R1
   and R2 (each with an independent Session_ID), THE Tokenization_Engine SHALL produce Token
   strings T1 ≠ T2 for V across the two sessions with probability ≥ 1 − 2^{-32}, verified
   by running the test with at least 1,000 independently seeded session pairs and asserting
   that no two sessions produce identical token index assignments for the same input.

---

### Requirement 17: Enterprise Authentication and Authorization

**User Story:** As a security administrator, I want all gateway and administrative interfaces protected by strong authentication and role-based authorization, so that only approved users and systems can access sensitive functionality.

#### Acceptance Criteria

1. THE Gateway SHALL support three authentication mechanisms: (a) API keys with a minimum entropy of 256 bits, generated using a cryptographically secure random source; (b) OAuth 2.0 JWT bearer tokens, validated against a configured JWKS endpoint, with token expiry enforced using a configurable expiry window (default 3600 seconds, minimum 60 seconds); and (c) mutual TLS (mTLS), with client certificate CN validated against a configurable allowlist pattern.

2. WHEN a request arrives without a valid credential in any of the configured authentication mechanisms, THE Gateway SHALL return HTTP 401 and SHALL NOT process the request further.

3. THE Gateway SHALL enforce RBAC using the following built-in roles: `administrator` (full access to all endpoints and configuration), `security_officer` (read/write access to compliance presets and audit logs; read-only access to configuration), `operator` (read/write access to provider configuration; no access to audit logs or compliance presets), and `read_only_auditor` (read-only access to audit logs and metrics; no access to configuration endpoints).

4. WHEN a request targets an administrative endpoint and the caller's role does not grant the required permission for that endpoint, THE Gateway SHALL return HTTP 403 and SHALL log a structured audit entry containing `timestamp`, `session_id`, `endpoint`, `method`, `caller_role`, and `required_permission`.

5. THE Gateway SHALL require authentication for all administrative endpoints, including `GET /v1/config/*`, `POST /v1/config/*`, `GET /v1/compliance/*`, `GET /metrics`, and, if enabled via configuration, `GET /health`.

6. THE Gateway SHALL support delegation to external identity providers via OpenID Connect (OIDC) and SAML 2.0, mapping external claims or attributes to internal RBAC roles using a configurable claim-to-role mapping.

7. THE Gateway SHALL maintain a revocation list for API keys and JWT tokens, checked on every authenticated request, with a configurable cache TTL (default 60 seconds) for the revocation list lookup to limit Cache_Manager load.

8. THE Gateway SHALL record all administrative authentication events (successful and failed) and all authorization denials in the audit log with fields: `timestamp`, `event_type` (one of `auth_success`, `auth_failure`, `authz_denied`), `mechanism` (one of `api_key`, `jwt`, `mtls`), `endpoint`, and `http_status_returned`.

9. IF the authentication service (OIDC provider, JWKS endpoint, or revocation list source) becomes unreachable, THEN THE Gateway SHALL fail closed: all requests requiring external authentication validation SHALL be rejected with HTTP 503, and no administrative functions SHALL be accessible until the authentication service is restored or the Gateway is reconfigured to use a local fallback credential.

---

### Requirement 18: Secrets Management and Network Security

**User Story:** As a Chief Information Security Officer, I want all credentials, certificates, and communications protected by enterprise-grade controls, so that the gateway can be deployed in regulated environments with no plaintext secrets at rest or in transit.

#### Acceptance Criteria

1. THE Gateway SHALL enforce TLS 1.3 for all external communications (inbound from clients, outbound to LLM providers). TLS 1.2 is permitted as a fallback ONLY when the connecting client or upstream provider explicitly does not support TLS 1.3 and the `tls.allow_tls12_fallback` configuration flag is set to `true` (default `false`); all TLS 1.2 connections SHALL be logged as a structured warning with the peer address and negotiated version.

2. THE Gateway SHALL support mTLS for internal component communications: between Gateway and Detection_Engine, between Gateway and Cache_Manager, and optionally between Gateway and upstream LLM providers where the provider supports client certificates. WHEN a configured mTLS channel receives a connection without a valid client certificate, THE Gateway SHALL reject the connection and SHALL NOT fall back to unauthenticated TLS.

3. WHEN mTLS is not configured for a given internal channel and an API key is configured as the fallback credential, THE Gateway SHALL accept API key authentication for that channel; IF neither mTLS nor an API key is configured, THE Gateway SHALL refuse to start and SHALL exit with a non-zero status code identifying the unsecured channel.

4. THE Gateway SHALL retrieve all secrets (LLM provider API keys, internal API keys, mTLS private keys, JWT signing keys) from one of the following sources, selected by configuration: HashiCorp Vault (KV v2 or Transit engine), AWS Secrets Manager, Azure Key Vault, or Google Secret Manager. Direct environment variable injection is permitted for development deployments only (when `environment: development` is set in configuration).

5. THE Gateway SHALL support automatic secret rotation without process restart: WHEN the configured secret source signals that a secret has been rotated (via a configurable polling interval, default 300 seconds), THE Gateway SHALL fetch the new secret value and begin using it for all new requests within the configured grace period (default 300 seconds, configurable 60–3600 seconds), allowing in-flight requests that began with the previous secret to complete.

6. THE Gateway SHALL NEVER write secret values (API keys, tokens, private key material, or passwords) to logs, metrics, audit events, error messages, or health check responses. WHEN any log record is constructed, THE Gateway SHALL apply a secrets-scrubbing pass that replaces any substring matching a loaded secret value with the literal string `[REDACTED]`.

7. THE Gateway SHALL validate that all required secrets are present, non-empty, and meet minimum entropy requirements (256 bits for API keys, as validated by Shannon entropy calculation) during the startup pre-flight check. IF any required secret is absent or fails validation, THE Gateway SHALL exit with a non-zero status code and SHALL log the name of the failing secret (not its value).

8. THE Gateway SHALL expose a `GET /v1/security/status` endpoint (requiring `security_officer` or `administrator` role) that returns the health status of each configured secret source (reachable/unreachable) and the age of each loaded secret in seconds, without exposing any secret values.

9. IF secret retrieval from the configured source fails at any point during request processing (e.g., a Vault token expires mid-operation), THEN THE Gateway SHALL return HTTP 503 and SHALL NOT process the request with stale or absent credentials.

---

### Requirement 19: Multi-Tenant Isolation and Governance

**User Story:** As a platform owner serving multiple customers, I want complete tenant isolation so that one tenant can never access another tenant's data, configuration, audit records, or metrics.

#### Acceptance Criteria

1. THE Gateway SHALL support multi-tenant operation within a single deployment. EACH tenant SHALL be identified by a Tenant_ID, supplied on every request via the `X-AnonReq-Tenant-ID` header.

2. WHEN a request arrives without an `X-AnonReq-Tenant-ID` header and multi-tenant mode is enabled, THE Gateway SHALL return HTTP 400 with a structured error body identifying the missing header and SHALL NOT process the request.

3. IF the supplied Tenant_ID does not match any provisioned tenant in the Gateway's tenant registry, THEN THE Gateway SHALL return HTTP 403 and SHALL NOT process the request.

4. THE Cache_Manager SHALL namespace all Mapping keys using both Tenant_ID and Session_ID, in the form `anonreq:{tenant_id}:{session_id}`. Cross-tenant Mapping access SHALL be structurally impossible: the Cache_Manager SHALL construct all key lookups using the Tenant_ID extracted from the authenticated request context, never from request body content.

5. EACH tenant SHALL have fully independent configuration: compliance presets, provider credentials, custom recognizers, exclusion lists, Confidence_Threshold overrides, and TTL settings. A change to one tenant's configuration SHALL NOT affect any other tenant's active sessions or configuration.

6. THE Audit_Logger SHALL write each tenant's audit log to a separate, tenant-scoped log stream. Cross-tenant log mixing SHALL be structurally prevented: the Audit_Logger SHALL include `tenant_id` as a mandatory top-level field in every log entry and SHALL route log entries to tenant-scoped output channels when configured.

7. THE Gateway SHALL maintain per-tenant Prometheus metrics, labeling all metric series with `tenant_id`. WHEN a metrics scrape is performed, THE Gateway SHALL return only the metrics the requesting API key's tenant is authorized to read, unless the caller has the `administrator` role.

8. THE Gateway SHALL expose a tenant provisioning API: `POST /v1/admin/tenants` (create tenant), `DELETE /v1/admin/tenants/{tenant_id}` (deprovision tenant), and `GET /v1/admin/tenants` (list tenants with status). All tenant management endpoints SHALL require the `administrator` role.

9. WHEN a tenant is deprovisioned via `DELETE /v1/admin/tenants/{tenant_id}`, THE Gateway SHALL immediately invalidate all active sessions for that tenant by issuing a batch `DEL` for all `anonreq:{tenant_id}:*` keys in the Cache_Manager, reject all subsequent requests carrying that Tenant_ID with HTTP 403, and emit a structured audit log entry with `event_type: tenant_deprovisioned`.

10. FOR ALL requests, tenant context SHALL remain isolated throughout the entire request lifecycle — detection, tokenization, cache read/write, provider routing, restoration, audit logging, and metrics recording — verified by an integration test that confirms zero cross-tenant data leakage under concurrent load.

---

### Requirement 20: High Availability, Scalability, and Disaster Recovery

**User Story:** As an infrastructure architect, I want AnonReq to continue operating during component failures, scale horizontally under load, and meet documented recovery objectives, so that it qualifies as a production-grade system for enterprise environments.

#### Acceptance Criteria

1. THE Gateway SHALL be stateless at the application tier so that multiple Gateway instances can run concurrently behind a load balancer without requiring session affinity. All shared state SHALL reside exclusively in the Cache_Manager.

2. THE Cache_Manager SHALL support high-availability deployment in both Valkey Sentinel mode (minimum 1 primary + 2 replicas + 3 sentinel processes) and Valkey Cluster mode (minimum 3 primary shards with 1 replica each). The `redis-py` client SHALL be configured with automatic failover using the Sentinel or Cluster client class as appropriate.

3. WHEN a primary Cache_Manager node fails, THE Gateway SHALL detect the failover and resume normal operation within 30 seconds, relying on Sentinel or Cluster automatic failover. Requests received during the failover window SHALL be rejected with HTTP 503 (fail-secure) rather than forwarded without a Mapping.

4. THE Gateway SHALL support Kubernetes deployment via the official Helm chart named `anonreq/anonreq`. The Helm chart SHALL expose values for replica count, resource requests/limits, HPA configuration, and Valkey connection parameters.

5. THE Gateway SHALL ship Kubernetes readiness and liveness probe definitions: the readiness probe SHALL target `GET /health` (HTTP 200 = ready), and the liveness probe SHALL target `GET /health` (HTTP 503 for ≥ 3 consecutive failures = restart).

6. THE Gateway SHALL support a Kubernetes HorizontalPodAutoscaler targeting 70% CPU utilization, with a minimum of 2 replicas and a configurable maximum (default 10).

7. THE Gateway SHALL support zero-downtime rolling upgrades: during a rolling upgrade, the old version SHALL continue to serve requests until the new version passes its readiness probe, and no request SHALL receive an error solely due to the upgrade process.

8. THE Gateway SHALL define and document the following recovery objectives: availability SLA of 99.9% measured over any 30-day calendar window (allowing ≤ 43.8 minutes of unplanned downtime per month), RTO ≤ 15 minutes (time from failure detection to full service restoration), and RPO = 0 for all configuration data (configuration is stored in version-controlled files or a secrets manager, not in volatile state).

9. THE Gateway SHALL publish documented minimum sizing recommendations for three deployment tiers: development (1 Gateway replica, 1 Valkey node, 2 CPU / 4 GB RAM total), staging (2 Gateway replicas, Valkey Sentinel, 4 CPU / 8 GB RAM total), and production (≥ 3 Gateway replicas, Valkey Cluster, ≥ 8 CPU / 16 GB RAM total, HPA enabled).

10. IF a Gateway instance fails while processing a request, other healthy instances SHALL continue serving traffic without interruption, and the failed instance SHALL be removed from the load balancer's rotation within the configured health check interval (default 10 seconds).

---

### Requirement 21: Data Sovereignty, Compliance Assurance, and Detection Quality

**User Story:** As a compliance and operations leader, I want measurable compliance guarantees, regional enforcement, and verifiable detection quality, so that AnonReq can withstand enterprise procurement review and regulatory audit.

#### Acceptance Criteria

**Geographic Routing and Data Residency**

1. THE Gateway SHALL support region-restricted provider routing policies. WHEN a policy restricts a tenant to a specific geographic region (e.g., `eu-only`, `de-only`, `ca-only`, `au-only`, or a customer-defined region set), THE Gateway SHALL route requests exclusively to provider endpoints whose declared data residency falls within the approved region(s).

2. WHEN a routing policy would require forwarding a request to a provider endpoint outside the approved region, THE Gateway SHALL reject the request with HTTP 403, include a structured error body with `reason: routing_policy_violation` and the tenant's active region policy, and emit a structured audit log entry with `event_type: routing_policy_violation`.

3. THE Gateway SHALL validate provider endpoint region assignments at startup against a configurable provider-region registry. IF a provider endpoint's region cannot be determined from the registry, THE Gateway SHALL treat it as outside all approved regions (fail-closed for unknown regions).

**Detection Quality Thresholds**

4. THE project SHALL maintain annotated benchmark datasets for every supported locale (`en-*`, `de-DE`, `fr-FR`, `nl-NL`, `es-*`, `it-IT`, `ar-*`, `pt-BR`). Each dataset SHALL contain a minimum of 500 labeled examples covering all mandatory entity types for that locale.

5. THE Detection_Engine SHALL meet the following detection quality thresholds per locale, measured on the benchmark dataset: precision ≥ 0.95 and recall ≥ 0.90 for each mandatory entity type. THE CI/CD pipeline SHALL execute a detection quality regression test on every pull request and SHALL fail the build if any locale/entity-type combination falls below these thresholds.

6. THE project SHALL publish detection quality metrics (precision, recall, F1 score per entity type per locale) in the repository's `docs/quality/` directory, updated on every release, so that compliance teams can include them in regulatory documentation.

**Multimodal and Structured Document Support**

7. THE Gateway SHALL apply the anonymization pipeline to the following content types in addition to plain chat messages: tool call arguments and results (JSON payloads), JSON documents submitted as message content, and metadata fields of multimodal requests (image description text, file name fields). IF a submitted content type is not supported for anonymization, THE Gateway SHALL return HTTP 415 with a structured error identifying the unsupported content type.

**Rate Limiting and Spend Controls**

8. WHEN a request exceeds the configured rate limit for the tenant (requests per minute, tokens per minute, or concurrent request count), THE Gateway SHALL return HTTP 429 with a `Retry-After` header indicating the number of seconds until the next request is permitted, and SHALL NOT forward the request to the upstream provider.

9. WHEN a request would cause the tenant's spend to exceed a configured daily or monthly budget limit, THE Gateway SHALL return HTTP 402 with a structured error body identifying the exceeded budget type and the current spend, and SHALL NOT forward the request to the upstream provider.

**Supply Chain Security**

10. THE project SHALL ship an SBOM (Software Bill of Materials) in CycloneDX JSON format with every release, generated automatically by the CI/CD pipeline. The SBOM SHALL enumerate all direct and transitive dependencies with name, version, and SPDX license identifier.

**Operational SLOs**

11. THE project SHALL define and publish Service Level Objectives covering: request success rate ≥ 99.9% over any 1-hour window, P95 processing overhead ≤ 100ms for prompts ≤ 1,000 words, fail-secure event rate ≤ 0.1% of total requests over any 24-hour window, and audit log write success rate ≥ 99.99% over any 24-hour window.

12. THE project SHALL document operational procedures for: upgrading to a new version (with rollback steps), backing up and restoring tenant configuration, responding to a fail-secure alert storm, and rotating all secrets.

**Configuration Change Audit Trail**

13. THE Gateway SHALL maintain a complete, append-only audit trail of all administrative configuration changes, recording for each change: `timestamp`, `operator_id`, `tenant_id`, `change_type` (one of `compliance_preset_updated`, `recognizer_added`, `recognizer_removed`, `exclusion_list_updated`, `provider_config_updated`), `previous_value_hash` (SHA-256 of the previous configuration value, not the value itself), and `new_value_hash`.

14. THE Gateway SHALL expose a `GET /v1/admin/audit/config-history` endpoint (requiring `security_officer` or `administrator` role) that returns paginated configuration change history filterable by `tenant_id`, `change_type`, and time range, enabling export for regulatory review.

**Legal and Regulatory Positioning**

15. THE Gateway SHALL include documentation in `docs/legal/data-sovereignty.md` describing how its self-hosted, perimeter-contained architecture reduces cross-border data-transfer exposure under GDPR Chapter V and the US CLOUD Act. The documentation SHALL include a disclaimer stating that it does not constitute legal advice and that organizations should obtain jurisdiction-specific legal counsel before making compliance determinations.

---

## Traceability Matrix

| Req ID | Title | Primary Persona | Regulatory Framework(s) | Tier |
|--------|-------|-----------------|------------------------|------|
| Req 1 | Core Anonymization Pipeline (Non-Streaming) | Enterprise Developer | GDPR, HIPAA | Core |
| Req 2 | Fail-Secure Architecture | Chief Information Security Officer | GDPR, ISO 27001 | Core |
| Req 3 | Hybrid PII Detection Engine | Data Protection Officer | GDPR, HIPAA, LGPD | Core |
| Req 4 | Context-Preserving Tokenization | Enterprise Developer | GDPR, HIPAA | Core |
| Req 5 | Ephemeral Mapping Store | Security Architect | GDPR, ISO 27001 | Core |
| Req 6 | SSE Streaming Support | Enterprise Developer | — | Core |
| Req 7 | Multi-Provider LLM Support | Infrastructure Engineer | — | Core |
| Req 8 | Multilingual PII Detection | Compliance Officer | GDPR, LGPD, PDPA, POPIA, Privacy Act (AU), PIPEDA | Global |
| Req 9 | Per-Jurisdiction Compliance Presets | Legal Counsel | GDPR, LGPD, PDPA, POPIA, Privacy Act (AU), PIPEDA | Global |
| Req 10 | Metadata-Only Audit Logging | Data Protection Officer | GDPR, HIPAA, ISO 27001 | Global |
| Req 11 | Custom Detection Rules and Exclusion Lists | Platform Engineer | GDPR, ISO 27001 | Global |
| Req 12 | Docker Compose Deployment | DevOps Engineer | — | Core |
| Req 13 | Response-Side Token Verification | Compliance Officer | GDPR, ISO 27001 | Core |
| Req 14 | Commercial Open-Source Positioning | Investor | — | Core |
| Req 15 | Developer Experience and Multilingual Documentation | Developer | — | Global |
| Req 16 | Anonymization Correctness Properties | Principal Engineer | GDPR, ISO 27001 | Core |
| Req 17 | Enterprise Authentication and Authorization | Security Administrator | ISO 27001, DORA, NIS2 | Enterprise |
| Req 18 | Secrets Management and Network Security | CISO | ISO 27001, DORA, NIS2 | Enterprise |
| Req 19 | Multi-Tenant Isolation and Governance | Platform Owner | GDPR, ISO 27001, ISO 42001 | Enterprise |
| Req 20 | High Availability, Scalability, and Disaster Recovery | Infrastructure Architect | DORA, ISO 27001, NIS2 | Enterprise |
| Req 21 | Data Sovereignty, Compliance Assurance, and Detection Quality | Compliance Leader | GDPR, LGPD, PDPA, POPIA, Privacy Act (AU), PIPEDA, HIPAA, EU AI Act | Enterprise |
