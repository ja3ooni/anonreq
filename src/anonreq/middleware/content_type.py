from __future__ import annotations

import json
from typing import Any, Callable

import structlog

from anonreq.multimodal.dispatcher import ContentTypeDispatcher
from anonreq.multimodal.models import ContentType

logger = structlog.get_logger("anonreq.middleware.content_type")


class ContentTypeMiddleware:
    def __init__(
        self,
        app: Any,
        dispatcher: ContentTypeDispatcher | None = None,
    ) -> None:
        self.app = app
        self._dispatcher = dispatcher

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http" or self._dispatcher is None:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_type_header = headers.get(b"content-type", b"").decode("utf-8", errors="replace")

        result = await self._dispatcher.dispatch(content_type_header, b"", None)

        if result.action == "ROUTE_LOCAL" and result.content_type == ContentType.UNKNOWN:
            logger.warning(
                "content_type.rejected",
                content_type=content_type_header,
                action="ROUTE_LOCAL",
            )
            body = json.dumps({
                "error": {
                    "message": f"Unsupported Content-Type: {content_type_header}",
                    "type": "unsupported_media_type",
                    "code": "unsupported_media_type",
                }
            }).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 415,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        scope["state"] = {**(scope.get("state", {})), "multimodal_result": result}
        await self.app(scope, receive, send)
