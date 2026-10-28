"""Structured audit logging configuration with strict field allowlist.

Provides:
- ``setup_logging()``: Configures structlog with processors including the
  custom allowlist processor that drops non-allowlisted fields.
- ``ALLOWLIST``: The set of allowed log field names.
- ``allowlist_processor``: The structlog processor that enforces the allowlist.
- ``scrub_log_value()``: Recursive PII and exception-message scrubber.
- ``get_logger()``: Convenience function for creating a bound logger.

Per D-04, D-05, D-06, AUDT-01, AUDT-02, AUDT-03:
- Structured JSON logs to stdout with timestamp, level, event.
- Strict field allowlist — non-allowlisted fields dropped before serialization.
- Nested values under allowlisted keys (``error``, ``data``, ``extra``, lists)
  are scrubbed with the project regex recognizers before serialization.
- Exception objects and ``exc_info`` are reduced to the exception type plus
  the file, line, and function of the raise site. Messages and args are
  never emitted.
- request_id propagated via structlog contextvars for trace correlation.
- Log level configurable by settings.LOG_LEVEL.

Threat model coverage:
- T-01-03-02 (Information Disclosure): Field allowlist drops unknown keys.
  Remaining values are scanned recursively. Presidio NER is not called from
  the logging path: it needs the analyzer service and must not block or
  fail open while a log record is being formatted. Regex detection, including
  Luhn checks for card numbers, is the practical detector.

Free-text person names and street addresses are not caught. The scrubber
only applies deterministic regex recognizers and checksum validators. A
value such as "Jane Doe" or "10 Downing Street" is left unchanged unless it
also matches a structured pattern (email, phone, national identifier, and
similar). Regex scans are capped at ``LOG_SCRUB_MAX_CHARS``; the remainder
is replaced with ``[TRUNCATED]`` so a long field cannot drive ReDoS.
"""

import logging
import re
import sys
import types
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import structlog
from structlog.stdlib import BoundLogger, ProcessorFormatter

