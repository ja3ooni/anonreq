# Codebase Structure

**Analysis Date:** 2026-07-17

## Directory Layout

```
annon/                              # Project root
├── src/                            # Source code
│   └── anonreq/                    # Python package (AnonReq Gateway)
│       ├── main.py                 # FastAPI app factory + entrypoint
│       ├── state.py                # Typed AppState dataclass for app.state
│       ├── __about__.py            # Package version
│       ├── config/                 # Pydantic settings + env config
│       │   ├── __init__.py         # Settings class + settings singleton
│       │   └── restricted_names.py # Tenant restricted name validation
│       ├── core/                   # Core configuration (early Settings)
│       ├── bootstrap/              # Domain-specific lifespan bootstrappers
│       │   └── services.py         # bootstrap_*() functions for startup
│       ├── auth/                   # OIDC authentication
│       │   ├── __init__.py         # Auth exports
│       │   └── oidc.py             # OIDCVerifier, JWKS cache, token validation
│       ├── exceptions.py           # Custom exception hierarchy + handlers
│       ├── dependencies.py         # FastAPI DI: auth, request context
│       ├── logging_config.py       # Structured JSON logging setup
│       ├── startup_checks.py       # Pre-flight dependency validation
│       ├── health.py               # /health + /health/ready endpoints
│       ├── models/                 # Pydantic models + dataclasses
│       ├── routing/                # Route handlers (chat completions)
│       ├── pipeline/               # Pipeline orchestration + stages
│       ├── detection/              # PII detection engine (regex + Presidio)
│       │   └── recognizers/        # Enterprise + MNPI recognizers
│       ├── tokenization/           # PII→token replacement
│       ├── restore/                # Token→original restoration
│       ├── streaming/              # SSE streaming with TailBuffer
│       ├── providers/              # LLM provider adapters
│       ├── cache/                  # Valkey/Redis cache manager
│       ├── proxy/                  # Proxy modes, MITM, TLS, PAC
│       ├── gateway/                # Gateway status, passthrough, routing
│       ├── policy/                 # Enterprise policy (PDP/PEP)
│       ├── governance/             # AI governance, approvals, supplier mgmt
│       │   └── webhooks/           # AML webhook integration
│       ├── compliance/             # Compliance preset engine
│       ├── services/               # Domain services (audit chain, SLO, etc.)
│       ├── secrets/                # Runtime secret management
│       │   ├── bootstrap.py        # Secret store bootstrap
│       │   ├── reloader.py         # SecretVolumeReloader (hot-reload)
│       │   ├── rotation.py         # SecretRotationBuffer
│       │   └── store.py            # RuntimeSecretStore
│       ├── license/                # HMAC license validation
│       │   ├── config.py           # License config
│       │   ├── models.py           # License models
│       │   ├── router.py           # License API routes
│       │   └── validator.py        # require_license() dependency
│       ├── trust_center/           # Trust Center public portal
│       │   ├── config.py           # TrustCenterSettings
│       │   ├── router.py           # Public compliance portal routes
│       │   ├── schemas.py          # Trust Center response schemas
│       │   └── service.py          # TrustCenterService + rate limiter
│       ├── admin/                  # Admin API routes + hot-reload
│       ├── routes/                 # API route definitions (compliance, governance, models, oversight)
│       ├── api/                    # Versioned API routes
│       │   └── v1/admin/audit.py   # Admin audit API (v1)
│       ├── middleware/              # FastAPI middleware
│       │   ├── classification.py   # X-AnonReq-Classification parsing
│       │   ├── content_type.py     # Content-Type enforcement
│       │   ├── firewall_inbound.py # Inbound firewall middleware
│       │   ├── firewall_outbound.py# Outbound firewall middleware
│       │   ├── mtls.py             # Ingress mTLS middleware
│       │   ├── policy.py           # PDP/PEP middleware
│       │   ├── rbac.py             # RBAC middleware
│       │   └── response_headers.py # Classification response headers
│       ├── monitoring/             # Prometheus metrics + middleware
│       ├── classification/         # Data classification engine
│       ├── firewall/               # AI firewall, injection detection, DLP
│       ├── locale/                 # Locale bundles, negotiator, checksum
│       │   └── checksums/          # Checksum algorithms (Luhn, ISO7064, etc.)
│       ├── soc/                    # SOC integration, SIEM sinks
│       │   └── sinks/              # Sink implementations (Splunk, Elastic, etc.)
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
│       │   └── macos/              # macOS-specific capture
│       ├── appliance/              # Appliance agent
│       ├── rag/                    # RAG governance (ingest, policy, vector)
│       └── verification/           # Verification scanner + stages
│
├── tests/                          # Test suite
│   ├── conftest.py                 # Shared fixtures (env vars, cache, etc.)
│   ├── hypothesis_strategies.py    # Hypothesis strategies for PBT
│   ├── policy/                     # Policy engine tests
│   ├── restore/                    # Restoration tests
│   ├── admin/                      # Admin route tests
│   ├── discovery/                  # Discovery tests
│   ├── unit/                       # Unit tests (structured subdirectories)
│   │   ├── admin/                  # Admin config registry, role normalization
│   │   ├── auth/                   # OIDC JWKS cache tests
│   │   ├── compliance/             # Compliance engine, merge, preset, validation
│   │   ├── detection/              # Enterprise recognizer tests
│   │   ├── license/                # License config, models, router, validator
│   │   ├── locale/                 # Bundle, checksum, merger, negotiator, registry
│   │   ├── middleware/             # mTLS ingress tests
│   │   ├── monitoring/            # Metrics, middleware tests
│   │   ├── providers/             # Provider adapter tests
│   │   ├── routing/               # Alias registry tests
│   │   ├── secrets/               # Secret reloader, bootstrap tests
│   │   ├── services/              # Compliance evidence tests
│   │   ├── streaming/             # Cleanup, emitter, restoration, tail buffer
│   │   └── verification/          # Scanner tests
│   ├── integration/                # Integration tests (27 files)
│   ├── load/                       # Load tests
│   ├── property/                   # Property-based tests
│   ├── firewall/                   # Firewall tests
│   ├── casb/                       # CASB tests
│   ├── rag/                        # RAG tests
│   ├── multimodal/                 # Multimodal tests
│   ├── endpoint/                   # Endpoint tests
│   └── test_*.py                   # Module-level test files (flat, 120+ files)
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
│   ├── multimodal.yaml             # Multimodal config
│   ├── capabilities.yaml           # Capability flags
│   ├── fairness.yaml               # Fairness config
│   ├── model_aliases.yaml          # Model alias definitions
│   ├── restricted_names.yaml       # Tenant restricted names
│   ├── mnpi_recognizers.yaml       # MNPI recognizer config
│   ├── mitre-mapping.yaml          # MITRE ATT&CK mapping
│   ├── mitre_atlas.yaml            # MITRE ATLAS mapping
│   ├── mitre_attack.yaml           # MITRE ATT&CK attack mapping
│   ├── prompt-security-rules.yaml  # Prompt security rules
│   ├── prompt-security-rules.example.yaml
│   ├── soc-sinks.yaml              # SIEM sink definitions
│   ├── financial_crime_words.yaml  # Financial crime keywords
│   ├── enterprise-policy.yaml      # Enterprise policy configuration
│   ├── trust_center.yaml           # Trust Center configuration
│   ├── recognizers.yaml            # Enterprise recognizer config
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
│   ├── en/                         # English docs (8 files)
│   ├── de/                         # German docs
│   ├── fr/                         # French docs
│   ├── es/                         # Spanish docs
│   ├── it/                         # Italian docs
│   ├── nl/                         # Dutch docs
│   ├── pt/                         # Portuguese docs
│   ├── ar/                         # Arabic docs
│   ├── architecture/               # Architecture docs
│   ├── operations/                 # Operations runbooks
│   ├── compliance/                 # Compliance mappings
│   └── security/                   # Security docs
│
├── data/                           # Runtime data directories
│   └── compliance_evidence/        # Generated compliance evidence artifacts
│
├── examples/                       # Quickstarts and examples
│   ├── curl/
│   ├── datasets/
│   ├── go/
│   ├── python/
│   ├── quickstart/
│   └── typescript/
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
│   ├── 08-*/ through 21-*/         # Phase directories (numbered)
│   └── screenshots/                # Phase screenshots
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
├── CHANGELOG.md                    # Project changelog
├── CODE_REVIEW.md                  # Code review findings
├── SECURITY.md                     # Security policy
├── SECURITY_SCAN.md                # Security scan results
├── STATE.md                        # Project state (current milestone)
└── README.md                       # Project README
```

