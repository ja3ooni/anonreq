# Codebase Structure

**Analysis Date:** 2026-07-06

## Directory Layout

```
annon/                              # Project root
├── src/                            # Source code
│   └── anonreq/                    # Python package (AnonReq Gateway)
│       ├── main.py                 # FastAPI app factory + entrypoint
│       ├── __about__.py            # Package version
│       ├── config/                 # Pydantic settings + env config
│       ├── core/                   # Core configuration (early Settings)
│       ├── exceptions.py           # Custom exception hierarchy + handlers
│       ├── dependencies.py         # FastAPI DI: auth, request context
│       ├── logging_config.py       # Structured JSON logging setup
│       ├── startup_checks.py       # Pre-flight dependency validation
│       ├── health.py               # /health + /health/ready endpoints
│       ├── models/                 # Pydantic models + dataclasses
│       ├── routing/                # Route handlers (chat completions)
│       ├── pipeline/               # Pipeline orchestration + stages
│       ├── detection/              # PII detection engine (regex + Presidio)
│       ├── tokenization/           # PII→token replacement
│       ├── restore/                # Token→original restoration
│       ├── streaming/              # SSE streaming with TailBuffer
│       ├── providers/              # LLM provider adapters
│       ├── cache/                  # Valkey/Redis cache manager
│       ├── proxy/                  # Proxy modes, MITM, TLS, PAC
│       ├── gateway/                # Gateway status, passthrough, routing
│       ├── policy/                 # Enterprise policy (PDP/PEP)
│       ├── governance/             # AI governance, approvals, supplier mgmt
│       ├── compliance/             # Compliance preset engine
│       ├── services/               # Domain services (audit chain, SLO, etc.)
│       ├── admin/                  # Admin API routes + hot-reload
│       ├── routes/                 # API route definitions
│       ├── api/                    # Versioned API routes
│       ├── middleware/              # FastAPI middleware
│       ├── monitoring/             # Prometheus metrics + middleware
│       ├── classification/         # Data classification engine
│       ├── firewall/               # AI firewall, injection detection, DLP
│       ├── locale/                 # Locale bundles, negotiator, checksum
│       ├── soc/                    # SOC integration, SIEM sinks
│       ├── discovery/              # AI traffic discovery, flow analysis
│       ├── agent/                  # Agent MCP inspection, schema
│       ├── mcp/                    # MCP protocol inspector + parser
│       ├── multimodal/             # Image/file content analysis
│       ├── voice/                  # Voice sanitization pipeline
│       ├── incidents/              # Incident classification
│       ├── breach/                 # Breach notification templates
│       ├── dsar/                   # DSAR workflow, erasure, restriction
│       ├── casb/                   # CASB engine + classifier
│       ├── ediscovery/             # E-discovery export formats
│       ├── retention/              # Retention tiers + legal hold
│       ├── lineage/                # Data lineage tracking
│       ├── fairness/               # Fairness evaluation + monitoring
│       ├── storage/                # Object storage (MinIO)
│       ├── deployment/             # Deployment mode config
│       ├── endpoint/               # Endpoint agent + discovery
│       ├── appliance/              # Appliance agent
│       └── verification/           # Verification scanner + stages
│
├── tests/                          # Test suite
│   ├── conftest.py                 # Shared fixtures (env vars, cache, etc.)
│   ├── hypothesis_strategies.py    # Hypothesis strategies for PBT
│   ├── policy/                     # Policy engine tests
│   ├── restore/                    # Restoration tests
│   ├── admin/                      # Admin route tests
│   ├── discovery/                  # Discovery tests
│   ├── unit/                       # Unit tests
│   ├── integration/                # Integration tests
│   ├── load/                       # Load tests
│   ├── property/                   # Property-based tests
│   ├── firewall/                   # Firewall tests
│   ├── casb/                       # CASB tests
│   ├── rag/                        # RAG tests
│   ├── multimodal/                 # Multimodal tests
│   ├── endpoint/                   # Endpoint tests
│   ├── test_*.py                   # Module-level test files (flat)
│   └── __init__.py
│
├── config/                         # YAML configuration files
│   ├── policy.yaml                 # Policy configuration
│   ├── policy.example.yaml         # Policy config example
│   ├── providers.yaml              # Provider capability registry
│   ├── classification.yaml         # Classification rules
│   ├── dlp.yaml                    # DLP rules
│   ├── slo.yaml                    # SLO definitions
│   ├── audit.yaml                  # Audit configuration
│   ├── webhook.yaml                # Webhook configuration
│   ├── export.yaml                 # Export configuration
│   ├── multimodall.yaml            # Multimodal config
│   ├── capabilities.yaml           # Capability flags
│   ├── fairness.yaml               # Fairness config
│   ├── model_aliases.yaml          # Model alias definitions
│   ├── restricted_names.yaml       # Tenant restricted names
│   ├── mnpi_recognizers.yaml       # MNPI recognizer config
│   ├── mitre-mapping.yaml          # MITRE ATT&CK mapping
│   ├── mitre_atlas.yaml            # MITRE ATLAS mapping
│   ├── prompt-security-rules.yaml  # Prompt security rules
│   ├── prompt-security-rules.example.yaml
│   ├── soc-sinks.yaml              # SIEM sink definitions
│   ├── financial_crime_words.yaml  # Financial crime keywords
│   ├── locales/                    # Locale-specific recognizer bundles
│   │   ├── en.yaml                 # English (universal base)
│   │   ├── de-DE.yaml              # German
│   │   ├── fr-FR.yaml              # French
│   │   ├── es.yaml                 # Spanish
│   │   ├── it-IT.yaml              # Italian
│   │   ├── nl-NL.yaml              # Dutch
│   │   ├── pt-BR.yaml              # Portuguese (Brazil)
│   │   └── ar.yaml                 # Arabic
│   ├── compliance/                 # Compliance preset configs
│   │   ├── gdpr.yaml
│   │   ├── popia.yaml
│   │   ├── pdpa.yaml
│   │   ├── lgpd.yaml
│   │   ├── pipeda.yaml
│   │   └── privacy_act.yaml
│   └── policies/                   # Policy definitions
│       └── default.yaml
│
├── docker/                         # Docker/observability configs
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── rules/
│   │       └── slo_alerts.yml
│   └── grafana/
│       ├── datasources/
│       │   └── prometheus.yml
│       └── dashboards/
│
├── alembic/                        # Database migrations
├── docs/                           # Multi-language documentation
│   ├── en/                         # English docs
│   ├── de/                         # German docs
│   ├── architecture/               # Architecture docs
│   ├── operations/                 # Operations runbooks
│   ├── compliance/                 # Compliance mappings
│   └── security/                   # Security docs
│
├── req/                            # Requirements specifications
│   ├── requirements.md             # Core requirements (Req 1–21)
│   ├── requirements_v2.md          # Enterprise requirements (Req 22–56)
│   ├── HLD.md                      # High-level design
│   ├── ROADMAP.md                  # Project roadmap
│   ├── roadmap2.md                 # Roadmap v2
│   ├── roadmap3.md                 # Roadmap v3
│   ├── GTM-CURRENT.md              # Go-to-market strategy
│   ├── abbreviations.md            # Abbreviations glossary
│   └── v3/, v4/                    # Future requirement iterations
│
├── phases/                         # Implementation phase artifacts
│   ├── 10-*-*/                     # Phase directories (numbered)
│   ├── 11-*-*/
│   ├── 13-*-*/
│   ├── 15-*-*/
│   ├── 17-*-*/
│   ├── 18-*-*/
│   ├── 19-*-*/
│   └── 21-*-*/
│
├── openapi/                        # OpenAPI specification
│   └── openapi.yaml
│
├── scripts/                        # Utility scripts
├── systemd/                        # Systemd service files
│
├── pyproject.toml                  # Python project config + deps
├── requirements.txt                # Pinned production deps
├── requirements-dev.txt            # Dev dependencies
├── uv.lock                         # UV lockfile
├── Dockerfile                      # Multi-stage Docker build
├── docker-compose.yml              # Docker Compose orchestration
├── alembic.ini                     # Alembic migration config
├── .env.example                    # Example environment variables
├── .env                            # Local environment (git-ignored)
├── AGENTS.md                       # Agent instructions
├── CLAUDE.md                       # Claude project rules
├── SECURITY.md                     # Security policy
└── README.md                       # Project README
```

