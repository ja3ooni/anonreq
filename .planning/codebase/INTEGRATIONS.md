# External Integrations

**Analysis Date:** 2026-07-18

## Provider APIs

**OpenAI:**
- Adapter: `src/anonreq/providers/openai.py` → `OpenAIAdapter`
- Endpoint: `https://api.openai.com/v1/chat/completions`
- Auth: `Authorization: Bearer {api_key}` header
- API key resolution: `RuntimeSecretStore` → `ANONREQ_OPENAI_API_KEY` → `OPENAI_API_KEY`
- HTTP client: `httpx.AsyncClient` (lazy-init, 30s timeout, no redirects)
- Streaming: SSE with `data: {...}\n\n` lines, `[DONE]` sentinel
- Translation: passes OpenAI requests through directly (canonical format)

**Anthropic:**
- Adapter: `src/anonreq/providers/anthropic.py` → `AnthropicAdapter`
- Endpoint: `https://api.anthropic.com/v1/messages`
- Auth: `x-api-key` header + `anthropic-version: 2023-06-01`
- Translation: OpenAI → Anthropic format (system message extracted to top-level `system` param, tools converted to `name`/`description`/`input_schema`)
- Streaming: SSE with `event:` prefix lines, events: `message_start`, `content_block_delta`, `message_delta`, `error`
- Response normalization: Anthropic content blocks → OpenAI `choices[0].message.content`

**Google Gemini:**
- Adapter: `src/anonreq/providers/gemini.py` → `GeminiAdapter`
- Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- Auth: `x-goog-api-key` header
- Translation: OpenAI → Gemini format (system → `system_instruction`, assistant → `model` role, tools → `function_declarations`)
- Streaming: SSE via `:streamGenerateContent?alt=sse` endpoint variant
- Response normalization: Gemini candidates → OpenAI canonical format

**Ollama:**
- Adapter: `src/anonreq/providers/ollama.py` → `OllamaAdapter`
- Endpoint: `{OLLAMA_HOST}/api/chat` (default: `http://localhost:11434/api/chat`)
- Auth: optional `Authorization: Bearer` (for remote setups); local runs without auth
- Translation: minimal — Ollama uses OpenAI-compatible messages format
- Streaming: NDJSON (newline-delimited JSON), each line has `message` + `done` boolean

**Provider Registry:**
- `src/anonreq/providers/registry.py` → `ProviderRegistry`
- Loads adapter class paths from `config/providers.yaml` via `yaml.safe_load()`
- Dynamic import via `importlib.import_module()` at resolution time
- Lazy-imported and cached per provider name
- API key resolution chain: `RuntimeSecretStore.get_provider_api_key()` → `ANONREQ_{PROVIDER}_API_KEY` → `{PROVIDER}_API_KEY`

**Adapter Pattern:**
- All adapters implement `ProviderAdapter` ABC (`src/anonreq/providers/adapter.py`)
- Methods: `translate_request()`, `execute()`, `stream_events()`, `translate_response()`
- Zero policy/classification/detection logic inside adapters (pure schema translators)
- Secrets resolved only at network boundary (never stored in `ProcessingContext`)
- Capabilities loaded from `config/capabilities.yaml` via `CapabilityResolver`

## Data Storage

**Redis/Valkey (ephemeral cache):**
- Client: `redis.asyncio` (Python redis-py async interface)
- Connection: `CacheManager` at `src/anonreq/cache/manager.py`
- Topologies supported:
  - Standalone: `redis://host:port/db` via `redis.from_url()`
  - Sentinel: `redis+sentinel://host1:port1,host2:port2/servicename` via `Sentinel().master_for()`
  - Cluster: `redis+cluster://host1:port1,host2:port2` via `RedisCluster()`