## Directory Purposes

**`src/anonreq/` — Application Package:**
- Purpose: All gateway source code
- Contains: FastAPI app factory, pipeline stages, domain services, API routes, models
- Key files: `main.py` (app factory + entrypoint), `state.py` (typed AppState), `exceptions.py` (error hierarchy), `dependencies.py` (auth DI), `logging_config.py` (structured logging)

**`src/anonreq/bootstrap/` — Lifespan Bootstrappers:**
- Purpose: Domain-specific startup functions called during lifespan
- Contains: `bootstrap_locale_detection()`, `bootstrap_policy_engine()`, `bootstrap_mitm_proxy()`, `bootstrap_audit_services()`, `bootstrap_slo_services()`, `bootstrap_governance_services()`, `bootstrap_gateway_services()`, `bootstrap_soc_services()`, `bootstrap_deployment_proxy()`, `bootstrap_trust_center()`, `bootstrap_compliance_services()`
- Key files: `services.py` (all bootstrap functions)

**`src/anonreq/pipeline/` — Pipeline Orchestration:**
- Purpose: Sequential stage execution framework + all pipeline stage implementations
- Contains: `PipelineManager`, `PipelineStage` abstract base, 12+ concrete stages
- Key files: `manager.py` (orchestrator), `base.py` (abstract base), `detection.py`, `tokenization.py`, `provider.py`, `restoration.py`, `cleanup.py`, `classification.py`, `stages.py`, `extraction.py`, `forwarding_guard.py`, `dlp.py`, `tool_governance.py`

