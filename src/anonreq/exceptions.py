"""Custom exception hierarchy and global exception handler for AnonReq.

Provides fail-secure error handling per D-01, D-02:
- Every unhandled exception returns a safe, OpenAI-compatible error envelope
- No stack traces, request bodies, header content, env var values, file paths,
  or dependency URLs are ever included in error responses
- request_id is propagated through all error envelopes for trace correlation

Threat model coverage:
- T-01-03-01 (Information Disclosure): Every exception returns generic error
  envelope. No internals leak to the client.
"""

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
def _extract_request_id(request: Request) -> str:
    """Extract or generate a request_id for error trace correlation.

    Priority:
    1. request.state.request_id if middleware set it
    2. X-Request-ID header from client
    3. structlog contextvars (bound by middleware via bind_contextvars)
    4. Fallback to 'unknown'

    This is a best-effort extraction — the middleware that binds
    request_id to structlog contextvars runs in a later phase.
    """
    # Try to get from request state (set by middleware in Phase 2)
    if hasattr(request, "state") and hasattr(request.state, "request_id"):
        rid: str | None = getattr(request.state, "request_id", None)
        if rid:
            return rid

    # Try to get from X-Request-ID header
    rid = request.headers.get("X-Request-ID")
    if rid:
        return rid

    return "unknown"


def _make_error_body(
    message: str,
    error_type: str,
    code: str,
    request_id: str,
) -> dict[str, dict[str, Any]]:
    """Build an OpenAI-compatible error response envelope.

    The envelope format follows OpenAI's error response schema:
    ``{"error": {"message": str, "type": str, "code": str, "request_id": str}}``

    Args:
        message: Human-readable error message (no internals).
        error_type: Machine-readable error category (e.g., "internal_error").
        code: Specific error code (e.g., "dependency_unavailable").
        request_id: Correlation ID for this request.

    Returns:
        A dict with a single ``error`` key containing the envelope.
    """
    return {
        "error": {
            "message": message,
            "type": error_type,
            "code": code,
            "request_id": request_id,
        }
    }


class AnonReqError(Exception):
    """Base exception for all AnonReq-specific errors.

    All subclasses define:
        message (str): Safe, user-facing error message (no internals).
        error_type (str): Machine-readable error category.
        status_code (int): HTTP status code.
        code (str): Specific error code.
        request_id (str | None): Correlation ID for traceability.
    """

    def __init__(
        self,
        message: str = "An internal error occurred",
        error_type: str = "internal_error",
        status_code: int = 500,
        code: str = "internal_error",
        request_id: str | None = None,
    ) -> None:
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        super().__init__(self.message)


class DependencyUnavailableError(AnonReqError):
    """Raised when a required dependency (Valkey, Presidio) is unreachable.

    Returns HTTP 503 with type ``service_unavailable`` and code
    ``dependency_unavailable``. The message includes the dependency name
    but no connection details (URLs, ports, or stack traces).
    """

    def __init__(
        self,
        dependency: str,
        request_id: str | None = None,
    ) -> None:
        self.dependency = dependency
        super().__init__(
            message=f"{dependency} unavailable",
            error_type="service_unavailable",
            status_code=503,
            code="dependency_unavailable",
            request_id=request_id,
        )


class PipelineAbortError(AnonReqError):
    """Raised by pipeline stages to abort execution with a specific HTTP status.

    Carries a ``status_code`` for the HTTP response and a generic safe message
    that does not leak implementation details per D-02.
    """

    def __init__(
        self,
        status_code: int = 500,
        message: str = "Pipeline aborted",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_type="pipeline_abort",
            status_code=status_code,
            code="pipeline_abort",
            request_id=request_id,
        )


class PipelineBlockedError(PipelineAbortError):
    """Raised when DLP or PDP #2 blocks a request (HTTP 451).

    Used by the DLP pipeline and PDP #2 to signal that a request or
    response should be blocked due to DLP policy.  The 451 status code
    is semantically appropriate: "Unavailable For Legal Reasons" —
    the content is being withheld due to an legal/regulatory policy
    (DLP, data classification, etc.).

    Threat model: T-13-02-01 (Loosening DLP via classification)
    — this error ensures blocked content never reaches the provider.
    """

    def __init__(
        self,
        detail: str = "Request blocked by DLP policy",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            status_code=451,
            message=detail,
            request_id=request_id,
        )


