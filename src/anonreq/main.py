"""FastAPI application factory and entrypoint for the AnonReq gateway.

Provides:
- ``create_app()`` factory that wires exception handlers, logging, auth
  dependencies, health routes, and startup checks
- Module-level ``app = create_app()`` for uvicorn
- Root ``GET /`` returning service metadata
- Request-scoped middleware that sets request_id BEFORE auth runs

Per D-01, D-02, FAIL-01, FAIL-02, FAIL-03, FAIL-04, AUTH-MINIMAL-01:
- Global exception handlers ensure fail-secure error responses
- Lifespan context manager runs pre-flight dependency checks
- Middleware populates request_id before auth (available in 401 responses)
- All protected routes require Bearer token via auth_context dependency
- Health endpoint exposes component status
"""

import os
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import REGISTRY, Counter, generate_latest
from sqlalchemy.ext.asyncio import create_async_engine
from structlog import get_logger

from anonreq.__about__ import __version__
from anonreq.admin.routes import admin_router
from anonreq.api.v1.admin.audit import router as admin_audit_router
from anonreq.auth.oidc import build_oidc_verifier
from anonreq.cache.manager import CacheManager
from anonreq.compliance.engine import PresetEngine
from anonreq.config import settings
from anonreq.dependencies import auth_context
from anonreq.deployment.modes import DeploymentMode, TopologyConfig, get_deployment_config
from anonreq.detection.presidio_client import PresidioClient
from anonreq.discovery.admin_router import router as discovery_admin_router
from anonreq.discovery.flow_analyzer import FlowAnalyzer
from anonreq.discovery.hostname_allowlist import HostnameAllowlist
from anonreq.discovery.inventory import AssetInventory
from anonreq.exceptions import (
    DependencyUnavailableError,
    global_exception_handler,
    http_exception_handler,
)
from anonreq.firewall.pipeline import FirewallPipeline
from anonreq.gateway.detector import AIDetector
from anonreq.gateway.passthrough import GatewayStatus
from anonreq.gateway.router import RouteTable
from anonreq.governance.router import (
    approval_router as approval_record_router,
)
from anonreq.governance.router import (
    governance_router as governance_record_router,
)
from anonreq.health import router as health_router
from anonreq.license.router import router as license_router
from anonreq.license.validator import LicenseValidator, require_license
from anonreq.locale.checksum import ChecksumValidatorRegistry
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiator
from anonreq.locale.registry import LocaleRegistry
from anonreq.logging_config import setup_logging
from anonreq.middleware.classification import ClassificationMiddleware
from anonreq.middleware.content_type import ContentTypeMiddleware
from anonreq.middleware.mtls import IngressMTLSMiddleware
from anonreq.middleware.policy import PolicyMiddleware
from anonreq.middleware.response_headers import ClassificationResponseMiddleware
from anonreq.models.request_context import RequestContext
from anonreq.monitoring.middleware import MetricsMiddleware
from anonreq.multimodal.dispatcher import ContentTypeDispatcher
from anonreq.multimodal.json_analyzer import JsonAnalyzer
from anonreq.multimodal.multipart_analyzer import MultipartAnalyzer
from anonreq.providers.registry import ProviderRegistry
from anonreq.proxy.ca_manager import CAManager
from anonreq.proxy.detection import AITrafficDetector
from anonreq.proxy.mitm_handler import MITMHandler, mitm_middleware
from anonreq.proxy.modes import (
    ProxyMode,
    get_pipeline_for_mode,
    mode_from_env,
    proxy_mode_description,
    requires_detection,
    requires_mitm,
)
from anonreq.proxy.pac import PACGenerator
from anonreq.proxy.pac import router as pac_router
from anonreq.proxy.pipeline_dispatcher import PipelineContentDispatcher
from anonreq.proxy.reverse_proxy import ReverseProxy
from anonreq.proxy.tls import ConfigurationError, TLSInterceptor
from anonreq.proxy.tls_interceptor import TLSInterceptor as DynamicTLSInterceptor
from anonreq.proxy.transparent_proxy import TransparentProxy
from anonreq.routes.compliance import router as compliance_router
from anonreq.routes.governance import router as governance_router
from anonreq.routes.models import router as models_router
from anonreq.routes.oversight import router as oversight_router
from anonreq.routing.alias_registry import AliasRegistry
from anonreq.routing.chat import build_pipeline
from anonreq.routing.chat import router as chat_router
from anonreq.secrets.bootstrap import bootstrap_runtime_secret_store
from anonreq.secrets.reloader import bootstrap_runtime_secret_reloader
from anonreq.secrets.rotation import SecretRotationBuffer
from anonreq.secrets.store import RuntimeSecretStore, set_runtime_secret_store
from anonreq.services.audit_chain import AuditChainService, AuditConfig
from anonreq.services.chain_anchor import AnchorConfig, ChainAnchorService
from anonreq.services.compliance_evidence import ComplianceEvidenceService
from anonreq.soc.config import SOCConfig
from anonreq.soc.mitre import MITREMapper
from anonreq.soc.normalizer import SOCNormalizer
from anonreq.startup_checks import run_startup_checks
from anonreq.state import get_app_state
from anonreq.trust_center.config import TrustCenterSettings as TrustCenterConfig
from anonreq.trust_center.router import router as trust_center_router
from anonreq.trust_center.service import TrustCenterRateLimiter, TrustCenterService