## Directory Purposes

**`src/anonreq/` — Application Package:**
- Purpose: All gateway source code
- Contains: FastAPI app factory, pipeline stages, domain services, API routes, models
- Key files: `main.py` (app factory + entrypoint), `exceptions.py` (error hierarchy), `dependencies.py` (auth DI), `logging_config.py` (structured logging)

**`src/anonreq/pipeline/` — Pipeline Orchestration:**
- Purpose: Sequential stage execution framework + all pipeline stage implementations
- Contains: `PipelineManager`, `PipelineStage` abstract base, 10+ concrete stages
- Key files: `manager.py` (orchestrator), `base.py` (abstract base), `detection.py`, `tokenization.py`, `provider.py`, `restoration.py`, `cleanup.py`, `classification.py`, `stages.py`, `extraction.py`, `forwarding_guard.py`

**`src/anonreq/models/` — Data Models:**
- Purpose: Pydantic models and dataclasses for request/response, processing context, detection results, DLP
- Contains: Chat request/response models, ProcessingContext, RequestContext, DetectionResult, TokenMapping, DLPResult
- Key files: `chat.py` (OpenAI-compatible schema), `processing_context.py` (pipeline state), `request_context.py` (auth context)

**`src/anonreq/detection/` — PII Detection:**
- Purpose: Regex + Presidio NER detection pipeline, span arbitration, MNPI
- Contains: Regex patterns, Presidio HTTP client, span arbiter, exclusion list, context booster, MNPI recognizers
- Key files: `regex_detector.py`, `presidio_client.py`, `span_arbiter.py`, `pipeline.py` (MNPI loading + boosting)