class OutboundDLPError(PipelineAbortError):
    """Raised when outbound DLP detects exfiltration in the LLM response.

    The provider successfully produced a response, but the response
    contains content that the outbound DLP scan flags as a policy
    violation.  The response is suppressed — the client receives
    HTTP 451 instead.

    Threat model: T-13-02-02 (Outbound DLP failure)
    — inbound DLP is the primary guard; outbound DLP is a secondary
    layer.  If outbound DLP fails open (cannot inspect), the response
    passes through rather than being incorrectly suppressed.
    """

    def __init__(
        self,
        detail: str = "Outbound DLP blocked response",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            status_code=451,
            message=detail,
            request_id=request_id,
        )


class AuthenticationError(AnonReqError):
    """Raised when API key validation fails.

    Returns HTTP 401 with type ``authentication_error`` and code
    ``invalid_api_key``. The message is generic — no indication of
    whether the API key was missing, malformed, or expired.
    """

    def __init__(
        self,
        message: str = "Invalid API key",
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_type="authentication_error",
            status_code=401,
            code="invalid_api_key",
            request_id=request_id,
        )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler that returns fail-secure error responses.

    Handles all uncaught exceptions and returns an OpenAI-compatible error
    envelope. This is the last line of defense — no internals should ever
    leak past this handler.

    Handler logic:
    1. If ``AnonReqError`` subclass: return its structured body directly.
    2. If ``HTTPException``: delegate to ``http_exception_handler``.
    3. If ``ValidationError`` (Pydantic): return 422 with generic message.
    4. All other exceptions: return generic 500 with no details.
    5. **Never** include: stack trace, request body, header content, env var
       values, file paths, or dependency URLs.

    Args:
        request: The incoming FastAPI request.
        exc: The unhandled exception.

    Returns:
        A ``JSONResponse`` with the OpenAI-compatible error envelope.
    """
    request_id = _extract_request_id(request)

    # AnonReqError subclasses have their own structured error data
    if isinstance(exc, AnonReqError):
        exc.request_id = exc.request_id or request_id  # type: ignore[union-attr]
        body = _make_error_body(
            message=exc.message,
            error_type=exc.error_type,
            code=exc.code,
            request_id=exc.request_id or request_id,
        )
        return JSONResponse(status_code=exc.status_code, content=body)

    # HTTPException needs special handling (used by FastAPI auth, etc.)
    if isinstance(exc, HTTPException):
        body = _make_error_body(
            message=exc.detail if isinstance(exc.detail, str) else "HTTP error",
            error_type="http_error",
            code="http_error",
            request_id=request_id,
        )
        return JSONResponse(status_code=exc.status_code, content=body)

    # Pydantic ValidationError
    if isinstance(exc, ValidationError):
        body = _make_error_body(
            message="Invalid request parameters",
            error_type="internal_error",
            code="internal_error",
            request_id=request_id,
        )
        return JSONResponse(status_code=422, content=body)

    # Log the actual error before returning generic response.
    # We use structlog directly — if logging_config.setup_logging() hasn't
    # been called yet, structlog uses its default configuration which
    # writes to stderr. This is safe because structlog is a core dependency
    # installed at build time, so the import will always succeed.
    import structlog  # noqa: F811

    logger = structlog.get_logger()
    logger.error(
        "exception_handler.unhandled",
        error_type=type(exc).__name__,
        request_id=request_id,
    )

    # Generic 500 — never leak the original exception
    body = _make_error_body(
        message="Internal gateway error",
        error_type="internal_error",
        code="internal_error",
        request_id=request_id,
    )
    return JSONResponse(status_code=500, content=body)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler specifically for HTTPException instances.

    FastAPI raises HTTPException for various built-in scenarios including
    HTTPBearer authentication failures (401). This handler ensures all
    HTTPExceptions get the same safe envelope treatment.

    Args:
        request: The incoming FastAPI request.
        exc: The HTTPException that was raised.

    Returns:
        A ``JSONResponse`` with the OpenAI-compatible error envelope.
    """
    request_id = _extract_request_id(request)
    body = _make_error_body(
        message=exc.detail if isinstance(exc.detail, str) else "HTTP error",
        error_type="http_error",
        code="http_error",
        request_id=request_id,
    )

    if exc.status_code == 451:
        ctx = getattr(request.state, "ctx", None)
        if ctx and getattr(ctx, "classification_result_v2", None):
            res = ctx.classification_result_v2
            body["classification"] = {
                "highest": res.highest.name,
                "labels": res.labels,
                "reason": exc.detail if isinstance(exc.detail, str) else "Request blocked due to classification policy",
            }
        else:
            body["classification"] = {
                "highest": "HIGHLY_RESTRICTED",
                "labels": [],
                "reason": exc.detail if isinstance(exc.detail, str) else "Request blocked due to classification policy",
            }

    return JSONResponse(status_code=exc.status_code, content=body)
