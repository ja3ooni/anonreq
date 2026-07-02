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

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import uuid4

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response
from structlog import get_logger

from prometheus_client import generate_latest, REGISTRY

from anonreq.__about__ import __version__
from anonreq.cache.manager import CacheManager
from anonreq.cache.health import check_cache_health
from anonreq.config import settings
from anonreq.compliance.engine import PresetEngine
from anonreq.services.audit_chain import AuditChainService, AuditConfig
from anonreq.services.chain_anchor import ChainAnchorService, AnchorConfig
from sqlalchemy.ext.asyncio import create_async_engine
from anonreq.admin.routes import admin_router
from anonreq.proxy.ca_manager import CAManager
from anonreq.proxy.mitm_handler import MITMHandler, mitm_middleware
from anonreq.proxy.tls import TLSInterceptor, ConfigurationError
from anonreq.dependencies import auth_context
from anonreq.detection.presidio_client import PresidioClient
from anonreq.exceptions import (
    DependencyUnavailableError,
    global_exception_handler,
    http_exception_handler,
)
from anonreq.health import router as health_router
from anonreq.locale.checksum import ChecksumValidatorRegistry
from anonreq.locale.merger import RecognizerMerger
from anonreq.locale.negotiator import LocaleNegotiator
from anonreq.locale.registry import LocaleRegistry
from anonreq.logging_config import setup_logging
from anonreq.middleware.classification import ClassificationMiddleware
from anonreq.middleware.policy import PolicyMiddleware
from anonreq.monitoring.middleware import MetricsMiddleware
from anonreq.models.request_context import RequestContext
from anonreq.providers.registry import ProviderRegistry
from anonreq.routing.chat import build_pipeline, router as chat_router
from anonreq.routes.compliance import router as compliance_router
from anonreq.governance.router import governance_router as governance_record_router
from anonreq.routes.governance import router as governance_router
from anonreq.routes.oversight import router as oversight_router
from anonreq.routes.models import router as models_router
from anonreq.routing.alias_registry import AliasRegistry
from anonreq.startup_checks import run_startup_checks