from anonreq.detection.regex_detector import RegexDetector

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
    "error_file",
    "error_line",
    "error_function",
    "version",
    "session_id",
    "provider",
    "model",
    "entity_counts",
    "latency_ms",
    "compliance_preset",
    "locale",
    "presidio_language",
    "actor_id",
    "decision_id",
    "action",
    "matched_rule_ids",
    "limit_type",
    "current_value",
    "limit",
    "budget_type",
    "current_spend",
    "budget_limit",
    "currency",
    "region",
    "allowed_regions",
    "classification_level",
    "matched_rule_id",
    "reset_at",
    "stage",
    "error",
    # Fields used across pipeline, proxy, locale, and middleware modules
    "path",
    "route",
    "method",
    "tenant_id",
    "content_type",
    "elapsed_ms",
    "count",
    "attempt",
    "bucket",
    "extra",
    "file_name",
    "max_locales",
    "part_name",
    "data",
    "ttl",
})

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bsk-[A-Za-z0-9]{8,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]{8,}\b"),
)
_KEY_VALUE_PATTERN = re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*([^\s,'\"]+)")
_SENSITIVE_KEY = re.compile(
    r"^(email|email_address|e_mail|phone|phone_number|telephone|ssn|"
    r"social_security_number|credit_card|card_number|iban|password|passwd|"
    r"secret|api_key|authorization|credential|access_token|private_key)$"
)
_REDACTED = "[REDACTED]"
_TRUNCATED = "[TRUNCATED]"
# Bound regex work in the logging path. Detection of request bodies is unchanged.
LOG_SCRUB_MAX_CHARS = 4096
_MAX_DEPTH = 12
_UVICORN_LOGGERS = ("uvicorn.access", "uvicorn.error")
_PII_DETECTOR = RegexDetector()
_GERMAN_ENTITY_TYPES = (
    "TAX_ID_DE",
    "PERSONAL_AUSWEIS",
    "KVNR",
    "SVNR_DE",
    "IBAN_DE",
)
_CHECKSUM_ENTITY_TYPES = {
    "IBAN_CODE": "IBAN_DE",
    "IBAN_DE": "IBAN_DE",
    "TAX_ID_DE": "TAX_ID_DE",
    "PERSONAL_AUSWEIS": "PERSONAL_AUSWEIS",
    "KVNR": "KVNR",
}
_german_patterns: dict[str, re.Pattern[str]] | None = None
_checksums: Any = None

# The stock PHONE_NUMBER pattern also matches timestamp fractions and UUID
# segments. Keep those spans only when they look like a formatted phone number.
_PHONE_SEPARATOR = re.compile(r"[+().\-\s]")

_STANDARD_LOG_ATTRS = frozenset(logging.makeLogRecord({}).__dict__) | frozenset({
    "message",
    "asctime",
    "taskName",
})


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def _plausible_phone(text: str, start: int, end: int) -> bool:
    """Reject phone hits that are slices of timestamps, UUIDs, or digit runs."""
    span = text[start:end]
    if sum(character.isdigit() for character in span) < 10:
        return False
    if _PHONE_SEPARATOR.search(span) is None:
        return False
    if start > 0 and text[start - 1] in ":-_./":
        return False
    return not (end < len(text) and text[end] in "-_")


def _german_locale_file() -> Path:
    bundled = Path(__file__).resolve().parents[2] / "config" / "locales" / "de-DE.yaml"
    if bundled.is_file():
        return bundled
    return Path("config/locales/de-DE.yaml")


def _load_german_recognizers() -> tuple[dict[str, re.Pattern[str]], Any]:
    """Load de-DE regexes and the gateway's checksum validators.

    Patterns come from ``config/locales/de-DE.yaml`` via ``LocaleBundle``.
    Validators are the same classes the locale registry registers. SVNR has
    no checksum in that bundle, so its regex match is kept as-is.
    """
    import yaml

    from anonreq.locale.bundle import LocaleBundle
    from anonreq.locale.checksum import ChecksumValidatorRegistry
    from anonreq.locale.checksums.germany import (
        IBANMod97Validator,
        KVNRValidator,
        PersonalausweisValidator,
    )
    from anonreq.locale.checksums.iso7064 import ISO7064Mod11_2Validator

    registry = ChecksumValidatorRegistry()
    registry.register("TAX_ID_DE", ISO7064Mod11_2Validator())
    registry.register("PERSONAL_AUSWEIS", PersonalausweisValidator())
    registry.register("KVNR", KVNRValidator())
    registry.register("IBAN_DE", IBANMod97Validator())

    try:
        path = _german_locale_file()
        if not path.is_file():
            return {}, registry
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        bundle = LocaleBundle.from_dict(raw)
        configs = [item for item in bundle.entity_types if item.name in _GERMAN_ENTITY_TYPES]
        return RegexDetector.patterns_from_entity_configs(configs), registry
    except Exception as exc:
        logging.getLogger("anonreq.logging_config").warning(
            "german recognizers unavailable type=%s",
            type(exc).__name__,
        )
        return {}, registry


def _german_pattern_map() -> dict[str, re.Pattern[str]]:
    global _german_patterns, _checksums
    if _german_patterns is None or _checksums is None:
        _german_patterns, _checksums = _load_german_recognizers()
    return _german_patterns


def _checksum_registry() -> Any:
    _german_pattern_map()
    return _checksums


def _checksum_accepts(entity_type: str, value: str) -> bool:
    validator_id = _CHECKSUM_ENTITY_TYPES.get(entity_type)
    if validator_id is None:
        return True
    validator = _checksum_registry().get(validator_id)
    if validator is None:
        return True
    return bool(validator.validate(value))


def _redact_text(value: str) -> str:
    truncated = len(value) > LOG_SCRUB_MAX_CHARS
    if truncated:
        value = value[:LOG_SCRUB_MAX_CHARS]
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(_REDACTED, redacted)
    redacted = _KEY_VALUE_PATTERN.sub(lambda match: f"{match.group(1)}={_REDACTED}", redacted)

    spans: list[tuple[int, int]] = []
    detections = _PII_DETECTOR.detect(redacted, extra_patterns=_german_pattern_map())
    for detection in detections:
        start = int(detection["start"])
        end = int(detection["end"])
        entity_type = str(detection["entity_type"])
        if entity_type == "PHONE_NUMBER" and not _plausible_phone(redacted, start, end):
            continue
        if not _checksum_accepts(entity_type, redacted[start:end]):
            continue
        spans.append((start, end))
    if not spans:
        if truncated:
            return f"{redacted}{_TRUNCATED}"
        return redacted

    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    parts: list[str] = []
    cursor = 0
    for start, end in merged:
        parts.append(redacted[cursor:start])
        parts.append(_REDACTED)
        cursor = end
    parts.append(redacted[cursor:])
    redacted = "".join(parts)
    if truncated:
        return f"{redacted}{_TRUNCATED}"
    return redacted


def _is_exc_info(value: tuple[Any, ...]) -> bool:
    if len(value) != 3:
        return False
    exc_type, exc, _traceback = value
    type_ok = exc_type is None or (
        isinstance(exc_type, type) and issubclass(exc_type, BaseException)
    )
    exc_ok = exc is None or isinstance(exc, BaseException)
    return type_ok and exc_ok


def _raise_location(value: Any) -> dict[str, Any]:
    """File, line, and function of the innermost raise, without the message."""
    tb: types.TracebackType | None = None
    if value is True:
        tb = sys.exc_info()[2]
    elif isinstance(value, BaseException):
        tb = value.__traceback__
    elif isinstance(value, tuple) and _is_exc_info(value):
        candidate = value[2]
        if isinstance(candidate, types.TracebackType):
            tb = candidate
        elif isinstance(value[1], BaseException):
            tb = value[1].__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    if tb is None:
        return {}
    code = tb.tb_frame.f_code
    return {
        "error_file": code.co_filename,
        "error_line": tb.tb_lineno,
        "error_function": code.co_name,
    }


def _exception_type_from(value: Any) -> str | None:
    """Return an exception type name, never its message or args."""
    if value is True:
        current = sys.exc_info()[1]
        return type(current).__name__ if isinstance(current, BaseException) else None
    if isinstance(value, BaseException):
        return type(value).__name__
    if isinstance(value, tuple) and _is_exc_info(value):
        exc_type, exc, _traceback = value
        if isinstance(exc, BaseException):
            return type(exc).__name__
        if isinstance(exc_type, type):
            return exc_type.__name__
    return None


def scrub_log_value(value: Any, *, _depth: int = 0, _seen: set[int] | None = None) -> Any:
    """Recursively remove PII and exception messages from a log value.

    Dicts, lists, tuples, sets, extra mappings, dataclass and Pydantic values
    are walked. Exception instances and ``exc_info`` tuples become the
    exception type name. Strings are scanned with the secret patterns and
    ``RegexDetector`` (Luhn-validated card numbers included).

    Free-text names and addresses are not recognized. Strings longer than
    ``LOG_SCRUB_MAX_CHARS`` are scanned only up to that limit and then marked
    ``[TRUNCATED]``.
    """
    if _depth > _MAX_DEPTH:
        return _REDACTED
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, BaseException):
        return type(value).__name__
    if isinstance(value, types.TracebackType):
        return _REDACTED
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, bytes | bytearray):
        return _redact_text(bytes(value).decode("utf-8", errors="replace"))
    if isinstance(value, tuple) and _is_exc_info(value):
        return _exception_type_from(value)

    seen = _seen if _seen is not None else set()
    if isinstance(value, (Mapping, list, tuple, set)):
        identity = id(value)
        if identity in seen:
            return _REDACTED
        seen.add(identity)

    if isinstance(value, Mapping):
        scrubbed: dict[Any, Any] = {}
        for key, inner in value.items():
            if isinstance(key, str):
                redacted_key = _redact_text(key)
                if _SENSITIVE_KEY.match(_normalize_key(key)):
                    scrubbed[redacted_key] = _REDACTED
                    continue
            else:
                redacted_key = key
            scrubbed[redacted_key] = scrub_log_value(inner, _depth=_depth + 1, _seen=seen)
        return scrubbed
    if isinstance(value, list):
        return [scrub_log_value(item, _depth=_depth + 1, _seen=seen) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_log_value(item, _depth=_depth + 1, _seen=seen) for item in value)
    if isinstance(value, set):
        return {scrub_log_value(item, _depth=_depth + 1, _seen=seen) for item in value}
    if hasattr(value, "model_dump"):
        return scrub_log_value(value.model_dump(), _depth=_depth + 1, _seen=seen)
    if hasattr(value, "__dataclass_fields__"):
        dumped = {key: getattr(value, key) for key in value.__dataclass_fields__}
        return scrub_log_value(dumped, _depth=_depth + 1, _seen=seen)
    return value


