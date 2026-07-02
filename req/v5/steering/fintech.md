---
title: Financial Data & Precision Standards
inclusion: always
---

# Financial Data & Precision Standards

## Currency and Amounts
- **No Floating Point:** Never use `float` or `double` for monetary values. Use arbitrary-precision decimals.
  - **Python:** Use the `decimal.Decimal` class. Always pass strings to the constructor, e.g., `Decimal("100.05")`.
  - **Go:** Use `shopspring/decimal` or `math/big`.
  - **PostgreSQL:** Use the `NUMERIC` type with explicit scale/precision (e.g., `NUMERIC(20, 4)`).
- **ISO 4217:** Always store currency codes as standard 3-letter strings (e.g., "EUR", "USD").

## Rounding Rules
- Default to **Banker's Rounding** (Round Half to Even) unless the specific regulatory reporting standard (e.g., EBA/ECB) mandates otherwise.
- Explicitly document the rounding strategy for all interest calculations and fee distributions.

## Temporal Accuracy
- Use **UTC** for all database timestamps.
- Maintain microsecond precision for transaction "Effective Dates" to ensure correct ordering in high-frequency scenarios.
- Use ISO 8601 format for all API date-time responses.

## Auditable Types
- When defining Pydantic models or Go structs, ensure `amount` fields are distinct from `currency` fields.
- Prefer a "Money" composite object: `{ "amount": "1250.00", "currency": "EUR" }`.
```

### 2. ISO 20022 Messaging Best Practices
Since your project relies on ISO 20022 (pain.001, pacs.008), this document enforces strict schema adherence and message validation.

```diff
---
title: ISO 20022 Messaging Best Practices
inclusion: fileMatch
fileMatchPattern: '**/ingestion/**,**/reporting/**,*.xml,*.xsd'
---

# ISO 20022 Messaging Best Practices

## Schema Validation
- All inbound messages (e.g., `pacs.008`) must be validated against the official XSD schema before reaching the business logic layer.
- Use a "Schema Registry" approach to manage different versions of the ISO 20022 standard.

## Message Integrity
- Store the **Raw XML** blob in the database (or S3) for audit purposes, even after parsing it into internal JSON/Protobuf models.
- Maintain the `MsgId` (Message Identification) and `CreDtTm` (Creation Date Time) throughout the processing lifecycle for traceability.

## Error Handling
- Map XSD validation errors to standard ISO 20022 error codes (e.g., `RC01` for invalid format).
- Ensure error messages do not leak PII (Personally Identifiable Information) but provide enough context for a Compliance Officer to troubleshoot.

## Transformations
- When converting ISO 20022 XML to internal models, use strictly typed mapping functions. 
- Avoid generic dictionary/map-based parsing to prevent missing mandatory tags like `Dbtr` (Debtor) or `Cdtr` (Creditor).
```

### 3. Idempotency & Transaction Safety
This document prevents the "Double Spend" or "Double Reporting" problem by enforcing idempotency across the platform.

```diff
---
title: Idempotency & Transaction Safety
inclusion: fileMatch
fileMatchPattern: '**/api/**,**/services/**,**/v1/**'
---

# Idempotency & Transaction Safety

## API Level
- All POST requests that result in a state change (e.g., `/v1/transactions`, `/v1/reports/sar`) **must** support the `Idempotency-Key` header.
- Use Redis to store idempotency keys with a TTL of 24 hours.
- If a request is retried with the same key, return the original response (cached) rather than re-processing.

## Kafka / Flink Level
- Implement **Exactly-Once Semantics (EOS)** in the Flink pipeline.
- Use the `transaction_id` + `tenant_id` as the unique key for deduplication in downstream consumers.
- Background jobs (like SAR generation) must be re-entrant and check for existing records before creating new ones.

## Database Transactions
- Wrap money movements and case status updates in explicit database transactions.
- Use `SELECT ... FOR UPDATE` or Optimistic Concurrency Control (OCC) with version columns to prevent race conditions during concurrent reviews.

## Error Recovery
- On failure, use **Idempotent Retries**. Never retry a non-idempotent operation without a unique client-generated key.
```

### 4. DORA & Operational Resilience
Aligned with the **Digital Operational Resilience Act**, this document focuses on how the code should handle failures and reporting.

```diff
---
title: DORA Resilience Standards
inclusion: always
---

# DORA Resilience Standards

## Fault Tolerance
- **Circuit Breakers:** All outbound calls to third-party APIs (Sanctions providers, Regulators) must use circuit breakers to prevent cascading failures.
- **Timeouts:** Enforce aggressive timeouts on all external integrations. No external call should block a request for more than 5 seconds.

## Incident Classification
- Every service error that impacts "Critical or Important Functions" (as defined in DORA) must emit a specialized `ICT_INCIDENT` log event.
- These logs must include: `impact_duration`, `affected_tenants`, and `severity_level`.

## Graceful Degradation
- If the AI Risk Scorer is down, the platform must fail-over to a "Static Rules" monitoring mode rather than stopping transaction ingestion.
- Inform the `Compliance_Officer` via the dashboard when the platform is running in degraded mode.

## Business Continuity
- Ensure stateful services (PostgreSQL/Kafka) have Cross-Region Replication (CRR) configured, but validate that CRR destinations do not violate **Data Sovereignty** policies.
- Automate the generation of DORA-compliant incident reports when the "Recovery Time Objective" (RTO) is breached.
```

These documents provide the necessary guardrails for building a robust, compliant fintech platform. Gemini will now proactively warn you if it sees floating-point math for money or missing idempotency logic in your APIs.

<!--
[PROMPT_SUGGESTION]Check the Transaction Ingestion Service in Go to see if it properly implements the new Idempotency and ISO 20022 best practices.[/PROMPT_SUGGESTION]
[PROMPT_SUGGESTION]Help me write a Python Pydantic model for a transaction that uses the new Financial Data standards.[/PROMPT_SUGGESTION]