- Key format: `anonreq:{tenant_id}:{session_id}` — HASH mapping `token → original_value`
- Atomicity: `pipeline(transaction=True)` for HSET + EXPIRE
- TTL: configurable via `ANONREQ_CACHE_TTL_SECONDS` (default: 300s)
- Retry: tenacity exponential backoff (0.1s–2s, 30s total stop) on `ConnectionError`, `TimeoutError`, `ReadOnlyError`, `ClusterDownError`, `MasterDownError`
- Health check: `src/anonreq/cache/health.py` — PING + verify `save ""` (persistence disabled)
- SLO tracking uses Redis sorted sets and counters for daily/monthly/rolling windows (`src/anonreq/services/slo_engine.py`)

**PostgreSQL (governance/audit persistence):**
- Driver: `asyncpg>=0.31.0` (async PostgreSQL)
- ORM: `sqlalchemy>=2.0.0` with async support
- Connection URL: `ANONREQ_DATABASE_URL` (default fallback: `sqlite+aiosqlite:///./anonreq.db`)
- Migrations: Alembic (`alembic/versions/`)
- Models: `src/anonreq/models/governance.py`, `src/anonreq/models/breach.py`, `src/anonreq/models/dsar.py`, `src/anonreq/models/ediscovery.py`, `src/anonreq/models/lineage.py`, `src/anonreq/models/dlp.py`
- Docker Compose: `postgres:16-alpine` (observability profile only)

**SQLite (default/fallback database):**
- Driver: `aiosqlite>=0.20.0`
- Default connection: `sqlite+aiosqlite:///./anonreq.db`
- Used when no PostgreSQL is configured (development/small deployments)

**MinIO (compliance archive storage):**
- Client: `minio>=7.2.0` Python SDK (optional extra `[storage]`)
- Module: `src/anonreq/storage/minio.py` → `MinioWormBucket`
- Bucket: `anonreq-mnpi-audit` with WORM (object_lock=True)
- Retention: COMPLIANCE mode, 7-year retain-until-date (2557 days)
- Object path: `{tenant_id}/{YYYY}/{MM}/{DD}/{event_id}.json`
- Factory: `create_mnpi_worm_bucket()` reads `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`
- Only SHA-256 hashes of detected values stored (never raw PII/MNPI)

## Presidio

**Presidio Analyzer Sidecar:**
- Client: `src/anonreq/detection/presidio_client.py` → `PresidioClient`
- HTTP client: `httpx.AsyncClient` (lazy-init, 2s default timeout, no redirects)
- Endpoint: `ANONREQ_PRESIDIO_URL/analyze` (POST), `{url}/health` (GET)
- Concurrency: `asyncio.Semaphore(max_concurrency)` — default 10 concurrent requests
- Short text skip: nodes < 20 chars bypass Presidio (regex only)
- Score threshold: 0.7 default
- Batch analysis: `analyze_text_nodes()` uses `asyncio.gather()` with semaphore control
- Docker: `mcr.microsoft.com/presidio-analyzer:latest` sidecar
- Error handling: `PresidioTimeoutError` on timeout, `PresidioError` on HTTP error
- Health check: GET `/health`, returns `{"reachable": bool}`

## SOC/SIEM Sinks

**Sink Architecture:**
- Router: `src/anonreq/soc/router.py` → `SinkRouter` — fan-out to all registered sinks
- Factory: `src/anonreq/soc/sink_factory.py` — instantiates sinks from `SinkDefinition` config
- Config: `src/anonreq/soc/sink_config.py` → `SinkConfigLoader` — loads `config/soc-sinks.yaml`
- Secret resolution: `$env:VAR_NAME` (env var) and `$file:/etc/anonreq/secrets/...` (file)
- Normalizer: `src/anonreq/soc/normalizer.py` → `SOCNormalizer` — strips content fields, MITRE mapping, metadata enrichment
- Event bus: `asyncio.Queue` (maxsize from config, default 10000) — non-blocking `put_nowait()`
- Buffering: optional `SinkBuffer` wrapper per sink (configurable `buffer_maxsize`)
- Health monitoring: `src/anonreq/soc/health.py` → `SinkHealthMonitor`

