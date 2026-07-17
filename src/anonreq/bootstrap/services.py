"""Domain-specific bootstrap functions for the AnonReq lifespan.

Each ``bootstrap_*`` function initialises a coherent slice of application
state.  They are called sequentially during startup and set attributes on
``get_app_state(app)``.  Errors are logged and re-raised so the lifespan
can clean up and abort.
"""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import create_async_engine
from structlog import get_logger

from anonreq.config import settings
from anonreq.proxy.modes import requires_detection, requires_mitm
from anonreq.state import get_app_state

log = get_logger()


async def bootstrap_locale_detection(
    app: FastAPI,
    cache_manager: Any,
) -> None:
    """Set up locale, Presidio client, and detection pipeline.

    Returns ``None`` if the current proxy mode does not require detection.
    """
    state = get_app_state(app)

    # Defaults for modes that skip detection
    state.presidio_client = None
    state.pipeline = None
    state.checksum_registry = None
    state.locale_registry = None
    state.locale_negotiator = None
    state.recognizer_merger = None
    state.preset_engine = None
    state.active_compliance_presets = []

    if not requires_detection(state.proxy_mode):
        log.info("Skipping detection/anonymization setup — proxy-only mode", component="lifespan")
        return

    from anonreq.compliance.engine import PresetEngine
    from anonreq.detection.presidio_client import PresidioClient
    from anonreq.locale.checksum import ChecksumValidatorRegistry
    from anonreq.locale.merger import RecognizerMerger
    from anonreq.locale.negotiator import LocaleNegotiator
    from anonreq.locale.registry import LocaleRegistry
    from anonreq.routing.chat import build_pipeline

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

    presidio_client = PresidioClient(
        base_url=settings.PRESIDIO_URL,
        timeout=settings.REQUEST_TIMEOUT_SECONDS,
        max_concurrency=settings.PRESIDIO_MAX_CONCURRENCY,
    )
    state.presidio_client = presidio_client

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


async def bootstrap_policy_engine(app: FastAPI, cache_manager: Any) -> None:
    """Initialize PDP, PEP, policy store, rate/spend controls."""
    state = get_app_state(app)
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


async def bootstrap_mitm_proxy(app: FastAPI) -> None:
    """Set up CA manager, TLS interceptor, MITM handler and middleware."""
    state = get_app_state(app)

    from anonreq.proxy.ca_manager import CAManager
    from anonreq.proxy.mitm_handler import MITMHandler, mitm_middleware
    from anonreq.proxy.tls import ConfigurationError, TLSInterceptor

    ca_manager = CAManager(ca_dir=settings.CA_DIR)
    state.ca_manager = ca_manager

    ca_info = await ca_manager.get_ca_info()
    if ca_info is None and requires_mitm(state.proxy_mode):
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


async def bootstrap_audit_services(app: FastAPI) -> None:
    """Create audit DB engine, audit chain, and chain anchor."""
    state = get_app_state(app)

    from anonreq.services.audit_chain import AuditChainService, AuditConfig
    from anonreq.services.chain_anchor import AnchorConfig, ChainAnchorService

    audit_engine = create_async_engine(settings.DATABASE_URL)
    state.audit_engine = audit_engine

    audit_config = AuditConfig(retention_days=2557)
    audit_chain = AuditChainService(audit_engine, audit_config)
    state.audit_chain = audit_chain

    anchor_config = AnchorConfig(signing_key=settings.ANCHOR_SIGNING_KEY)
    chain_anchor = ChainAnchorService(audit_chain, audit_engine, anchor_config)
    state.chain_anchor = chain_anchor


async def bootstrap_slo_services(app: FastAPI, cache_manager: Any) -> None:
    """Initialize SLO engine, webhook client, breach detector."""
    state = get_app_state(app)

    import httpx

    from anonreq.services.breach_detector import BreachDetector
    from anonreq.services.slo_engine import SLOEngine

    slo_engine = SLOEngine(cache_manager, "config/slo.yaml")
    state.slo_engine = slo_engine

    webhook_client = httpx.AsyncClient(follow_redirects=False)
    state.webhook_client = webhook_client

    breach_detector = BreachDetector(
        slo_engine=slo_engine,
        audit_chain=state.audit_chain,
        cache_manager=cache_manager,
        http_client=webhook_client,
        config_path="config/webhook.yaml",
    )
    state.breach_detector = breach_detector