**`src/anonreq/models/` — Data Models:**
- Purpose: Pydantic models and dataclasses for request/response, processing context, detection results, DLP, domain models
- Contains: Chat request/response models, ProcessingContext, RequestContext, DetectionResult, TokenMapping, DLPResult, Audit, Breach, Classification, DSAR, EDiscovery, Fairness, Governance, Lineage
- Key files: `chat.py` (OpenAI-compatible schema), `processing_context.py` (pipeline state), `request_context.py` (auth context), `audit.py`, `breach.py`, `classification.py`, `dlp.py`, `dsar.py`, `ediscovery.py`, `fairness.py`, `governance.py`, `lineage.py`

**`src/anonreq/detection/` — PII Detection:**
- Purpose: Regex + Presidio NER detection pipeline, span arbitration, MNPI
- Contains: Regex patterns, Presidio HTTP client, span arbiter, exclusion list, context booster, MNPI recognizers, enterprise recognizers
- Key files: `regex_detector.py`, `presidio_client.py`, `span_arbiter.py`, `pipeline.py` (MNPI loading + boosting), `boost.py`, `provider.py`, `recognizers/enterprise.py`, `recognizers/mnpi.py`

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
- Contains: AuditChainService, ChainAnchorService, SLOEngine, BreachDetector, OversightService, LifecycleService, TransparencyService, NotificationService, ClassificationService, DLPEngine, ExfiltrationDetector, Pipeline, AuditExporter, ComplianceEvidenceService, PDP2
- Key files: `audit_chain.py`, `chain_anchor.py`, `slo_engine.py`, `breach_detector.py`, `oversight.py`, `lifecycle.py`, `compliance_evidence.py`, `pdp2.py`

**`src/anonreq/secrets/` — Runtime Secret Management:**
- Purpose: Secret store, rotation, volume hot-reloading
- Contains: RuntimeSecretStore, SecretRotationBuffer, SecretVolumeReloader
- Key files: `store.py`, `rotation.py`, `reloader.py`, `bootstrap.py`

**`src/anonreq/auth/` — OIDC Authentication:**
- Purpose: OpenID Connect token verification with JWKS caching
- Contains: OIDCVerifier, JWKS key cache
- Key files: `oidc.py`

**`src/anonreq/license/` — HMAC License Validation:**
- Purpose: License key validation and gating for enterprise features
- Contains: LicenseValidator, license models, config, API router
- Key files: `validator.py` (require_license dependency), `models.py`, `config.py`, `router.py`

