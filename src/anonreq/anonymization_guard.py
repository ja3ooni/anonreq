"""Startup guard: refuse to run in a configuration that forwards personal data untouched.

The shipped classification default is ``PASS`` (forward unmatched requests unmodified) and
``ANONREQ_PROXY_MODE=proxy-only`` skips detection. Both are fine for some deployments and
a silent leak for others. Setting ``ANONREQ_REQUIRE_ANONYMIZATION=true`` makes the gateway
refuse to start unless requests are anonymized by default.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from anonreq.exceptions import AnonReqError
from anonreq.proxy.modes import ProxyMode


def effective_default_action(override: str | None, classification_path: str) -> str:
    """The default classification action: the env override, else the YAML ``default_action``."""
    if override:
        return override.strip().upper()
    path = Path(classification_path)
    if not path.exists():
        return "PASS"
    data = yaml.safe_load(path.read_text()) or {}
    return str(data.get("default_action", "PASS")).strip().upper()


def assert_anonymization_required(
    *, required: bool, default_action: str, mode: ProxyMode
) -> None:
    """Raise if anonymization is required but the configuration would not perform it."""
    if not required:
        return
    problems = []
    if default_action != "ANONYMIZE":
        problems.append(
            f"classification default action is {default_action}; set "
            "ANONREQ_CLASSIFICATION_DEFAULT_ACTION=ANONYMIZE"
        )
    if mode == ProxyMode.PROXY_ONLY:
        problems.append("proxy mode is proxy-only (no detection); set ANONREQ_PROXY_MODE=full")
    if problems:
        raise AnonReqError(
            message="ANONREQ_REQUIRE_ANONYMIZATION is set but: " + "; ".join(problems),
            error_type="configuration_error",
            status_code=500,
            code="anonymization_not_enforced",
        )