def _replace_exceptions(value: Any) -> Any:
    """Replace exception objects before log messages are interpolated."""
    if isinstance(value, BaseException):
        return type(value).__name__
    if isinstance(value, types.TracebackType):
        return _REDACTED
    if isinstance(value, tuple):
        if _is_exc_info(value):
            return _exception_type_from(value)
        return tuple(_replace_exceptions(item) for item in value)
    if isinstance(value, list):
        return [_replace_exceptions(item) for item in value]
    if isinstance(value, Mapping):
        return {key: _replace_exceptions(inner) for key, inner in value.items()}
    return value


def strip_exception_details_processor(
    _logger: structlog.stdlib.BoundLogger,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Drop exception messages and args before they are formatted.

    The raise site's file, line, and function are kept. The message is not.
    """
    if "exc_info" in event_dict:
        raw_exc = event_dict.pop("exc_info")
        name = _exception_type_from(raw_exc)
        if name and not event_dict.get("error_type"):
            event_dict["error_type"] = name
        for key, loc in _raise_location(raw_exc).items():
            event_dict.setdefault(key, loc)
    event_dict.pop("stack_info", None)
    if "positional_args" in event_dict:
        event_dict["positional_args"] = _replace_exceptions(event_dict["positional_args"])
    for key, value in list(event_dict.items()):
        if key in {"positional_args", "event"}:
            continue
        event_dict[key] = _replace_exceptions(value)
    return event_dict


def redact_sensitive_values_processor(
    _logger: structlog.stdlib.BoundLogger,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Scrub PII and secrets from every remaining log value."""
    for key, value in list(event_dict.items()):
        event_dict[key] = scrub_log_value(value)
    return event_dict


def redact_secret_substrings_processor(
    logger: structlog.stdlib.BoundLogger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Backward-compatible name for :func:`redact_sensitive_values_processor`."""
    return redact_sensitive_values_processor(logger, method_name, event_dict)


class PiiRedactingFilter(logging.Filter):
    """Scrub stdlib log records before they are formatted.

    Covers the message, positional and mapping args, ``extra`` attributes,
    and exception info. Exception messages are replaced with the type name.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            name = _exception_type_from(record.exc_info)
            if name and not getattr(record, "error_type", None):
                record.error_type = name
            for key, loc in _raise_location(record.exc_info).items():
                if not getattr(record, key, None):
                    setattr(record, key, loc)
            record.exc_info = None
            record.exc_text = None
        if isinstance(record.stack_info, str):
            record.stack_info = _redact_text(record.stack_info)

        record.msg = scrub_log_value(_replace_exceptions(record.msg))
        if isinstance(record.args, Mapping):
            record.args = scrub_log_value(_replace_exceptions(dict(record.args)))
        elif isinstance(record.args, tuple):
            record.args = tuple(scrub_log_value(_replace_exceptions(arg)) for arg in record.args)

        for key, value in list(record.__dict__.items()):
            if key in _STANDARD_LOG_ATTRS or key in {"msg", "args", "exc_info", "exc_text"}:
                continue
            setattr(record, key, scrub_log_value(_replace_exceptions(value)))
        return True


def allowlist_processor(
    _logger: structlog.stdlib.BoundLogger,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor that drops non-allowlisted fields.

    Iterates over top-level keys in the event dict and deletes any key
    not in ``ALLOWLIST``. This prevents accidental logging of sensitive
    data (PII, credentials, internal paths) by rejecting unknown keys.

    Only top-level keys are compared to ``ALLOWLIST``. Nested mappings and
    lists stored under an allowlisted key such as ``error``, ``data``, or
    ``extra`` are kept, then scrubbed by
    :func:`redact_sensitive_values_processor`.

    Args:
        logger: The structlog logger instance.
        method_name: The logging method (``info``, ``error``, etc.).
        event_dict: The structured log event dict.

    Returns:
        The filtered event dict with non-allowlisted keys removed.
    """
    # ``_record`` is added by ProcessorFormatter and must survive until
    # ``remove_processors_meta`` runs. Deleting it here breaks foreign logs.
    preserved = {"event", "_from_structlog", "_record"}
    for key in list(event_dict.keys()):
        if key not in ALLOWLIST and key not in preserved:
            del event_dict[key]
    return event_dict


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog with strict field allowlist.

    Sets up the structlog processing pipeline:

    1. ``add_log_level`` — adds ``level`` key.
    2. ``merge_contextvars`` — merges context vars into event dict.
    3. ``PositionalArgumentsFormatter`` — formats positional args.
    4. ``TimeStamper(fmt="iso")`` — adds ISO-8601 timestamp.
    5. ``strip_exception_details_processor`` — drops exception messages.
    6. ``allowlist_processor`` — removes non-allowlisted fields.
    7. ``redact_sensitive_values_processor`` — scrubs nested PII and secrets.
    8. ``ProcessorFormatter.wrap_for_formatter`` — wraps for stdlib.

    Finally, configures a ``logging.StreamHandler(sys.stderr)`` with the
    ``ProcessorFormatter`` using ``structlog.processors.JSONRenderer()``
    as the final renderer. The root logger's level is set to the provided
    ``level`` argument.

    Args:
        level: The minimum logging level (e.g., ``"INFO"``, ``"WARNING"``).
    """
    # Our processors take BoundLogger/dict; structlog's Processor alias uses
    # Any/MutableMapping. They are compatible at runtime, so cast explicitly.
    foreign_pre_chain: list[structlog.typing.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ExtraAdder(),
        cast(structlog.typing.Processor, strip_exception_details_processor),
        cast(structlog.typing.Processor, allowlist_processor),
        cast(structlog.typing.Processor, redact_sensitive_values_processor),
    ]
    structlog.configure(
        processors=[
            strip_exception_details_processor,  # type: ignore[list-item]
            structlog.stdlib.add_log_level,
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            allowlist_processor,  # type: ignore[list-item]
            redact_sensitive_values_processor,  # type: ignore[list-item]
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure the stdlib logging handler
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(PiiRedactingFilter())
    handler.setFormatter(
        ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=foreign_pre_chain,
        )
    )

    # Attach handler to root logger and set level
    root_logger = logging.getLogger()
    # Remove any existing handlers to avoid duplicate output
    root_logger.handlers.clear()
    root_logger.filters = [
        existing
        for existing in root_logger.filters
        if not isinstance(existing, PiiRedactingFilter)
    ]
    root_logger.addFilter(PiiRedactingFilter())
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())
    _attach_uvicorn_redaction()


def _attach_filter(target: logging.Logger | logging.Handler) -> None:
    if any(isinstance(existing, PiiRedactingFilter) for existing in target.filters):
        return
    target.addFilter(PiiRedactingFilter())


def _attach_uvicorn_redaction() -> None:
    """Scrub uvicorn's own access and error handlers.

    Those loggers do not propagate to the root handler, so the root filter
    never sees their records. Filters are attached to the loggers and to
    every current handler, and ``addHandler`` is wrapped so a handler uvicorn
    installs later is covered too.
    """
    for name in _UVICORN_LOGGERS:
        target = logging.getLogger(name)
        _attach_filter(target)
        for handler in list(target.handlers):
            _attach_filter(handler)
        if getattr(target, "_anonreq_pii_add_handler", False):
            continue
        original = target.addHandler

        def _adding(handler: logging.Handler, _original: Any = original) -> None:
            _attach_filter(handler)
            _original(handler)

        target.addHandler = _adding  # type: ignore[method-assign,assignment]
        target._anonreq_pii_add_handler = True  # type: ignore[attr-defined]


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
    return cast(BoundLogger, log)