**`src/anonreq/providers/` — LLM Provider Adapters:**
- Purpose: Provider-specific request/response translation
- Contains: OpenAI, Anthropic, Gemini, Ollama adapters, registry, capabilities
- Key files: `adapter.py` (base), `openai.py`, `anthropic.py`, `gemini.py`, `ollama.py`, `registry.py`

**`src/anonreq/policy/` — Enterprise Policy Engine:**
- Purpose: PDP/PEP for rate limits, spend control, residency routing
- Contains: PolicyDecisionPoint, PolicyEnforcementPoint, UsageLimiter, SpendController, ResidencyRouter, ForwardingGuard, store, audit, evidence
- Key files: `pdp.py`, `pep.py`, `usage_limiter.py`, `spend_controller.py`, `residency_router.py`, `config.py`, `store.py`

**`src/anonreq/services/` — Domain Services:**
- Purpose: Long-lived business logic services
- Contains: AuditChainService, SLOEngine, BreachDetector, OversightService, LifecycleService, TransparencyService, NotificationService, ClassificationService, DLPEngine, ExfiltrationDetector, Pipeline, AuditExporter
- Key files: `audit_chain.py`, `slo_engine.py`, `breach_detector.py`, `oversight.py`, `lifecycle.py`,

**`src/anonreq/firewall/` — AI Security Firewall:**
- Purpose: Injection detection, jailbreak detection, DLP, streaming inspection
- Contains: FirewallPipeline, Classifier, InjectionScorer, JailbreakDB, ML model, Gates, Rules, Override detector
- Key files: `pipeline.py`, `classifier.py`, `engine.py`, `injection_scorer.py`, `jailbreak_db.py`

**`src/anonreq/governance/` — AI Governance:**
- Purpose: Tool call governance, approvals, model/provider inventory, supplier management, risk assessment
- Contains: ApprovalManager, ToolExtractor, ToolInspector, PDP tool evaluator, ModelInventory, ProviderInventory, Supplier, Risk, Records, Reports, Reviews
- Key files: `approval.py`, `tool_extractor.py`, `tool_inspector.py`, `pdp_tool_evaluator.py`, `model_inventory.py`, `provider_inventory.py`, `router.py`

**`src/anonreq/proxy/` — Proxy Infrastructure:**
- Purpose: Proxy modes, MITM TLS interception, CA management, PAC generation, transparent/reverse proxy
- Contains: ProxyMode enum, TLSInterceptor, MITMHandler, CAManager, PACGenerator, ReverseProxy, TransparentProxy
- Key files: `modes.py`, `mitm_handler.py`, `tls_interceptor.py`, `ca_manager.py`, `pac.py`, `reverse_proxy.py`, `transparent_proxy.py`