**`src/anonreq/trust_center/` — Trust Center Portal:**
- Purpose: Public compliance portal for customer-facing trust transparency
- Contains: TrustCenterService, rate limiter, config, schemas
- Key files: `service.py`, `router.py` (public, no auth), `config.py`, `schemas.py`

**`src/anonreq/rag/` — RAG Governance:**
- Purpose: RAG ingest, retrieval, policy enforcement, vector connectivity, audit
- Contains: VectorConnector, RAG policy engine, ingest pipeline, metadata, detection, restoration
- Key files: `vector_connector.py`, `policy.py`, `ingest.py`, `retrieval.py`, `audit.py`, `detection.py`, `restoration.py`, `metadata.py`

**`src/anonreq/firewall/` — AI Security Firewall:**
- Purpose: Injection detection, jailbreak detection, DLP, streaming inspection
- Contains: FirewallPipeline, Classifier, InjectionScorer, JailbreakDB, ML model, Gates, Rules, Override detector
- Key files: `pipeline.py`, `classifier.py`, `engine.py`, `injection_scorer.py`, `jailbreak_db.py`

**`src/anonreq/governance/` — AI Governance:**
- Purpose: Tool call governance, approvals, model/provider inventory, supplier management, risk assessment
- Contains: ApprovalManager, ToolExtractor, ToolInspector, PDP tool evaluator, ModelInventory, ProviderInventory, Supplier, Risk, Records, Reports, Reviews
- Key files: `approval.py`, `tool_extractor.py`, `tool_inspector.py`, `pdp_tool_evaluator.py`, `model_inventory.py`, `provider_inventory.py`, `router.py`
- Sub-package: `webhooks/` — AML webhook integration (`webhooks/aml.py`)

**`src/anonreq/proxy/` — Proxy Infrastructure:**
- Purpose: Proxy modes, MITM TLS interception, CA management, PAC generation, transparent/reverse proxy
- Contains: ProxyMode enum, TLSInterceptor, MITMHandler, CAManager, PACGenerator, ReverseProxy, TransparentProxy, AITrafficDetector, PipelineDispatcher
- Key files: `modes.py`, `mitm_handler.py`, `tls_interceptor.py`, `ca_manager.py`, `pac.py`, `reverse_proxy.py`, `transparent_proxy.py`, `detection.py`, `pipeline_dispatcher.py`, `optimizations.py`, `metrics.py`

**`src/anonreq/middleware/` — FastAPI Middleware:**
- Purpose: Request/response middleware for classification, policy, firewall, mTLS, RBAC
- Key files: `classification.py`, `policy.py`, `content_type.py`, `mtls.py`, `response_headers.py`, `firewall_inbound.py`, `firewall_outbound.py`, `rbac.py`

**`src/anonreq/soc/` — SOC Integration:**
- Purpose: SOC/SIEM event normalization, MITRE mapping, sink routing, health monitoring
- Contains: SOCNormalizer, MITREMapper, event buffer, sink factory, health monitor
- Key files: `normalizer.py`, `mitre.py`, `buffer.py`, `config.py`, `event.py`, `health.py`, `api.py`, `sink_factory.py`, `sink_config.py`, `router.py`
- Sub-package: `sinks/` — Sink implementations (`splunk_hec.py`, `elastic_bulk.py`, `datadog_logs.py`, `sentinel_dcr.py`, `qradar_cef.py`, `webhook.py`)

**`src/anonreq/locale/` — Locale Support:**
- Purpose: Multi-locale PII detection with locale-specific recognizer bundles
- Contains: LocaleRegistry, LocaleNegotiator, RecognizerMerger, ChecksumValidatorRegistry, locale bundles
- Key files: `registry.py`, `negotiator.py`, `merger.py`, `checksum.py`, `bundle.py`
- Sub-package: `checksums/` — Checksum algorithms (`luhn.py`, `iso7064.py`, `codice_fiscale.py`, `nir.py`)

**`tests/` — Test Suite:**
- Purpose: All tests organized by domain
- Contains: 287 test files covering unit, integration, property-based, and load tests
- Key files: `conftest.py` (shared fixtures), `hypothesis_strategies.py` (PBT strategies)
- Structure: Flat `test_*.py` at root (120+ files), `unit/` with domain subdirectories (14 subdirs), `integration/` (27 files), plus domain packages (`policy/`, `restore/`, `firewall/`, `casb/`, `rag/`, `multimodal/`, `endpoint/`, `discovery/`, `admin/`, `property/`, `load/`)