**Splunk HEC:**
- Sink: `src/anonreq/soc/sinks/splunk_hec.py` → `SplunkHECSink`
- Protocol: HTTP POST to `/services/collector/event`
- Auth: `Authorization: Splunk {token}` header
- Wire format: HEC JSON envelope (`time`, `host`, `source`, `sourcetype: anonreq:ai_security`, `event`)
- Batch support: `send_batch()` for multiple events in one request

**Elastic Bulk:**
- Sink: `src/anonreq/soc/sinks/elastic_bulk.py` → `ElasticBulkSink`
- Protocol: HTTP POST to bulk API endpoint
- Auth: `api_key` header
- Index pattern: `anonreq-ai-security-%Y.%m.%d` (daily rotation)

**Azure Sentinel DCR:**
- Sink: `src/anonreq/soc/sinks/sentinel_dcr.py` → `SentinelDCRSink`
- Protocol: HTTP POST to DCR endpoint
- Auth: Azure AD client credentials (tenant_id, client_id, client_secret)
- Config: DCR immutable ID, stream name

**QRadar CEF:**
- Sink: `src/anonreq/soc/sinks/qradar_cef.py` → `QRadarCEFSink`
- Protocol: TCP/UDP syslog with CEF format
- Default port: 514, TCP by default

**Datadog Logs:**
- Sink: `src/anonreq/soc/sinks/datadog_logs.py` → `DatadogLogsSink`
- Protocol: HTTP POST to Datadog Logs API
- Auth: `DD-API-KEY` header
- Default site: `datadoghq.com`

**Webhook:**
- Sink: `src/anonreq/soc/sinks/webhook.py` → `WebhookSink`
- Protocol: configurable HTTP method (default POST)
- Custom headers and payload templates supported
- Content-Type: `application/json` default