**`src/anonreq/locale/` — Locale Support:**
- Purpose: Multi-locale PII detection with locale-specific recognizer bundles
- Contains: LocaleRegistry, LocaleNegotiator, RecognizerMerger, ChecksumValidatorRegistry, locale bundles
- Key files: `registry.py`, `negotiator.py`, `merger.py`, `checksum.py`, `bundle.py`

**`tests/` — Test Suite:**
- Purpose: All tests organized by domain
- Contains: 150+ test files covering unit, integration, property-based, and load tests
- Key files: `conftest.py` (shared fixtures), `hypothesis_strategies.py` (PBT strategies), sub-packages for domain-specific test groups

**`config/` — Runtime Configuration:**
- Purpose: YAML configuration files loaded at startup and hot-reloaded at runtime
- Contains: Policy definitions, compliance presets, locale bundles, provider registry, DLP rules, alerting configs
- Key files: `policy.yaml`, `providers.yaml`, `classification.yaml`, `locales/en.yaml` (universal base)

## Key File Locations

**Entry Points:**
- `src/anonreq/main.py:667` — Module-level `app = create_app()` for uvicorn
- `src/anonreq/main.py:152` — `create_app()` factory function
- `Dockerfile:76` — `CMD ["uvicorn", "anonreq.main:app", ...]`

**Configuration:**
- `src/anonreq/config/__init__.py` — `Settings` class (env vars), `settings` singleton
- `src/anonreq/core/config.py` — Legacy/alternative Settings class
- `config/policy.yaml` — Runtime policy configuration
- `config/providers.yaml` — Provider capability registry
- `config/classification.yaml` — Classification rule definitions
- `config/locales/en.yaml` — Universal locale recognizer bundle
- `.env.example` — Environment variable template

**Core Logic:**
- `src/anonreq/routing/chat.py` — `POST /v1/chat/completions` handler
- `src/anonreq/pipeline/manager.py` — `PipelineManager.run()` orchestrator
- `src/anonreq/detection/pipeline.py` — MNPI loading + context boosting bridge
- `src/anonreq/detection/presidio_client.py` — Presidio HTTP client
- `src/anonreq/policy/pdp.py` — Policy Decision Point
- `src/anonreq/providers/registry.py` — Provider registry
- `src/anonreq/streaming/tail_buffer.py` — Tail buffer for split-token restoration
- `src/anonreq/streaming/restoration.py` — Streaming token restoration
- `src/anonreq/tokenization/tokenizer.py` — PII→token replacement
- `src/anonreq/restore/engine.py` — Token→original restoration

**Testing:**
- `tests/conftest.py` — Shared fixtures (env vars, fakeredis, sample data)
- `tests/hypothesis_strategies.py` — Hypothesis strategies for property-based tests
- `tests/policy/test_property.py` — Property-based policy tests
- `tests/test_gateway_property.py` — Property-based gateway tests
- `tests/test_roundtrip.py` — Round-trip anonymize→restore tests
- `tests/test_compliance_property.py` — Compliance property tests

**Configuration (YAML):**
- `config/policy.yaml` — Runtime policy rules
- `config/providers.yaml` — Provider capability registry
- `config/classification.yaml` — Data classification rules
- `config/locales/en.yaml` — Universal locale bundle

## Naming Conventions

**Files:**
- Python: `snake_case.py` — all source files (e.g., `processing_context.py`, `span_arbiter.py`)
- Configuration: `kebab-case.yaml` — YAML config files (e.g., `model-aliases.yaml`, `prompt-security-rules.yaml`)
- Test files: `test_*.py` — flat namespace under `tests/` (e.g., `test_detection.py`, `test_pipeline.py`)
- Test subdirectories: domain-name matching package (e.g., `tests/policy/`, `tests/restore/`)

**Functions:**
- `snake_case()` — all functions and methods (e.g., `build_pipeline()`, `raise_for_pipeline_errors()`, `run_startup_checks()`)
- Leading underscore for private/internal (e.g., `_raise_for_pipeline_errors()`, `_stream_chat_completions()`)
- Async prefix not used — functions are async if awaited