**`config/` — Runtime Configuration:**
- Purpose: YAML configuration files loaded at startup and hot-reloaded at runtime
- Contains: Policy definitions, compliance presets, locale bundles, provider registry, DLP rules, alerting configs, enterprise policy, trust center config, enterprise recognizers
- Key files: `policy.yaml`, `providers.yaml`, `classification.yaml`, `locales/en.yaml` (universal base), `enterprise-policy.yaml`, `trust_center.yaml`

## Key File Locations

**Entry Points:**
- `src/anonreq/main.py:460` — Module-level `app = create_app()` for uvicorn
- `src/anonreq/main.py:201` — `create_app()` factory function
- `Dockerfile` — `CMD ["uvicorn", "anonreq.main:app", ...]`

**Configuration:**
- `src/anonreq/config/__init__.py` — `Settings` class (env vars), `settings` singleton
- `src/anonreq/state.py` — Typed `AppState` dataclass, `get_app_state()` helper
- `config/policy.yaml` — Runtime policy configuration
- `config/providers.yaml` — Provider capability registry
- `config/classification.yaml` — Classification rule definitions
- `config/locales/en.yaml` — Universal locale recognizer bundle
- `config/enterprise-policy.yaml` — Enterprise policy configuration
- `config/trust_center.yaml` — Trust Center settings
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
- `src/anonreq/bootstrap/services.py` — Domain bootstrap functions (lifespan startup)
- `src/anonreq/secrets/store.py` — RuntimeSecretStore
- `src/anonreq/auth/oidc.py` — OIDCVerifier + JWKS cache
- `src/anonreq/license/validator.py` — `require_license()` dependency
- `src/anonreq/trust_center/service.py` — TrustCenterService
- `src/anonreq/rag/vector_connector.py` — RAG vector store connector

**Testing:**
- `tests/conftest.py` — Shared fixtures (env vars, fakeredis, sample data)
- `tests/hypothesis_strategies.py` — Hypothesis strategies for property-based tests
- `tests/integration/test_e2e_round_trip.py` — E2E round-trip integration test
- `tests/integration/test_license_gates.py` — License gate integration tests
- `tests/integration/test_oidc_admin_gate.py` — OIDC admin gate tests
- `tests/integration/test_secret_hot_reload.py` — Secret hot-reload tests
- `tests/unit/auth/test_oidc_jwks_cache.py` — OIDC JWKS cache tests
- `tests/unit/license/` — License unit tests (config, models, router, validator)
- `tests/unit/secrets/` — Secret management tests (reloader, bootstrap)
- `tests/test_trust_center.py` — Trust Center tests

**Configuration (YAML):**
- `config/policy.yaml` — Runtime policy rules
- `config/providers.yaml` — Provider capability registry
- `config/classification.yaml` — Data classification rules
- `config/locales/en.yaml` — Universal locale bundle
- `config/enterprise-policy.yaml` — Enterprise policy configuration
- `config/trust_center.yaml` — Trust Center configuration

## Naming Conventions

**Files:**
- Python: `snake_case.py` — all source files (e.g., `processing_context.py`, `span_arbiter.py`)
- Configuration: `kebab-case.yaml` — YAML config files (e.g., `model-aliases.yaml`, `prompt-security-rules.yaml`)
- Test files: `test_*.py` — flat namespace under `tests/` and `tests/unit/*/` (e.g., `test_detection.py`, `test_oidc_jwks_cache.py`)
- Test subdirectories: domain-name matching package (e.g., `tests/policy/`, `tests/restore/`, `tests/unit/auth/`)

**Functions:**
- `snake_case()` — all functions and methods (e.g., `build_pipeline()`, `raise_for_pipeline_errors()`, `run_startup_checks()`)
- Leading underscore for private/internal (e.g., `_raise_for_pipeline_errors()`, `_stream_chat_completions()`, `_shutdown()`)
- Async prefix not used — functions are async if awaited

**Variables:**
- `snake_case` — all variables (e.g., `proc_ctx`, `cache_manager`, `presidio_client`)
- Descriptive names preferred — abbreviations only when well-known (`ctx`, `pdp`, `pep`)

