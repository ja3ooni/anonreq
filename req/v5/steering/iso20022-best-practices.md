---
title: ISO 20022 Messaging Best Practices
inclusion: fileMatch
fileMatchPattern: '**/ingestion/**,**/reporting/**,*.xml,*.xsd,**/pacs.*,**/pain.*'
---

# ISO 20022 Messaging Best Practices

## Schema & Validation
- **Strict XSD Validation:** All inbound messages must be validated against the official ISO 20022 XSD before any processing. Use a schema registry for versioning (e.g., pacs.008.001.08).
- **Namespace Awareness:** Ensure XML parsers are configured to be namespace-aware to handle different versions of the standard correctly.

## Data Integrity & Precision
- **Raw Message Preservation:** Always store the original, unmodified XML blob for audit and non-repudiation purposes.
- **Decimal Precision:** Map all `Amount` fields to arbitrary-precision decimals. Floating-point types are strictly forbidden.
- **ISO 4217 Compliance:** Validate currency codes against the ISO 4217 3-letter standard.

## Traceability
- **Identifier Mapping:** Explicitly extract and store the following identifiers:
  - `MsgId`: Message Identification (Group Header)
  - `EndToEndId`: End-to-End Identification (Transaction Level)
  - `UETR`: Unique End-to-End Transaction Reference (if present)
  - `InstrId`: Instruction Identification

## Transformation Logic
- **Typed Mapping:** Use strictly typed structs/models for transformation. Avoid generic map-based parsing.
- **Business Rule Validation:** Beyond schema validation, implement "External Code List" validation for purpose codes, category purposes, and charge bearings.

## Error Handling (Status Reports)
- **Standard Status Codes:** When generating Payment Status Reports (e.g., `pain.002`), use standard status reason codes (e.g., `RJCT`, `ACCP`, `ACSP`).
- **PII Redaction in Logs:** Ensure that while the raw XML is stored securely, application logs do not leak PII from tags like `<Nm>` (Name) or `<AdrLine>` (Address).

## Performance
- **Streaming for Large Files:** For large batch files (e.g., `pain.001` with thousands of entries), use SAX or StAX (streaming) parsers instead of DOM to minimize memory footprint.