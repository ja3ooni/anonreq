# Frequently Asked Questions

## What happens when PII detection fails?

The gateway fails secure. If detection, cache, or provider timeout errors occur, the request returns HTTP 5xx and zero data is forwarded upstream. See the fail-secure architecture in the project README for details.

## Is my data persisted anywhere?

No. All PII-to-token mappings are stored in Valkey with no persistence (`save ""`). Mappings are deleted after the response is sent. Logs contain metadata only — no raw PII values.

## Which LLM providers are supported?

OpenAI, Azure OpenAI, Anthropic (Claude), Google Gemini, and Ollama (local models). The gateway translates the OpenAI-compatible request format to each provider's native protocol.

## How does streaming work?

The gateway uses a Tail_Buffer FSM to handle tokens split across SSE chunk boundaries. Tokens are restored in real-time as chunks arrive. The response is byte-for-byte identical to non-streaming mode.

## What is the token format?

Detected PII is replaced with `[TYPE_N]` placeholders, where `TYPE` is the entity type (e.g., `EMAIL`, `PHONE`) and `N` is a unique index. Token matching is case-insensitive and bracket-optional during restoration.

## How are locales handled?

Set the `X-AnonReq-Locale` header to activate locale-specific detection. Multiple locales can be combined (comma-separated). Unsupported locales return HTTP 400.

## Can I add custom detection patterns?

Yes, custom regex recognizers can be added via a YAML configuration file and hot-reloaded without restart. See the configuration documentation for the rule format.

## How do I contribute?

Contributions are welcome under the Apache 2.0 license. See the contributing guide in the repository for pull request guidelines and development setup instructions.