log = get_logger()

# DLP Prometheus counters (Plan 13-04, Task 2)
dlp_violations_total = Counter(
    "anonreq_dlp_violations_total",
    "Total DLP violations by category and action",
    ["tenant_id", "category", "action"],
)
dlp_exfiltration_total = Counter(
    "anonreq_dlp_exfiltration_total",
    "Total exfiltration detections by encoding type",
    ["tenant_id", "encoding_type"],
)
dlp_actions_total = Counter(
    "anonreq_dlp_actions_total",
    "Total DLP actions applied by action type",
    ["tenant_id", "action"],
)


def _network_proxy_autostart_enabled() -> bool:
    import os

    return os.environ.get("ANONREQ_START_NETWORK_PROXY", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def create_deployment_proxy(
    topology: TopologyConfig,
    dispatcher,
):
    """Create the proxy object for a deployment topology.

    Network listeners are started by lifespan only when explicitly enabled.
    This keeps regular FastAPI tests from binding appliance ports.
    """
    if topology.mode == DeploymentMode.REVERSE:
        return ReverseProxy(dispatcher)

    tls_interceptor = DynamicTLSInterceptor(
        ca_cert_path=topology.ca_cert_path,
        ca_key_path=topology.ca_key_path,
    )
    return TransparentProxy(
        tls_interceptor=tls_interceptor,
        traffic_detector=AITrafficDetector(),
        content_dispatcher=dispatcher,
        fail_open=topology.fail_open_policy,
        firewall_pipeline=FirewallPipeline(),
    )


def bootstrap_runtime_secrets(app: FastAPI) -> None:
    """Load provider secrets into app state and the runtime secret store."""
    state = get_app_state(app)
    state.settings = settings
    app.state.settings = settings
    if settings.SECRET_BACKEND.strip().casefold() in {"volume", "file"}:
        state.secret_volume_path = f"{settings.SECRET_VOLUME_DIR}/{settings.SECRET_VOLUME_FILE}"
        app.state.secret_volume_path = state.secret_volume_path
    secret_source = getattr(app.state, "secret_backend_client", None)
    if secret_source is None:
        if (
            settings.SECRET_BACKEND.strip().casefold() == "vault"
            and os.environ.get("VAULT_ADDR")
            and os.environ.get("VAULT_TOKEN")
        ):
            state.secret_store = bootstrap_runtime_secret_store(settings)
        else:
            state.secret_store = RuntimeSecretStore()
            set_runtime_secret_store(state.secret_store)
    else:
        state.secret_store = bootstrap_runtime_secret_store(
            settings,
            source=secret_source,
        )
    app.state.secret_store = state.secret_store
    state.provider_registry = ProviderRegistry(
        secret_store=state.secret_store,
    )
    app.state.provider_registry = state.provider_registry
    state.secret_rotation_buffer = SecretRotationBuffer(
        state.secret_store.snapshot(),
    )
    app.state.secret_rotation_buffer = state.secret_rotation_buffer


def bootstrap_secret_volume_reloader(app: FastAPI):
    """Attach a secret volume reloader when the app exposes a secret path."""
    return bootstrap_runtime_secret_reloader(app)


def create_app() -> FastAPI:
    """Create and configure the AnonReq FastAPI application.

    Configures:
    - Structured logging with field allowlist via ``setup_logging()``.
    - Lifespan context manager that creates ``CacheManager``, runs
      cache health checks, and pre-flight dependency checks.
    - Exception handlers for ``Exception`` and ``HTTPException`` (fail-secure).
    - Health routes (``GET /health``, ``GET /health/ready``).
    - Root ``GET /`` returning service metadata.
    - ``CacheManager`` stored at ``app.state.cache_manager`` for route
      handler access, with clean shutdown on app teardown.

    Returns:
        A configured FastAPI application instance.
    """
    # Configure structured logging first
    setup_logging(level="INFO")

    # Resolve proxy mode at startup — immutable for the lifetime of the process
    active_mode: ProxyMode = mode_from_env()
    log.info(
        "AnonReq starting in %s mode",
        active_mode.value,
        component="lifespan",
        mode=active_mode.value,
        mode_description=proxy_mode_description(active_mode),
        pipeline_stages=get_pipeline_for_mode(active_mode),
    )

    # Phase 22: ContentTypeDispatcher for multimodal enforcement (created
    # before middleware registration, accessible to lifespan via closure).
    _json_analyzer = JsonAnalyzer()
    _multipart_analyzer = MultipartAnalyzer(json_analyzer=_json_analyzer)
    _content_type_dispatcher = ContentTypeDispatcher(
        json_analyzer=_json_analyzer,
        multipart_analyzer=_multipart_analyzer,
    )

    # Create lifespan context manager
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        log.info("Starting pre-flight checks", component="lifespan")

        state = get_app_state(app)

        # Store active mode on app state
        state.proxy_mode = active_mode
        state.deployment_config = get_deployment_config()
        state.deployment_proxy = None

        if (
            settings.OIDC_ISSUER
            and settings.OIDC_AUDIENCE
            and settings.OIDC_JWKS_URL
        ):
            state.oidc_verifier = build_oidc_verifier(
                issuer=settings.OIDC_ISSUER,
                audience=settings.OIDC_AUDIENCE,
                jwks_url=settings.OIDC_JWKS_URL,
                role_claim=settings.OIDC_ROLE_CLAIM,
                cache_ttl_seconds=settings.OIDC_JWKS_CACHE_SECONDS,
            )

        # Bootstrap provider secrets before building provider-facing runtime state.
        bootstrap_runtime_secrets(app)

        # Create cache manager for the application lifetime
        cache_manager = CacheManager(
            settings.VALKEY_URL,
            ttl=settings.CACHE_TTL_SECONDS,
        )

        try:
            await run_startup_checks(settings, cache_manager)
        except DependencyUnavailableError:
            await cache_manager.close()
            log.error("Pre-flight check failed", component="lifespan")
            raise

        # Store cache_manager on app state for route handlers
        state.cache_manager = cache_manager
        state.secret_reloader = bootstrap_secret_volume_reloader(app)
        state.alias_registry = AliasRegistry(
            provider_registry=state.provider_registry
        )

        # Detection/anonymization setup — only for modes that need it
        state.presidio_client = None
        state.pipeline = None
        state.checksum_registry = None
        state.locale_registry = None
        state.locale_negotiator = None
        state.recognizer_merger = None
        state.preset_engine = None
        state.active_compliance_presets = []

        if requires_detection(active_mode):
            checksum_registry = ChecksumValidatorRegistry()
            locale_registry = LocaleRegistry(checksum_registry=checksum_registry)
            universal_bundle = locale_registry.get("en")
            if universal_bundle is None:
                await cache_manager.close()
                raise RuntimeError("Universal locale bundle 'en' is required")
            state.checksum_registry = checksum_registry
            state.locale_registry = locale_registry
            state.locale_negotiator = LocaleNegotiator(locale_registry)
            state.recognizer_merger = RecognizerMerger(universal_bundle)
            preset_engine = PresetEngine()
            active_presets = [
                preset.strip()
                for preset in settings.ACTIVE_PRESETS.split(",")
                if preset.strip()
            ]
            base_config = {
                "entity_types": {
                    entity.name: {
                        "tier": entity.tier,
                        "confidence_threshold": entity.confidence_threshold,
                    }
                    for entity in universal_bundle.entity_types
                },
                "requires_checksum": list(checksum_registry.registered_entity_types()),
            }
            if active_presets:
                preset_engine.assert_startup_checks(active_presets, base_config)
            state.preset_engine = preset_engine
            state.active_compliance_presets = active_presets

            # Create Presidio client for the application lifetime
            presidio_client = PresidioClient(
                base_url=settings.PRESIDIO_URL,
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
                max_concurrency=settings.PRESIDIO_MAX_CONCURRENCY,
            )
            state.presidio_client = presidio_client

            # Build and store the pipeline manager
            pipeline = build_pipeline(
                cache_manager=cache_manager,
                presidio_client=presidio_client,
                alias_registry=state.alias_registry,
                locale_negotiator=state.locale_negotiator,
                recognizer_merger=state.recognizer_merger,
                checksum_registry=state.checksum_registry,
                app_state=state,
            )
            state.pipeline = pipeline
        else:
            log.info(
                "Skipping detection/anonymization setup — proxy-only mode",
                component="lifespan",
            )

        # Phase 22: Discovery inventory service
        state.inventory_service = AssetInventory()

        # Phase 22: ContentTypeDispatcher reference on app state
        state.content_type_dispatcher = _content_type_dispatcher

        # Phase 8: Enterprise Policy Engine
        try:
            from anonreq.policy.config import load_policy_config
            from anonreq.policy.forwarding_guard import ForwardingGuard
            from anonreq.policy.models import RateLimitConfig
            from anonreq.policy.pdp import PolicyDecisionPoint
            from anonreq.policy.pep import PolicyEnforcementPoint
            from anonreq.policy.residency_router import ResidencyRouter
            from anonreq.policy.spend_controller import SpendController
            from anonreq.policy.store import PolicyStore
            from anonreq.policy.usage_limiter import UsageLimiter

            policy_config = load_policy_config(settings.POLICY_CONFIG_PATH)
            policy_store = PolicyStore(cache_manager, policy_config)
            rate_limits = policy_config.rate_limits or RateLimitConfig()
            usage_limiter = UsageLimiter(cache_manager, rate_limits)
            spend_controller = SpendController(cache_manager, policy_config.spend_budgets)
            residency_router = ResidencyRouter(policy_config.residency_rules)
            pdp = PolicyDecisionPoint(
                policy_store=policy_store,
                usage_limiter=usage_limiter,
                spend_controller=spend_controller,
                residency_router=residency_router,
            )
            pep = PolicyEnforcementPoint()
            forwarding_guard = ForwardingGuard()

            state.pdp = pdp
            state.pep = pep
            state.forwarding_guard = forwarding_guard
            state.policy_store = policy_store
            log.info("Policy engine initialised", component="lifespan")
        except Exception as exc:
            log.error("Failed to initialise policy engine", component="lifespan", error=str(exc))
            await cache_manager.close()
            raise

        # Phase 17: MITM proxy setup
        ca_manager = CAManager(ca_dir=settings.CA_DIR)
        state.ca_manager = ca_manager

        ca_info = await ca_manager.get_ca_info()
        if ca_info is None and requires_mitm(active_mode):
            log.warning(
                "No CA certificate loaded in transparent proxy mode",
                component="lifespan",
                ca_dir=settings.CA_DIR,
            )

        tls_interceptor: TLSInterceptor | None = None
        if ca_info is not None:
            try:
                serial = ca_info["serial"]
                cert_path = f"{settings.CA_DIR}/{serial}.pem"
                key_path = f"{settings.CA_DIR}/{serial}.key"
                tls_interceptor = TLSInterceptor(
                    ca_cert_path=cert_path,
                    ca_key_path=key_path,
                )
            except ConfigurationError as exc:
                log.error("Failed to create TLS interceptor", component="lifespan", error=str(exc))

        if tls_interceptor is not None:
            mitm_handler = MITMHandler(
                tls_interceptor=tls_interceptor,
                ca_manager=ca_manager,
            )
            state.mitm_handler = mitm_handler

            @app.middleware("http")
            async def proxy_middleware(request: Request, call_next: Callable) -> Response:
                return await mitm_middleware(request, call_next)

            log.info("MITM proxy middleware registered", component="lifespan")

        # Phase 11: Initialize audit database and services
        audit_engine = create_async_engine(settings.DATABASE_URL)
        state.audit_engine = audit_engine
        audit_config = AuditConfig(retention_days=2557)
        audit_chain = AuditChainService(audit_engine, audit_config)
        state.audit_chain = audit_chain

        anchor_config = AnchorConfig(
            signing_key=settings.ANCHOR_SIGNING_KEY,
        )
        chain_anchor = ChainAnchorService(audit_chain, audit_engine, anchor_config)
        state.chain_anchor = chain_anchor

        # Phase 11: Initialize SLO Engine and Breach Detector
        import httpx

        from anonreq.services.breach_detector import BreachDetector
        from anonreq.services.slo_engine import SLOEngine

        slo_engine = SLOEngine(cache_manager, "config/slo.yaml")
        state.slo_engine = slo_engine

        webhook_client = httpx.AsyncClient(follow_redirects=False)
        state.webhook_client = webhook_client
        breach_detector = BreachDetector(
            slo_engine=slo_engine,
            audit_chain=audit_chain,
            cache_manager=cache_manager,
            http_client=webhook_client,
            config_path="config/webhook.yaml"
        )
        state.breach_detector = breach_detector

        # Phase 14: AI Governance & Oversight services
        from anonreq.services.lifecycle import LifecycleService
        from anonreq.services.notifications import NotificationService
        from anonreq.services.oversight import OversightService
        from anonreq.services.transparency import TransparencyService

        state.oversight_service = OversightService(cache_manager)
        state.lifecycle_service = LifecycleService(cache_manager)
        state.transparency_service = TransparencyService(cache_manager)
        state.notification_service = NotificationService(cache_manager)

        # Phase 18: ApprovalManager for tool call governance
        from anonreq.governance.approval import ApprovalManager

        state.approval_manager = ApprovalManager(
            cache_manager=cache_manager,
            oversight_service=state.oversight_service,
            ttl=settings.CACHE_TTL_SECONDS,
        )
        log.info("ApprovalManager initialized", component="lifespan", ttl=settings.CACHE_TTL_SECONDS)  # noqa: E501

        # Phase 17: Universal AI Traffic Gateway
        state.gateway_status = GatewayStatus()
        state.ai_detector = AIDetector()
        state.route_table = RouteTable()

        # Phase 17-02: AI traffic detection and MCP inspection
        allowlist = HostnameAllowlist()
        flow_analyzer = FlowAnalyzer()
        state.allowlist = allowlist
        state.flow_analyzer = flow_analyzer

        # Create PACGenerator with all known AI provider domains
        pac_domains = allowlist.get_all_proxy_domains()
        pac_generator = PACGenerator(
            pac_domains,
            settings.HOST,
            settings.PORT,
        )
        state.pac_generator = pac_generator
        log.info(
            "PAC generator initialized",
            component="lifespan",
            domain_count=len(pac_domains),
        )

        # Create MCP inspector for protocol detection
        try:
            from anonreq.mcp.inspector import MCPInspector as MCPInspectorCls

            mcp_inspector = MCPInspectorCls(flow_analyzer, allowlist)
            state.mcp_inspector = mcp_inspector
            log.info("MCP inspector initialized", component="lifespan")
        except Exception as exc:
            log.warning(
                "MCP inspector not available",
                component="lifespan",
                error=str(exc),
            )

        log.info("Phase 17 gateway services initialized", component="lifespan")

        # Phase 20: SOC Integration Service
        try:
            soc_config = SOCConfig()
            mitre_mapper = MITREMapper("config/mitre-mapping.yaml")
            soc_normalizer = SOCNormalizer(
                mitre_mapper=mitre_mapper,
                config=soc_config,
            )
            await soc_normalizer.start()
            state.soc_normalizer = soc_normalizer
            state.soc_mitre_mapper = mitre_mapper
            log.info(
                "SOC Integration Service initialized",
                component="lifespan",
                gateway_version=soc_config.gateway_version,
                appliance_instance_id=soc_config.appliance_instance_id,
            )
        except Exception as exc:
            log.warning(
                "SOC Integration Service not available",
                component="lifespan",
                error=str(exc),
            )

        # Phase 20-05: SIEM sink infrastructure (config-driven)
        try:
            from anonreq.soc.sink_config import SinkConfigLoader
            from anonreq.soc.sink_factory import build_sinks

            sink_loader = SinkConfigLoader("config/soc-sinks.yaml")
            sink_definitions = sink_loader.load()
            sink_router, sink_health_monitor = build_sinks(sink_definitions)

            # Start all enabled sinks
            await sink_router.start_all()

            # Start periodic health monitor
            await sink_health_monitor.start()

            state.soc_sink_router = sink_router
            state.soc_sink_health_monitor = sink_health_monitor

            log.info(
                "SIEM sinks initialized",
                component="lifespan",
                sink_count=len(sink_definitions),
                enabled_count=sum(1 for d in sink_definitions if d.enabled),
            )
        except Exception as exc:
            log.warning(
                "SIEM sinks not available — SOC events will not be forwarded",
                component="lifespan",
                error=str(exc),
            )

        # Phase 22: Register SOC normalizer fan-out to sink router
        if state.soc_normalizer is not None and state.soc_sink_router is not None:
            state.soc_normalizer.register_sink_callback(
                "sink_router",
                state.soc_sink_router.fan_out,
            )
            log.info(
                "SOC normalizer fan-out registered to sink router",
                component="lifespan",
            )

        # Phase 21/22: Endpoint visibility deployment topology with PipelineContentDispatcher.
        try:
            if state.pipeline is not None:
                dispatcher = PipelineContentDispatcher(
                    state.pipeline,
                    app_state=state,
                )
            else:
                def dispatcher(_request: Any) -> bytes:
                    return b""
            state.deployment_proxy = create_deployment_proxy(
                state.deployment_config,
                dispatcher,
            )
            if _network_proxy_autostart_enabled() and hasattr(state.deployment_proxy, "start"):
                await state.deployment_proxy.start(
                    state.deployment_config.listen_host,
                    state.deployment_config.listen_port,
                )
            log.info(
                "Deployment proxy initialized",
                component="lifespan",
                deployment_mode=state.deployment_config.mode.value,
                listener_started=_network_proxy_autostart_enabled(),
            )
        except Exception as exc:
            log.error(
                "Failed to initialize deployment proxy",
                component="lifespan",
                deployment_mode=state.deployment_config.mode.value,
                error=str(exc),
            )
            await cache_manager.close()
            raise

        # Phase 24: Trust Center — public compliance evidence portal
        try:
            import yaml
            trust_config_path = "config/trust_center.yaml"
            with open(trust_config_path) as f:
                trust_yaml = yaml.safe_load(f) or {}
            trust_settings = TrustCenterConfig(**trust_yaml)
            state.trust_center_settings = trust_settings
            state.trust_center_enabled = trust_settings.enabled

            trust_center_service = TrustCenterService(
                slo_engine=state.slo_engine,
                preset_engine=state.preset_engine,
                settings=trust_settings,
            )
            state.trust_center_service = trust_center_service

            trust_rate_limiter = TrustCenterRateLimiter(cache_manager)
            state.trust_center_rate_limiter = trust_rate_limiter

            log.info(
                "Trust Center initialised",
                component="lifespan",
                enabled=trust_settings.enabled,
            )
        except Exception as exc:
            log.error(
                "Trust Center initialisation failed",
                component="lifespan",
                error=str(exc),
            )
            state.trust_center_enabled = False

        # Phase 26: Initialize compliance evidence service
        compliance_evidence_service = ComplianceEvidenceService(
            slo_engine=state.slo_engine,
            audit_chain=state.audit_chain,
            governance_service=None,  # wired when governance service available
            incident_service=None,
        )
        state.compliance_evidence_service = compliance_evidence_service

        # Phase 26: Startup license validation
        license_status = await LicenseValidator.validate_license()
        log.info(
            "License validation complete",
            component="lifespan",
            valid=license_status.valid,
            tier=license_status.tier.value if license_status.tier else None,
            features=[f.value for f in license_status.features],
            organization=license_status.organization,
        )

        log.info("Pre-flight checks passed, accepting traffic", component="lifespan")
        yield

        # Clean shutdown
        log.info("Shutting down", component="lifespan")
        if state.deployment_proxy is not None and hasattr(state.deployment_proxy, "stop"):
            await state.deployment_proxy.stop()
        if state.soc_sink_health_monitor is not None:
            await state.soc_sink_health_monitor.stop()
            log.info("Sink health monitor stopped", component="lifespan")
        if state.soc_sink_router is not None:
            await state.soc_sink_router.stop_all()
            log.info("Sink router stopped", component="lifespan")
        if state.soc_normalizer is not None:
            await state.soc_normalizer.stop()
            log.info("SOC normalizer stopped", component="lifespan")
        if state.webhook_client is not None:
            await state.webhook_client.aclose()
        if state.secret_reloader is not None:
            state.secret_reloader.close()
        if state.audit_engine is not None:
            await state.audit_engine.dispose()
        if state.mitm_handler is not None:
            await state.mitm_handler.close()
        if state.ca_manager is not None:
            await state.ca_manager.close()
        if state.presidio_client is not None:
            await state.presidio_client.close()
        await cache_manager.close()

    app = FastAPI(
        title="AnonReq",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Register fail-secure exception handlers (order matters — specific first)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # Add MetricsMiddleware for Prometheus request counting and latency
    # Must be added before set_request_context so it's outermost (first
    # to run on request, last on response), capturing request_receipt_time
    # before any other middleware processing.
    app.add_middleware(MetricsMiddleware)

    # ClassificationMiddleware — parses X-AnonReq-Classification header,
    # blocks HIGHLY_RESTRICTED requests with HTTP 451, stores client
    # classification on request state for pipeline use.
    # Runs after MetricsMiddleware but before PolicyMiddleware (PDP #2)
    # per Plan 12-02: after Content-Type dispatch, before PDP #2.
    app.add_middleware(ClassificationMiddleware)

    # PolicyMiddleware — evaluates PDP/PEP on chat-completion routes.
    # Runs after request-context middleware so request_id is available.
    app.add_middleware(PolicyMiddleware)

    # ClassificationResponseMiddleware — conditionally returns classification result headers
    app.add_middleware(ClassificationResponseMiddleware)

    # Phase 22: Content-Type enforcement middleware — rejects unsupported
    # content types before any route processing.
    app.add_middleware(
        ContentTypeMiddleware,
        dispatcher=_content_type_dispatcher,
    )

    app.add_middleware(IngressMTLSMiddleware)

    # Add /metrics endpoint for Prometheus scraping (no auth — scrapers
    # connect on internal networks; secured at network level)
    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(
            content=generate_latest(REGISTRY),
            media_type="text/plain; charset=utf-8",
        )

    # Middleware: set request_id BEFORE auth runs so it's available in
    # 401 error responses (per RESEARCH Open Question 4).
    @app.middleware("http")
    async def set_request_context(request: Request, call_next: Callable) -> Response:
        request_id = f"req_{uuid4().hex[:24]}"
        request.state.request_id = request_id
        request.state.context = RequestContext(request_id=request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        structlog.contextvars.unbind_contextvars("request_id")
        return response

    # Include health routes with auth protection
    app.include_router(health_router, dependencies=[Depends(auth_context)])

    # Include chat route with auth protection
    app.include_router(chat_router, dependencies=[Depends(auth_context)])
    app.include_router(models_router, dependencies=[Depends(auth_context)])
    app.include_router(compliance_router, dependencies=[Depends(auth_context)])
    app.include_router(governance_router, dependencies=[Depends(auth_context)])
    app.include_router(governance_record_router, dependencies=[Depends(auth_context)])
    app.include_router(approval_record_router, dependencies=[Depends(auth_context)])
    app.include_router(oversight_router, dependencies=[Depends(auth_context)])
    app.include_router(admin_router, dependencies=[Depends(auth_context)])
    app.include_router(admin_audit_router, dependencies=[Depends(auth_context)])

    # Phase 22: Discovery inventory admin routes
    app.include_router(discovery_admin_router, dependencies=[Depends(auth_context)])

    # Phase 26: License router (requires auth)
    app.include_router(license_router, dependencies=[Depends(auth_context)])

    # PAC file endpoint — public (no auth, used by browsers/proxies)
    app.include_router(pac_router)

    # Trust Center router — public (no auth), config-gated, rate-limited
    app.include_router(trust_center_router)
    log.info("Trust Center router registered", component="lifespan")

    # Phase 17: Gateway status endpoint
    @app.get("/v1/gateway/status")
    async def gateway_status(_ctx: Any = Depends(auth_context)) -> dict[str, Any]:
        gs: GatewayStatus = get_app_state(app).gateway_status
        return gs.get_status()

    # Phase 20-05: SOC integration status endpoint
    @app.get("/v1/admin/soc/integration/status")
    async def soc_integration_status(
        _ctx: Any = Depends(auth_context),
        _license: None = Depends(require_license("soc_integration")),
    ) -> Any:
        from anonreq.soc.api import create_soc_status_response
        return create_soc_status_response(
            get_app_state(app).soc_sink_health_monitor
        )

    @app.get("/")
    async def root(_ctx: Any = Depends(auth_context)) -> dict[str, str]:
        return {"service": "AnonReq", "version": __version__}

    return app


app = create_app()
"""Module-level application instance for uvicorn.

Usage:
    ``uvicorn anonreq.main:app --host 0.0.0.0 --port 8080``
"""
