"""FastAPI application factory and entrypoint for the AnonReq gateway.

Provides:
- ``create_app()`` factory that wires exception handlers, logging, health
  routes, and startup checks
- Module-level ``app = create_app()`` for uvicorn
- Root ``GET /`` returning service metadata

Per D-01, D-02, FAIL-01, FAIL-02, FAIL-03, FAIL-04:
- Global exception handlers ensure fail-secure error responses
- Lifespan context manager runs pre-flight dependency checks
- Health endpoint exposes component status
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException

from anonreq.__about__ import __version__
from anonreq.exceptions import global_exception_handler, http_exception_handler


def create_app() -> FastAPI:
    """Create and configure the AnonReq FastAPI application.

    Wires:
    - Exception handlers for ``Exception`` and ``HTTPException`` (fail-secure).
    - Root ``GET /`` returning service metadata.

    Note:
        Lifespan context manager, health routes, and startup checks are
        wired by Task 3 of this plan. For now the app is minimal with
        exception handlers and root route only.

    Returns:
        A configured FastAPI application instance.
    """
    app = FastAPI(
        title="AnonReq",
        version=__version__,
        docs_url=None,
        redoc_url=None,
    )

    # Register fail-secure exception handlers (order matters — specific first)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    @app.get("/")
    async def root():
        return {"service": "AnonReq", "version": __version__}

    return app


app = create_app()
"""Module-level application instance for uvicorn.

Usage:
    ``uvicorn anonreq.main:app --host 0.0.0.0 --port 8080``
"""
