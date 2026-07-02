"""Model-list endpoint exposing configured model aliases."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/v1", tags=["models"])


@router.get("/models")
async def list_models(request: Request) -> dict[str, Any]:
    """Return configured aliases in OpenAI-compatible list format."""

    alias_registry = request.app.state.alias_registry
    created = int(time.time())
    data = []
    for alias_name, alias in alias_registry.list_aliases().items():
        data.append(
            {
                "id": alias_name,
                "object": "model",
                "created": created,
                "owned_by": "anonreq",
                "metadata": alias.metadata,
            }
        )
    return {"object": "list", "data": data}
