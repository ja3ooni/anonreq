"""RequestContext dataclass for request-scoped correlation data.

Provides:
- ``RequestContext``: A dataclass holding request_id, tenant_id, and
  session_id for correlation across logs, errors, and metrics.

Per D-11, D-12:
- tenant_id defaults to "default" (single-tenant in Phase 1)
- request_id auto-generated using uuid4 if not provided
- session_id is optional (populated in Phase 2+)
"""

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class RequestContext:
    """Request-scoped context for trace correlation.

    Propagated through every authenticated request via FastAPI dependency
    injection. Used by logging, exception handling, and metrics to
    correlate events to a specific request.

    Attributes:
        request_id: Unique identifier for this request, auto-generated as
            ``req_<24 hex chars>`` if not provided.
        tenant_id: Tenant identifier. Defaults to ``"default"`` per D-11
            (single-tenant in Phase 1).
        session_id: Optional session identifier. Populated in Phase 2+
            when session-scoped token mappings are introduced.
    """

    request_id: str = field(default_factory=lambda: f"req_{uuid4().hex[:24]}")
    tenant_id: str = "default"
    session_id: str | None = None
