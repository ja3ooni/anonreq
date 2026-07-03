# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Initial project scaffolding

## [0.1.0] - 2026-06-19

### Added

- Docker Compose setup with anonreq, presidio-analyzer, and valkey containers
- Static bearer token authentication with key length validation
- Fail-secure global exception handler returning static HTTP 500
- Structured JSON audit logging with field allowlist
- Pre-flight health checks for Valkey and Presilio dependencies
- PII detection pipeline (regex + NER via Microsoft Presidio Analyzer)
- Tokenization engine with deduplication and reverse-offset replacement
- Restoration engine with case-insensitive, bracket-optional matching
- Cache Manager with Valkey (ephemeral, TTL-based, DEL post-response)
- SSE streaming with Tail_Buffer FSM for split-token handling
- Multi-provider support for Anthropic Claude, Google Gemini, and Ollama
- Model alias routing and GET /v1/models endpoint
- Multi-locale detection with 8 locales and locale-specific recognizer bundles
- Checksum validation for national IDs (Steuer-ID, BSN, NIR, CPF, CNPJ, Codice Fiscale)
- 6 compliance presets (GDPR, LGPD, PDPA, POPIA, Privacy Act AU, PIPEDA)
- Prometheus metrics endpoint with request counts, detection latency, entity counters
- Post-restoration residual token verification scan
- Custom detection rules API with hot-reload
- Property-based test suite (fail-secure, no-PII-in-logs, cross-request randomization, locale checksum)
- Classification engine (4 tiers: Block, Route Local, Anonymize, Pass) with YAML rules

### Security

- Fail-secure architecture: ForwardingGuard requires signed SanitizedEnvelope before upstream calls
- No-PII-in-logs enforcement via structlog field allowlist
- Ephemeral cache: Valkey with `save ""`, no RDB/AOF
- Cross-session token randomization with P(duplicate) ≤ 2⁻³²

## [0.1.1] - 2026-06-20

### Added

- Developer documentation (EN and DE)
- Executable quickstart scripts for gateway startup, anonymization test, and cleanup
- SDK examples for curl, Python, TypeScript, and Go (4 use cases each)
- Apache 2.0 LICENSE file
- NOTICE file with third-party attribution notices
- SECURITY.md with vulnerability disclosure policy
- Comprehensive README.md with 13 sections
- Documentation CI pipeline (markdown lint, link check, Mermaid validation, OpenAPI sync)