async def bootstrap_governance_services(app: FastAPI, cache_manager: Any) -> None:
    """Oversight, lifecycle, transparency, notification, approval."""
    state = get_app_state(app)

    from anonreq.governance.approval import ApprovalManager
    from anonreq.services.lifecycle import LifecycleService
    from anonreq.services.notifications import NotificationService
    from anonreq.services.oversight import OversightService
    from anonreq.services.transparency import TransparencyService

    state.oversight_service = OversightService(cache_manager)
    state.lifecycle_service = LifecycleService(cache_manager)
    state.transparency_service = TransparencyService(cache_manager)
    state.notification_service = NotificationService(cache_manager)

    state.approval_manager = ApprovalManager(
        cache_manager=cache_manager,
        oversight_service=state.oversight_service,
        ttl=settings.CACHE_TTL_SECONDS,
    )
    log.info(
        "ApprovalManager initialized",
        component="lifespan",
        ttl=settings.CACHE_TTL_SECONDS,
    )


async def bootstrap_gateway_services(app: FastAPI) -> None:
    """AI detector, route table, PAC generator, MCP inspector."""
    state = get_app_state(app)

    from anonreq.discovery.flow_analyzer import FlowAnalyzer
    from anonreq.discovery.hostname_allowlist import HostnameAllowlist
    from anonreq.gateway.detector import AIDetector
    from anonreq.gateway.passthrough import GatewayStatus
    from anonreq.gateway.router import RouteTable
    from anonreq.proxy.pac import PACGenerator

    state.gateway_status = GatewayStatus()
    state.ai_detector = AIDetector()
    state.route_table = RouteTable()

    allowlist = HostnameAllowlist()
    flow_analyzer = FlowAnalyzer()
    state.allowlist = allowlist
    state.flow_analyzer = flow_analyzer

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

    try:
        from anonreq.mcp.inspector import MCPInspector as MCPInspectorCls

        mcp_inspector = MCPInspectorCls(flow_analyzer, allowlist)
        state.mcp_inspector = mcp_inspector
        log.info("MCP inspector initialized", component="lifespan")
    except Exception as exc:
        log.warning("MCP inspector not available", component="lifespan", error=str(exc))

    log.info("Phase 17 gateway services initialized", component="lifespan")


async def bootstrap_soc_services(app: FastAPI) -> None:
    """SOC normalizer, MITRE mapper, SIEM sinks."""
    state = get_app_state(app)

    from anonreq.soc.config import SOCConfig
    from anonreq.soc.mitre import MITREMapper
    from anonreq.soc.normalizer import SOCNormalizer

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
        log.warning("SOC Integration Service not available", component="lifespan", error=str(exc))

    try:
        from anonreq.soc.sink_config import SinkConfigLoader
        from anonreq.soc.sink_factory import build_sinks

        sink_loader = SinkConfigLoader("config/soc-sinks.yaml")
        sink_definitions = sink_loader.load()
        sink_router, sink_health_monitor = build_sinks(sink_definitions)

        await sink_router.start_all()
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

    # Wire SOC normalizer fan-out to sink router
    if state.soc_normalizer is not None and state.soc_sink_router is not None:
        state.soc_normalizer.register_sink_callback(
            "sink_router",
            state.soc_sink_router.fan_out,
        )
        log.info("SOC normalizer fan-out registered to sink router", component="lifespan")


async def bootstrap_deployment_proxy(app: FastAPI, cache_manager: Any) -> None:
    """Create and optionally start the deployment proxy."""
    state = get_app_state(app)

    from anonreq.proxy.pipeline_dispatcher import PipelineContentDispatcher

    try:
        if state.pipeline is not None:
            dispatcher = PipelineContentDispatcher(
                state.pipeline,
                app_state=state,
            )
        else:
            def dispatcher(_request: Any) -> bytes:
                return b""

        from anonreq.main import _network_proxy_autostart_enabled, create_deployment_proxy

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


async def bootstrap_trust_center(app: FastAPI, cache_manager: Any) -> None:
    """Trust center service and rate limiter."""
    state = get_app_state(app)

    from anonreq.trust_center.config import TrustCenterSettings as TrustCenterConfig
    from anonreq.trust_center.service import TrustCenterRateLimiter, TrustCenterService

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
        log.error("Trust Center initialisation failed", component="lifespan", error=str(exc))
        state.trust_center_enabled = False


async def bootstrap_compliance_services(app: FastAPI) -> None:
    """Compliance evidence service and license validation."""
    state = get_app_state(app)

    from anonreq.license.validator import LicenseValidator
    from anonreq.services.compliance_evidence import ComplianceEvidenceService

    compliance_evidence_service = ComplianceEvidenceService(
        slo_engine=state.slo_engine,
        audit_chain=state.audit_chain,
        governance_service=None,
        incident_service=None,
    )
    state.compliance_evidence_service = compliance_evidence_service

    license_status = await LicenseValidator.validate_license()
    log.info(
        "License validation complete",
        component="lifespan",
        valid=license_status.valid,
        tier=license_status.tier.value if license_status.tier else None,
        features=[f.value for f in license_status.features],
        organization=license_status.organization,
    )
