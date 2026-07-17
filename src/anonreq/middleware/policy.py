from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from structlog import get_logger

from anonreq.models.processing_context import ProcessingContext

logger = get_logger("anonreq.middleware.policy")

_SKIP_PATHS = {"/health", "/health/ready", "/metrics", "/"}


class PolicyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    @staticmethod
    def _extract_tenant_id(request: Request) -> str:
        """Extract tenant_id from the authenticated principal, falling back to 'default'."""
        principal = getattr(request.state, "oidc_principal", None)
        if isinstance(principal, dict):
            return principal.get("tenant_id", "default") or "default"
        return "default"

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path in _SKIP_PATHS or not request.url.path.startswith("/v1/"):
            return await call_next(request)

        pdp = getattr(request.app.state, "pdp", None)
        pep = getattr(request.app.state, "pep", None)
        if pdp is None or pep is None:
            logger.error("policy_middleware.not_configured", path=request.url.path)
            return await call_next(request)

        ctx = ProcessingContext(
            request_id=getattr(request.state, "request_id", "unknown"),
            tenant_id=self._extract_tenant_id(request),
        )

        try:
            decision = await pdp.evaluate_all(ctx)
            ctx.policy_decision = decision
        except Exception:
            logger.exception("policy_middleware.pdp_error", path=request.url.path)
            return JSONResponse(
                status_code=503,
                content={"error": "Policy evaluation unavailable"},
                headers={"X-AnonReq-Blocked": "true"},
            )

        try:
            result = await pep.enforce(decision, ctx)
            ctx.policy_enforcement = result
        except Exception:
            logger.exception("policy_middleware.pep_error", path=request.url.path)
            return JSONResponse(
                status_code=503,
                content={"error": "Policy enforcement unavailable"},
                headers={"X-AnonReq-Blocked": "true"},
            )

        if not result.should_forward:
            return JSONResponse(
                status_code=result.status_code or 403,
                content=result.body or {"reason": "Request blocked by policy"},
                headers=result.headers,
            )

        response = await call_next(request)

        for key, value in result.headers.items():
            response.headers[key] = value

        return response
