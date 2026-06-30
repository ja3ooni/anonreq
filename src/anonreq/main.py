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

from anonreq.__about__ import __version__
from anonreq.config import settings
from anonreq.dependencies import auth_context
from anonreq.exceptions import (
    DependencyUnavailableError,
    global_exception_handler,
    http_exception_handler,
)
from anonreq.health import router as health_router
from anonreq.logging_config import setup_logging
from anonreq.models.request_context import RequestContext
from anonreq.startup_checks import run_startup_checks

log = get_logger()


def create_app() -> FastAPI:
    """Create and configure the AnonReq FastAPI application.

    Configures:
    - Structured logging with field allowlist via ``setup_logging()``.
    - Lifespan context manager that runs pre-flight dependency checks.
    - Exception handlers for ``Exception`` and ``HTTPException`` (fail-secure).
    - Health routes (``GET /health``, ``GET /health/ready``).
    - Root ``GET /`` returning service metadata.

    Returns:
        A configured FastAPI application instance.
    """
    # Configure structured logging first
    setup_logging(level="INFO")

    # Create lifespan context manager
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        log.info("Starting pre-flight checks", component="lifespan")
        try:
            await run_startup_checks(settings)
        except DependencyUnavailableError:
            log.error("Pre-flight check failed", component="lifespan")
            raise
        log.info("Pre-flight checks passed, accepting traffic", component="lifespan")
        yield
        log.info("Shutting down", component="lifespan")

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

    @app.get("/")
    async def root(ctx=Depends(auth_context)):
        return {"service": "AnonReq", "version": __version__}

    return app


app = create_app()
"""Module-level application instance for uvicorn.

Usage:
    ``uvicorn anonreq.main:app --host 0.0.0.0 --port 8080``
"""