log = get_logger()


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

    # Create lifespan context manager
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        log.info("Starting pre-flight checks", component="lifespan")

        # Create cache manager for the application lifetime
        cache_manager = CacheManager(
            settings.VALKEY_URL,
            ttl=settings.CACHE_TTL_SECONDS,
        )

        # Run pre-flight health checks on cache during startup
        try:
            cache_health = await check_cache_health(cache_manager)
            if not cache_health.get("healthy", False):
                log.error(
                    "Cache health check failed",
                    component="lifespan",
                    cache_health=cache_health,
                )
                raise DependencyUnavailableError(dependency="cache")
        except Exception:
            await cache_manager.close()
            raise

        try:
            await run_startup_checks(settings)
        except DependencyUnavailableError:
            await cache_manager.close()
            log.error("Pre-flight check failed", component="lifespan")
            raise

        # Store cache_manager on app state for route handlers
        app.state.cache_manager = cache_manager
        app.state.provider_registry = ProviderRegistry()
        app.state.alias_registry = AliasRegistry(
            provider_registry=app.state.provider_registry
        )
        checksum_registry = ChecksumValidatorRegistry()
        locale_registry = LocaleRegistry(checksum_registry=checksum_registry)
        universal_bundle = locale_registry.get("en")
        if universal_bundle is None:
            await cache_manager.close()
            raise RuntimeError("Universal locale bundle 'en' is required")
        app.state.checksum_registry = checksum_registry
        app.state.locale_registry = locale_registry
        app.state.locale_negotiator = LocaleNegotiator(locale_registry)
        app.state.recognizer_merger = RecognizerMerger(universal_bundle)
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
        app.state.preset_engine = preset_engine
        app.state.active_compliance_presets = active_presets

        # Create Presidio client for the application lifetime
        presidio_client = PresidioClient(
            base_url=settings.PRESIDIO_URL,
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
            max_concurrency=10,
        )
        app.state.presidio_client = presidio_client

        # Build and store the pipeline manager
        pipeline = build_pipeline(
            cache_manager=cache_manager,
            presidio_client=presidio_client,
            alias_registry=app.state.alias_registry,
            locale_negotiator=app.state.locale_negotiator,
            recognizer_merger=app.state.recognizer_merger,
            checksum_registry=app.state.checksum_registry,
        )
        app.state.pipeline = pipeline

        # Phase 8: Enterprise Policy Engine
        try:
            from anonreq.policy.config import load_policy_config
            from anonreq.policy.models import RateLimitConfig
            from anonreq.policy.store import PolicyStore
            from anonreq.policy.usage_limiter import UsageLimiter
            from anonreq.policy.spend_controller import SpendController
            from anonreq.policy.residency_router import ResidencyRouter
            from anonreq.policy.pdp import PolicyDecisionPoint
            from anonreq.policy.pep import PolicyEnforcementPoint
            from anonreq.policy.forwarding_guard import ForwardingGuard

            policy_config = load_policy_config("config/policy.yaml")
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

            app.state.pdp = pdp
            app.state.pep = pep
            app.state.forwarding_guard = forwarding_guard
            app.state.policy_store = policy_store
            log.info("Policy engine initialised", component="lifespan")
        except Exception as exc:
            log.error("Failed to initialise policy engine", component="lifespan", error=str(exc))
            await cache_manager.close()
            raise

        # Phase 17: MITM proxy setup
        ca_manager = CAManager(ca_dir=settings.CA_DIR)
        app.state.ca_manager = ca_manager

        ca_info = await ca_manager.get_ca_info()
        if ca_info is None and settings.PROXY_MODE == "transparent":
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
            app.state.mitm_handler = mitm_handler

            @app.middleware("http")
            async def proxy_middleware(request: Request, call_next):
                return await mitm_middleware(request, call_next)

            log.info("MITM proxy middleware registered", component="lifespan")

        # Phase 11: Initialize audit database and services
        audit_engine = create_async_engine(settings.DATABASE_URL)
        app.state.audit_engine = audit_engine
        audit_config = AuditConfig(retention_days=2557)
        audit_chain = AuditChainService(audit_engine, audit_config)
        app.state.audit_chain = audit_chain

        anchor_config = AnchorConfig(
            signing_key=settings.ANCHOR_SIGNING_KEY,
        )
        chain_anchor = ChainAnchorService(audit_chain, audit_engine, anchor_config)
        app.state.chain_anchor = chain_anchor

        # Phase 14: AI Governance & Oversight services
        from anonreq.services.oversight import OversightService
        from anonreq.services.lifecycle import LifecycleService
        from anonreq.services.transparency import TransparencyService
        from anonreq.services.notifications import NotificationService

        app.state.oversight_service = OversightService(cache_manager)
        app.state.lifecycle_service = LifecycleService(cache_manager)
        app.state.transparency_service = TransparencyService(cache_manager)
        app.state.notification_service = NotificationService(cache_manager)

        log.info("Phase 14 governance services initialized", component="lifespan")
        log.info("Pre-flight checks passed, accepting traffic", component="lifespan")
        yield

        # Clean shutdown
        log.info("Shutting down", component="lifespan")
        if hasattr(app.state, "audit_engine"):
            await app.state.audit_engine.dispose()
        if hasattr(app.state, "mitm_handler"):
            await app.state.mitm_handler.close()
        if hasattr(app.state, "ca_manager"):
            await app.state.ca_manager.close()
        await presidio_client.close()
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

    # Add /metrics endpoint for Prometheus scraping (no auth — scrapers
    # connect on internal networks; secured at network level)
    @app.get("/metrics")
    async def metrics():
        return Response(
            content=generate_latest(REGISTRY),
            media_type="text/plain; charset=utf-8",
        )

    # Middleware: set request_id BEFORE auth runs so it's available in
    # 401 error responses (per RESEARCH Open Question 4).
    @app.middleware("http")
    async def set_request_context(request: Request, call_next) -> Response:
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
    app.include_router(oversight_router, dependencies=[Depends(auth_context)])
    app.include_router(admin_router, dependencies=[Depends(auth_context)])

    @app.get("/")
    async def root(ctx=Depends(auth_context)):
        return {"service": "AnonReq", "version": __version__}

    return app


app = create_app()
"""Module-level application instance for uvicorn.

Usage:
    ``uvicorn anonreq.main:app --host 0.0.0.0 --port 8080``
"""
