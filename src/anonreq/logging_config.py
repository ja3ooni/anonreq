"""Structured audit logging configuration with strict field allowlist.

Provides:
- ``setup_logging()``: Configures structlog with processors including the
  custom allowlist processor that drops non-allowlisted fields.
- ``ALLOWLIST``: The set of allowed log field names.
- ``allowlist_processor``: The structlog processor that enforces the allowlist.
- ``get_logger()``: Convenience function for creating a bound logger.

Per D-04, D-05, D-06, AUDT-01, AUDT-02, AUDT-03:
- Structured JSON logs to stdout with timestamp, level, event.
- Strict field allowlist — non-allowlisted fields dropped before serialization.
- request_id propagated via structlog contextvars for trace correlation.
- Log level configurable by settings.LOG_LEVEL.

Threat model coverage:
- T-01-03-02 (Information Disclosure): Field allowlist processor drops
  non-allowlisted keys. Nested-dict limitation documented (acceptable in
  Phase 1 — no request data flows yet). Recursive deep check added in
  Phase 2 when request data flows.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.stdlib import BoundLogger, ProcessorFormatter

# The canonical set of allowed log field names.
# Any key not in this set is dropped by the allowlist processor.
# Per AUDT-02: no raw prompt text, raw response text, tokens, entity values,
# credentials, or internal URLs in logs.
ALLOWLIST: frozenset[str] = frozenset({
    "timestamp",
    "level",
    "event",
    "request_id",
    "component",
    "status_code",
    "duration_ms",
    "error_type",
    "version",
    "session_id",
    "provider",
    "model",
    "entity_counts",
    "latency_ms",
    "compliance_preset",
    "locale",
})


def allowlist_processor(
    logger: structlog.stdlib.BoundLogger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor that drops non-allowlisted fields.

    Iterates over top-level keys in the event dict and deletes any key
    not in ``ALLOWLIST``. This prevents accidental logging of sensitive
    data (PII, credentials, internal paths) by rejecting unknown keys.

    **Important limitation (per RESEARCH Pitfall 1):**
    This processor only checks *top-level* keys. Nested dict values
    (e.g., ``log.info("msg", data={"sensitive": "value"})``) are NOT
    recursively scanned. The key ``"data"`` would be dropped because it
    is not in the allowlist, **but** if the nested dict is assigned to
    an allowlisted key, its contents would NOT be filtered.

    In Phase 1, this is acceptable — the log surface is infrastructure-only
    (exception handling, startup checks, health probes). No request data
    flows through the logging system yet.

    In Phase 2, when request/response data flows through the pipeline,
    a recursive deep-check processor MUST be added to scan allowlisted
    keys' values for nested sensitive data.

    Args:
        logger: The structlog logger instance.
        method_name: The logging method (``info``, ``error``, etc.).
        event_dict: The structured log event dict.

    Returns:
        The filtered event dict with non-allowlisted keys removed.
    """
    # Iterate over a frozen list of keys so we can safely delete during iteration
    for key in list(event_dict.keys()):
        if key not in ALLOWLIST and key != "event" and key != "_from_structlog":
            del event_dict[key]
    return event_dict


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog with strict field allowlist.

    Sets up the structlog processing pipeline:

    1. ``add_log_level`` — adds ``level`` key.
    2. ``merge_contextvars`` — merges context vars into event dict.
    3. ``PositionalArgumentsFormatter`` — formats positional args.
    4. ``TimeStamper(fmt="iso")`` — adds ISO-8601 timestamp.
    5. ``allowlist_processor`` — removes non-allowlisted fields.
    6. ``ProcessorFormatter.wrap_for_formatter`` — wraps for stdlib.

    Finally, configures a ``logging.StreamHandler(sys.stderr)`` with the
    ``ProcessorFormatter`` using ``structlog.processors.JSONRenderer()``
    as the final renderer. The root logger's level is set to the provided
    ``level`` argument.

    Args:
        level: The minimum logging level (e.g., ``"INFO"``, ``"WARNING"``).
    """
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            allowlist_processor,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure the stdlib logging handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
        )
    )

    # Attach handler to root logger and set level
    root_logger = logging.getLogger()
    # Remove any existing handlers to avoid duplicate output
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())


def get_logger(component: str | None = None) -> BoundLogger:
    """Get a structlog logger, optionally bound to a component name.

    Args:
        component: Optional component name to bind (e.g., ``"startup_checks"``).

    Returns:
        A structlog ``BoundLogger`` instance.
    """
    log = structlog.get_logger()
    if component:
        log = log.bind(component=component)
    return log