**Variables:**
- `snake_case` — all variables (e.g., `proc_ctx`, `cache_manager`, `presidio_client`)
- Descriptive names preferred — abbreviations only when well-known (`ctx`, `pdp`, `pep`)

**Types:**
- `PascalCase` for classes (e.g., `PipelineManager`, `ProcessingContext`, `PolicyDecisionPoint`, `StreamingRestorationStage`)
- `PascalCase` for dataclasses (e.g., `ProcessingContext`, `RequestContext`, `ChatRequest`)
- `UPPER_CASE` for constants (e.g., `ALLOWLIST`, `DEFAULT_ALLOWED_PROVIDERS`, `PROXY_ONLY_STAGES`)

**Directories:**
- `snake_case` — all subdirectories under `src/anonreq/` (e.g., `detection/`, `tokenization/`, `proxy/`, `providers/`)
- Glob-style phase names: `{number}-{kebab-description}/` under `phases/` (e.g., `13-ai-firewall-data-loss-prevention/`)

## Where to Add New Code

**New Feature (e.g., new pipeline stage):**
- Primary code: `src/anonreq/pipeline/{feature_name}.py` — new `PipelineStage` subclass
- Pipeline registration: `src/anonreq/routing/chat.py` — add to `build_pre_provider_pipeline()` or `build_pipeline()`
- Models: `src/anonreq/models/{feature_name}.py` or add fields to `ProcessingContext`
- Tests: `tests/test_{feature_name}.py`

**New Provider Adapter:**
- Implementation: `src/anonreq/providers/{provider_name}.py` — subclass `ProviderAdapter`
- Registry: `src/anonreq/providers/registry.py` — register in `ProviderRegistry`
- Config: `config/providers.yaml` — add provider capability entry
- Tests: `tests/test_{provider_name}_adapter.py`

**New API Route:**
- Route file: `src/anonreq/routes/{feature_name}.py` or `src/anonreq/admin/{feature_name}_routes.py`
- Router registration: `src/anonreq/main.py` — `app.include_router()`
- Auth: Use `Depends(auth_context)` for protected routes
- Tests: `tests/test_{feature_name}.py`

**New Domain Service:**
- Implementation: `src/anonreq/services/{feature_name}.py` — service class with async methods
- Lifespan initialization: `src/anonreq/main.py` — create and store on `app.state`
- Tests: `tests/test_{feature_name}.py`

**New YAML Config:**
- File: `config/{feature_name}.yaml`
- Loading: Create loader function in appropriate module
- Hot-reload: Integrate with admin config registry if needed (`src/anonreq/admin/config.py`)

**New Detection Recognizer:**
- Implementation: `src/anonreq/detection/recognizers/{feature_name}.py`
- Registration: Add to `load_mnpi_recognizers()` in `src/anonreq/detection/pipeline.py`
- Config: `config/mnpi_recognizers.yaml`
- Locale: Add to locale-specific bundle in `config/locales/{code}.yaml`

**Tests:**
- Flat test file: `tests/test_{module_name}.py` for standalone modules
- Subpackage: `tests/{domain}/` for domain groups with multiple test files
- Shared fixtures: `tests/conftest.py`
- Hypothesis strategies: `tests/hypothesis_strategies.py`

## Special Directories

**`alembic/`:**
- Purpose: Database migration scripts for audit chain PostgreSQL
- Generated: Yes (by Alembic)
- Committed: Yes

**`phases/`:**
- Purpose: Implementation phase artifacts (task breakdowns, architecture docs, test plans, discussion logs)
- Generated: Yes (by GSD workflow)
- Committed: Yes

**`docs/`:**
- Purpose: User-facing and operations documentation (multi-language)
- Generated: No
- Committed: Yes

**`config/locales/`:**
- Purpose: Locale-specific PII recognizer bundles (8 locales)
- Generated: Partially (checksums generated at build)
- Committed: Yes

**`.hypothesis/`:**
- Purpose: Hypothesis test example database (cached test cases)
- Generated: Yes (by Hypothesis)
- Committed: No (in `.gitignore`)

**`.venv/`:**
- Purpose: Python virtual environment
- Generated: Yes (by uv/pip)
- Committed: No (in `.gitignore`)

---

*Structure analysis: 2026-07-06*
