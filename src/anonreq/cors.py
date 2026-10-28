"""Optional browser CORS.

``ANONREQ_CORS_ORIGINS`` is a comma-separated origin list. When the
variable is unset or empty, no CORS middleware is installed.
"""

from __future__ import annotations

from typing import Any

from fastapi.middleware.cors import CORSMiddleware

from anonreq.config import settings


def parse_cors_origins(raw: str | None) -> list[str]:
    """Split a comma-separated origin list. Blank entries are dropped."""
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def apply_cors(app: Any, origins: list[str] | None = None) -> None:
    """Install CORSMiddleware when at least one origin is configured."""
    allowed = parse_cors_origins(settings.CORS_ORIGINS) if origins is None else origins
    if not allowed:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
        allow_credentials="*" not in allowed,
        allow_methods=["*"],
        allow_headers=["*"],
    )