**SOC Event Flow:**
1. Detection engines publish `RawSecurityEvent` to `SOCNormalizer.event_bus` (asyncio.Queue)
2. Normalizer strips content fields (`content`, `prompt`, `response`, `raw_text`, `message`, `text`) per D-012
3. If content fields detected → event dropped with `soc_strip_failure` audit
4. MITRE technique ID resolved via `MITREMapper` (config: `config/mitre_mapping.yaml`, `config/mitre_attack.yaml`, `config/mitre_atlas.yaml`)
5. `NormalizedEvent` produced with 8 required fields + metadata dict
6. Fan-out to all enabled sinks via `SinkRouter.fan_out()`
7. Each sink formats and delivers independently (failure in one doesn't affect others)

## Proxy/TLS

**Transparent Proxy:**
- Module: `src/anonreq/proxy/transparent_proxy.py` → `TransparentProxy`
- TLS interception: `src/anonreq/proxy/tls_interceptor.py` → `TLSInterceptor`
  - Enterprise CA loaded from disk (`ANONREQ_CA_DIR`)
  - Dynamic leaf cert generation (RSA 2048, SHA-256, 24h TTL)
  - TLS 1.3 minimum, in-memory cert cache per domain
  - Generated certs written to temp files briefly, loaded into `ssl.SSLContext`, then deleted
- Traffic detection: `src/anonreq/proxy/detection.py` → `AITrafficDetector` — identifies AI API traffic
- Certificate pinning detection: `CertPinningDetector` — blocks pinned clients with HTTP 426
- Fail-closed policy: all ambiguities block forwarding

**Reverse Proxy:**
- Module: `src/anonreq/proxy/reverse_proxy.py` → `ReverseProxy`

**MITM Handler:**
- Module: `src/anonreq/proxy/mitm_handler.py` → `MITMHandler`
- Orchestrates TLS interception, cert pinning detection, bidirectional tunnel establishment

**CA Manager:**
- Module: `src/anonreq/proxy/ca_manager.py` → `CAManager`
- Dual-path management: API upload + filesystem watch
- Hot-reload via `watchdog` filesystem observer
- In-memory metadata store keyed by certificate serial number

**PAC File:**
- Module: `src/anonreq/proxy/pac.py` → `PACGenerator` + FastAPI router
- Endpoint: `GET /v1/proxy.pac` (public, no auth)
- Generates Netscape PAC JavaScript routing AI provider domains through gateway
- Admin endpoints for custom PAC rules (authenticated)
- Default domains: `.openai.com`, `.anthropic.com`, `.googleapis.com`
- Custom rules support wildcard subdomain patterns

**Proxy Modes:**
- Module: `src/anonreq/proxy/modes.py`
- `proxy-only` — standard API proxy
- `transparent` — transparent interception with TLS/MITM
- `full` — full appliance mode with all interception features

## Endpoint Agent

**Desktop Agent:**
- Module: `src/anonreq/endpoint/agent.py` → `EndpointAgent`
- Lifecycle: async start/stop with background tasks
- AI app discovery: `src/anonreq/endpoint/discovery.py` → `AppDiscovery`
  - Scans running processes for known AI apps: Cursor, Claude Desktop, ChatGPT Desktop, VS Code (Copilot)
  - macOS-specific: uses bundle IDs (`com.todesktop.230113mto6h4b5r`, `com.anthropic.claudedesktop`, etc.)
- Traffic capture: `src/anonreq/endpoint/macos/capture.py` → `TrafficCapture` (macOS-specific)
- Heartbeat telemetry: periodic status emission via structured audit logger
- Config: `src/anonreq/endpoint/config.py` → `EndpointConfig` (heartbeat_interval_sec, discovery_interval_sec, capture_enabled, capture_interface)

## Voice

**Speech-to-Text Engine:**
- Module: `src/anonreq/voice/stt_engine.py` → `STTEngine`
- Model backends (tried in order):
  1. `faster_whisper.WhisperModel` (preferred, CTranslate2-based)
  2. `whisper.load_model` (OpenAI Whisper fallback)
- Config: `src/anonreq/voice/config.py` → `VoiceConfig` (stt_model_size, stt_device, audio_sample_rate, transcript_buffer settings)
- Device selection: auto-detect CUDA via `torch.cuda.is_available()`, fallback to CPU
- Streaming: `transcribe_streaming()` with sliding window overlap buffer
- Transcript buffer: `src/anonreq/voice/transcript_buffer.py` — contiguous assembly from overlapping chunks

**Voice Connectors:**
- Module: `src/anonreq/voice/connectors.py`
- `SIPConnector` — SIP trunk proxy, RTP audio extraction
- `WebRTCConnector` — WebRTC media with SDP inspection and ICE passthrough
- `WebSocketConnector` — binary audio frame streaming with fragmentation support
- `GRPCConnector` — bidirectional gRPC-style audio streams with length-prefixed messages
- Audio format detection: WAV (RIFF header), Opus (RTP payload type), PCM (default)
- All connectors extend `BaseConnector` ABC with common lifecycle and chunk delivery

**Voice Pipeline:**
- Module: `src/anonreq/voice/pipeline.py` — orchestrates connector → STT → sanitization
- Sanitizer: `src/anonreq/voice/sanitizer.py` — PII detection/redaction on transcripts
- Detector: `src/anonreq/voice/detector.py` — security event detection on voice content

## Prometheus/Grafana

**Metrics Export:**
- Endpoint: `GET /metrics` (no auth, network-level security)
- Format: Prometheus text exposition via `prometheus_client.generate_latest(REGISTRY)`
- Core metrics defined in `src/anonreq/monitoring/metrics.py`
- Middleware: `src/anonreq/monitoring/middleware.py` → `MetricsMiddleware` — request counting and latency
- Docker Compose: Prometheus v2.53.0 + Grafana 11.0.0 (observability profile)
- Prometheus config: `docker/prometheus/prometheus.yml`
- Grafana dashboards: `docker/grafana/dashboards/` (SLO dashboard as default home)

**Docker Compose Observability Services:**
- `postgres-exporter` (v0.15.0) — PostgreSQL metrics for Prometheus
- `valkey-exporter` (v1.61.0) — Valkey/Redis metrics for Prometheus

## Authentication

**API Key Auth (primary):**
- Module: `src/anonreq/dependencies.py` → `verify_api_key` / `auth_context`
- Bearer token via `HTTPBearer(auto_error=True)`
- Constant-time comparison: `hmac.compare_digest(token, settings.API_KEY)`
- Min key length: 32 characters (validated at startup)
- `auth_context` composite dependency: validates auth + populates `RequestContext`

**Admin API Key:**
- Separate key: `ANONREQ_ADMIN_API_KEY` env var
- Module: `src/anonreq/admin/auth.py` → `verify_admin_api_key`

**OIDC (admin identity tokens):**
- Module: `src/anonreq/auth/oidc.py` → `build_oidc_verifier`
- JWKS-based verification with cached key lookups (`JWKSCache`)
- Config: `ANONREQ_OIDC_ISSUER`, `ANONREQ_OIDC_AUDIENCE`, `ANONREQ_OIDC_JWKS_URL`
- Role projection from configurable claim (`ANONREQ_OIDC_ROLE_CLAIM`, default: `role`)

**mTLS (ingress forwarded):**
- Module: `src/anonreq/middleware/mtls.py` → `IngressMTLSMiddleware`
- Validates forwarded client certificates from trusted ingress proxies
- Config: `ANONREQ_MTLS_ENFORCE`, `ANONREQ_MTLS_TRUSTED_PROXY_CIDRS`, `ANONREQ_MTLS_FORWARD_CERT_HEADER`

## Secrets Management

**Runtime Secret Store:**
- Module: `src/anonreq/secrets/store.py` → `RuntimeSecretStore`
- Thread-safe in-memory snapshot container (RLock)
- Immutable snapshots: `SecretSnapshot(provider_api_keys=...)` with `MappingProxyType`
- ContextVar-based access: `get_runtime_secret_store()` / `set_runtime_secret_store()`

**Secret Backends:**
- Volume/file: reads from `ANONREQ_SECRET_VOLUME_DIR`/`ANONREQ_SECRET_VOLUME_FILE`
- Vault: HashiCorp Vault integration (when `VAULT_ADDR` + `VAULT_TOKEN` set)
- Hot-reload: `src/anonreq/secrets/reloader.py` → `bootstrap_runtime_secret_reloader()` via watchdog

**Secret Rotation:**
- Module: `src/anonreq/secrets/rotation.py` → `SecretRotationBuffer`
- Buffers current snapshot for graceful rotation without downtime

## Database (Alembic)

**Migrations:**
- Directory: `alembic/`
- Config: `alembic/env.py`
- Models: `src/anonreq/models/` (governance, breach, DSAR, eDiscovery, lineage, DLP, audit)
- SQLAlchemy declarative base: `src/anonreq/models/audit.py` → `Base`

## Licensing

**License Validation:**
- Module: `src/anonreq/license/validator.py` → `require_license(feature)`
- HMAC-SHA256 signed license key
- Config: `ANONREQ_LICENSE_KEY`, `ANONREQ_LICENSE_SECRET`
- Feature-gated: `require_license("soc_integration")` etc.
- Router: `src/anonreq/license/router.py`

## MCP (Model Context Protocol)

**MCP Integration:**
- Module: `src/anonreq/mcp/`
- Provides MCP-compatible tool/resource access for AI agents interacting with the gateway

## Monitoring Middleware

**Request Metrics:**
- Module: `src/anonreq/monitoring/middleware.py` → `MetricsMiddleware`
- Outermost middleware (added first, runs first on request, last on response)
- Captures `request_receipt_time` before any other processing

---

*Integration audit: 2026-07-18*
