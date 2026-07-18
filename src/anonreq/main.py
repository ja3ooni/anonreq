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
from starlette.responses import StreamingResponse
from structlog import get_logger

from anonreq.__about__ import __version__
from anonreq.admin.routes import admin_router
from anonreq.api.v1.admin.audit import router as admin_audit_router
from anonreq.auth.oidc import build_oidc_verifier
from anonreq.bootstrap.services import (
    bootstrap_audit_services,
    bootstrap_compliance_services,
    bootstrap_deployment_proxy,
    bootstrap_gateway_services,
    bootstrap_governance_services,
    bootstrap_locale_detection,
    bootstrap_mitm_proxy,
    bootstrap_policy_engine,
    bootstrap_slo_services,
    bootstrap_soc_services,
    bootstrap_trust_center,
)
from anonreq.cache.manager import CacheManager
from anonreq.config import settings
from anonreq.dependencies import auth_context
from anonreq.deployment.modes import DeploymentMode, TopologyConfig, get_deployment_config
from anonreq.discovery.admin_router import router as discovery_admin_router
from anonreq.discovery.inventory import AssetInventory
from anonreq.exceptions import (
    DependencyUnavailableError,
    global_exception_handler,
    http_exception_handler,
)
from anonreq.firewall.pipeline import FirewallPipeline
from anonreq.gateway.passthrough import GatewayStatus
from anonreq.governance.router import (
    approval_router as approval_record_router,
)
from anonreq.governance.router import (
    governance_router as governance_record_router,
)
from anonreq.health import router as health_router
from anonreq.license.router import router as license_router
from anonreq.license.validator import require_license
from anonreq.logging_config import setup_logging
from anonreq.middleware.classification import ClassificationMiddleware
from anonreq.middleware.content_type import ContentTypeMiddleware
from anonreq.middleware.mtls import IngressMTLSMiddleware
from anonreq.middleware.policy import PolicyMiddleware
from anonreq.middleware.response_headers import ClassificationResponseMiddleware
from anonreq.middleware.tenant import TenantContextMiddleware
from anonreq.models.request_context import RequestContext
from anonreq.monitoring.middleware import MetricsMiddleware
from anonreq.multimodal.dispatcher import ContentTypeDispatcher
from anonreq.multimodal.json_analyzer import JsonAnalyzer
from anonreq.multimodal.multipart_analyzer import MultipartAnalyzer
from anonreq.providers.registry import ProviderRegistry
from anonreq.proxy.detection import AITrafficDetector
from anonreq.proxy.modes import (
    ProxyMode,
    get_pipeline_for_mode,
    mode_from_env,
    proxy_mode_description,
)
from anonreq.proxy.pac import router as pac_router
from anonreq.proxy.reverse_proxy import ReverseProxy
from anonreq.proxy.tls_interceptor import TLSInterceptor as DynamicTLSInterceptor
from anonreq.proxy.transparent_proxy import TransparentProxy
from anonreq.routes.compliance import router as compliance_router
from anonreq.routes.governance import router as governance_router
from anonreq.routes.models import router as models_router
from anonreq.routes.oversight import router as oversight_router
from anonreq.routing.alias_registry import AliasRegistry
from anonreq.routing.chat import router as chat_router
from anonreq.secrets.bootstrap import bootstrap_runtime_secret_store
from anonreq.secrets.reloader import bootstrap_runtime_secret_reloader
from anonreq.secrets.rotation import SecretRotationBuffer
from anonreq.secrets.store import RuntimeSecretStore, set_runtime_secret_store
from anonreq.startup_checks import run_startup_checks
from anonreq.state import get_app_state
from anonreq.tenant.registry import TenantRegistry
from anonreq.trust_center.router import router as trust_center_router

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
    return os.environ.get("ANONREQ_START_NETWORK_PROXY", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def create_deployment_proxy(
    topology: TopologyConfig,
    dispatcher: Any,
) -> ReverseProxy | TransparentProxy:
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


def bootstrap_secret_volume_reloader(app: FastAPI) -> Any:
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

        # Per D-07/D-08: Configure KMS backend for cache encryption
        kms_backend = settings.KMS_BACKEND.strip().lower()
        if kms_backend == "local":
            from anonreq.kms.cache import InMemoryKeyCache
            from anonreq.kms.local import LocalAES256GCM

            master_key = os.environ.get("ANONREQ_KMS_MASTER_KEY", "")
            if not master_key:
                # Generate ephemeral master key for dev/testing (not for production)
                master_key = LocalAES256GCM.generate_master_key()
            key_cache = InMemoryKeyCache(ttl_seconds=settings.CACHE_TTL_SECONDS)
            kms_client = LocalAES256GCM(master_key=master_key, key_cache=key_cache)
            cache_manager._kms = kms_client
            state.kms_client = kms_client
        else:
            log.warning(
                "KMS backend '%s' not yet implemented, cache encryption disabled",
                kms_backend,
            )
        state.secret_reloader = bootstrap_secret_volume_reloader(app)
        state.alias_registry = AliasRegistry(
            provider_registry=state.provider_registry
        )

        # Discovery inventory service
        state.inventory_service = AssetInventory()

        # ContentTypeDispatcher reference on app state
        state.content_type_dispatcher = _content_type_dispatcher

        # Domain-specific bootstrap sequence
        await bootstrap_locale_detection(app, cache_manager)
        await bootstrap_policy_engine(app, cache_manager)
        await bootstrap_mitm_proxy(app)
        await bootstrap_audit_services(app)
        await bootstrap_slo_services(app, cache_manager)
        await bootstrap_governance_services(app, cache_manager)
        await bootstrap_gateway_services(app)
        await bootstrap_soc_services(app)
        await bootstrap_deployment_proxy(app, cache_manager)
        await bootstrap_trust_center(app, cache_manager)
        await bootstrap_compliance_services(app)

        log.info("Pre-flight checks passed, accepting traffic", component="lifespan")
        yield

        # Clean shutdown
        await _shutdown(state, cache_manager)

    app = FastAPI(
        title="AnonReq",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Register fail-secure exception handlers (order matters — specific first)
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
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

    # TenantContextMiddleware — validates X-AnonReq-Tenant-ID header,
    # rejects missing/invalid/disabled tenants, sets request.state.tenant_id.
    # Runs after PolicyMiddleware but before ClassificationResponseMiddleware
    # per D-02: after auth, before classification.
    tenant_registry = TenantRegistry(yaml_path=settings.TENANTS_CONFIG_PATH)
    app.state.tenant_registry = tenant_registry
    app.add_middleware(TenantContextMiddleware, tenant_registry=tenant_registry)

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
    async def set_request_context(
        request: Request, call_next: Callable[..., Any]
    ) -> StreamingResponse:
        request_id = f"req_{uuid4().hex[:24]}"
        request.state.request_id = request_id
        request.state.context = RequestContext(request_id=request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response: StreamingResponse = await call_next(request)
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
        gs: GatewayStatus | None = get_app_state(app).gateway_status
        if gs is None:
            return {"status": "unavailable"}
        result: dict[str, Any] = gs.get_status()
        return result

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


async def _shutdown(state: Any, cache_manager: Any) -> None:
    """Ordered teardown of all lifespan-managed services."""
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


app = create_app()
"""Module-level application instance for uvicorn.

Usage:
    ``uvicorn anonreq.main:app --host 0.0.0.0 --port 8080``
"""
