# AnonReq Master Data Flow

## Sensitive Data Classes

Raw prompts, raw responses, original entity values, token mappings, tool outputs, RAG chunks, transcript text, and audio frames are sensitive runtime data. Tokens are also sensitive because they reveal anonymization structure and must not be logged. Durable records use counts, hashes, classifications, policy action codes, provider identifiers, timestamps, and HMAC tags.

## Non-Streaming Flow

Client request enters Gateway, receives tenant/principal context, passes schema validation, is evaluated by Policy Engine, scanned by Detection Engine, tokenized, mapped into Valkey, forwarded by ForwardingGuard, restored, output-scanned, audited, and cleaned up. Mapping deletion is attempted within 100ms after response write; TTL is fallback.

## Streaming Flow

The Mapping is prefetched with one `HGETALL` before stream restoration. The Restoration Engine uses a bounded Tail_Buffer for split tokens and flushes on terminal event, timeout, or chunk threshold. Mapping TTL is extended at 80 percent of configured TTL during long streams and deleted after `[DONE]` or connection close.

## Durable Metadata Flow

Audit, lineage, governance, risk, incident, compliance, and retention records flow to PostgreSQL or append-only evidence storage. Records are tenant-scoped and never include raw values. Exports are JSONL or ZIP packages with SHA-256 manifests.
