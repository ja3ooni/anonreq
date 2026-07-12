"""ForwardingGuard — model approval and provider active checks for MRM (SR 11-7).

Per D-007, these governance-level checks gate outbound LLM traffic based on
model approval status (SR 11-7 Model Risk Management) and provider suspension
status (DORA ICT).  They are called from the pipeline ForwardingGuard or
routing layer before any provider dispatch.

Instrumentation:
- ``anonreq_model_approval_gates_total`` Prometheus counter (result="allowed"|"blocked")
- ``model_approval_gated`` / ``provider_suspended`` audit events via structlog
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prometheus_client import Counter
from structlog import get_logger

from anonreq.exceptions import AnonReqError

if TYPE_CHECKING:
    from anonreq.governance.model_inventory import ModelInventory
    from anonreq.governance.provider_inventory import ProviderInventory

logger = get_logger("anonreq.governance.forwarding_guard")

# Prometheus counter for model approval gates (D-007 instrumentation)
model_approval_gates = Counter(
    "anonreq_model_approval_gates_total",
    "Total model approval gate checks, partitioned by result",
    labelnames=["result"],
)


class ModelNotApprovedError(AnonReqError):
    """Raised when a model is not approved for use (HTTP 403).

    Per D-007: unapproved or unknown models are blocked at the ForwardingGuard.
    This is a fail-secure behaviour — unknown models default to not-approved.
    """

    def __init__(
        self,
        provider: str,
        model_name: str,
        request_id: str | None = None,
    ) -> None:
        self.provider = provider
        self.model_name = model_name
        super().__init__(
            message=f"Model '{provider}/{model_name}' is not approved for use",
            error_type="model_not_approved",
            status_code=403,
            code="model_not_approved",
            request_id=request_id,
        )


class ProviderSuspendedError(AnonReqError):
    """Raised when a provider has been suspended (HTTP 403).

    Per D-011: provider suspension immediately blocks all traffic to that
    provider.  This check runs inline in the dispatch path.
    """

    def __init__(
        self,
        provider_id: str,
        request_id: str | None = None,
    ) -> None:
        self.provider_id = provider_id
        super().__init__(
            message=f"Provider '{provider_id}' is suspended",
            error_type="provider_suspended",
            status_code=403,
            code="provider_suspended",
            request_id=request_id,
        )


async def check_model_approval(
    model_inventory: ModelInventory,
    provider: str,
    model_name: str,
    request_id: str | None = None,
    audit_logger: Any | None = None,
) -> None:
    """Check whether a model is approved and raise if not.

    Per D-007: every outbound request must pass this check before reaching
    the provider.  Unknown models default to not-approved (fail-secure).

    Args:
        model_inventory: Model inventory service for approval queries.
        provider: The LLM provider name (e.g., "openai").
        model_name: The model name (e.g., "gpt-4").
        request_id: Optional request ID for error correlation.
        audit_logger: Optional structlog logger for audit events.

    Raises:
        ModelNotApprovedError: If the model is not approved or unknown.
    """
    approved = await model_inventory.is_model_approved(
        provider=provider,
        model_name=model_name,
    )

    if approved:
        model_approval_gates.labels(result="allowed").inc()
        _emit_audit(
            "model_approval_allowed",
            provider=provider,
            model_name=model_name,
            audit_logger=audit_logger,
        )
        return

    model_approval_gates.labels(result="blocked").inc()
    _emit_audit(
        "model_approval_gated",
        provider=provider,
        model_name=model_name,
        reason="not_approved",
        audit_logger=audit_logger,
    )
    raise ModelNotApprovedError(
        provider=provider,
        model_name=model_name,
        request_id=request_id,
    )


async def check_provider_active(
    provider_inventory: ProviderInventory,
    provider_id: str,
    request_id: str | None = None,
    audit_logger: Any | None = None,
) -> None:
    """Check whether a provider is active and raise if suspended.

    Per D-011: suspended providers must block all traffic.  This check
    runs inline in the dispatch path.

    Args:
        provider_inventory: Provider inventory service for status queries.
        provider_id: The provider record ID.
        request_id: Optional request ID for error correlation.
        audit_logger: Optional structlog logger for audit events.

    Raises:
        ProviderSuspendedError: If the provider is not active.
    """
    active = await provider_inventory.is_provider_active(
        provider_id=provider_id,
    )

    if active:
        return

    _emit_audit(
        "provider_suspended",
        provider_id=provider_id,
        reason="blocked_by_suspension",
        audit_logger=audit_logger,
    )
    raise ProviderSuspendedError(
        provider_id=provider_id,
        request_id=request_id,
    )


def _emit_audit(event_type: str, audit_logger: Any | None = None, **fields: Any) -> None:
    """Emit a structured audit event via structlog."""
    log = audit_logger or logger
    log.info(event_type, **fields)
