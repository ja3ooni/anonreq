# AnonReq Abbreviations & Glossary

## Core Abbreviations
- **PII**: Personally Identifiable Information
- **PHI**: Protected Health Information
- **NER**: Named Entity Recognition
- **mTLS**: Mutual Transport Layer Security
- **SSE**: Server-Sent Events
- **TTL**: Time-to-live
- **RBAC**: Role-Based Access Control

## Enterprise & Regulatory Abbreviations
- **MNPI**: Material Non-Public Information
- **MCP**: Model Context Protocol
- **MRM**: Model Risk Management
- **DORA**: Digital Operational Resilience Act
- **NIS2**: Network and Information Security Directive 2
- **RAG**: Retrieval-Augmented Generation
- **CASB**: Cloud Access Security Broker
- **SOC**: Security Operations Center

## Key System Components
- **Gateway**: The main FastAPI proxy service intercepting traffic.
- **Detection_Engine**: Hybrid regex and NER pipeline for identifying sensitive data.
- **Tokenization_Engine**: Replaces entity spans with placeholder tokens (e.g. `[TYPE_1]`).
- **Restoration_Engine**: Restores tokens back to original values in the response.
- **Cache_Manager**: Ephemeral in-memory store (Valkey/Redis) for mappings.
- **Provider_Adapter**: Format translation layer for upstream APIs (OpenAI, Anthropic, Gemini, etc.).
- **Audit_Logger**: Emits metadata-only structured logs.