**Types:**
- `PascalCase` for classes (e.g., `PipelineManager`, `ProcessingContext`, `PolicyDecisionPoint`, `StreamingRestorationStage`)
- `PascalCase` for dataclasses (e.g., `AppState`, `ProcessingContext`, `RequestContext`, `ChatRequest`)
- `UPPER_CASE` for constants (e.g., `ALLOWLIST`, `DEFAULT_ALLOWED_PROVIDERS`, `PROXY_ONLY_STAGES`)

**Directories:**
- `snake_case` — all subdirectories under `src/anonreq/` (e.g., `detection/`, `tokenization/`, `proxy/`, `providers/`)
- Glob-style phase names: `{number}-{kebab-description}/` under `phases/` (e.g., `13-ai-firewall-data-loss-prevention/`)

## Where to Add New Code

**New Feature (e.g., new pipeline stage):**
- Primary code: `src/anonreq/pipeline/{feature_name}.py` — new `PipelineStage` subclass
- Pipeline registration: `src/anonreq/routing/chat.py` — add to `build_pre_provider_pipeline()` or `build_pipeline()`
- Models: `src/anonreq/models/{feature_name}.py` or add fields to `ProcessingContext`
- Tests: `tests/test_{feature_name}.py` (flat) or `tests/unit/{domain}/` (structured)

**New Provider Adapter:**
- Implementation: `src/anonreq/providers/{provider_name}.py` — subclass `ProviderAdapter`
- Registry: `src/anonreq/providers/registry.py` — register in `ProviderRegistry`
- Config: `config/providers.yaml` — add provider capability entry
- Tests: `tests/unit/providers/test_adapters.py` or `tests/test_{provider_name}_adapter.py`

**New API Route:**
- Route file: `src/anonreq/routes/{feature_name}.py` or `src/anonreq/admin/{feature_name}_routes.py`
- Versioned routes: `src/anonreq/api/v1/{feature_name}.py`
- Router registration: `src/anonreq/main.py` — `app.include_router()`
- Auth: Use `Depends(auth_context)` for protected routes
- License gate: Use `Depends(require_license("feature_name"))` for enterprise features
- Tests: `tests/test_{feature_name}.py` or `tests/unit/{domain}/`

**New Domain Service:**
- Implementation: `src/anonreq/services/{feature_name}.py` — service class with async methods
- Bootstrap: Add `bootstrap_{feature_name}()` to `src/anonreq/bootstrap/services.py`
- AppState field: Add typed field to `AppState` dataclass in `src/anonreq/state.py`
- Lifespan: Call bootstrap in `create_app()` lifespan in `src/anonreq/main.py`
- Tests: `tests/unit/services/test_{feature_name}.py` or `tests/test_{feature_name}.py`

**New Middleware:**
- Implementation: `src/anonreq/middleware/{feature_name}.py`
- Registration: `src/anonreq/main.py` — `app.add_middleware()`
- Tests: `tests/unit/middleware/test_{feature_name}.py`

**New YAML Config:**
- File: `config/{feature_name}.yaml`
- Loading: Create loader function in appropriate module
- Hot-reload: Integrate with admin config registry if needed (`src/anonreq/admin/config.py`)

**New Detection Recognizer:**
- Implementation: `src/anonreq/detection/recognizers/{feature_name}.py`
- Registration: Add to `load_mnpi_recognizers()` in `src/anonreq/detection/pipeline.py`
- Config: `config/mnpi_recognizers.yaml` or `config/recognizers.yaml`
- Locale: Add to locale-specific bundle in `config/locales/{code}.yaml`

**Tests:**
- Flat test file: `tests/test_{module_name}.py` for standalone modules
- Subpackage: `tests/{domain}/` for domain groups with multiple test files
- Structured unit: `tests/unit/{domain}/` for fine-grained unit tests
- Integration: `tests/integration/test_{feature_name}_integration.py`
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
- Purpose: User-facing and operations documentation (8 languages: EN, DE, FR, ES, IT, NL, PT, AR)
- Generated: No (translated via Phase 25)
- Committed: Yes

**`data/compliance_evidence/`:**
- Purpose: Runtime-generated compliance evidence artifacts
- Generated: Yes (at runtime)
- Committed: No (in `.gitignore`)

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

*Structure analysis: 2026-07-17*
