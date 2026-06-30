"""Classification engine data models.

Per D-22 through D-28:
- ClassificationRule defines a single YAML-based rule with conditions
- ClassResult captures the outcome of classification
- ClassificationAction is a Literal type for the 4-tier action system

Action precedence per D-24: BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ClassificationAction = Literal["BLOCK", "ROUTE_LOCAL", "ANONYMIZE", "PASS"]
"""The four classification actions (D-24).

- ``BLOCK``: Return HTTP 403, do not forward.
- ``ROUTE_LOCAL``: Forward to configured on-prem endpoint.
- ``ANONYMIZE``: Run full detection + tokenization pipeline.
- ``PASS``: Forward request unchanged.
"""


@dataclass
class ClassificationRule:
    """A single classification rule loaded from YAML.

    Per D-22, D-23: rules have stable IDs, conditions are ANDed
    (roles + regex + keywords must all match for the rule to fire),
    and there is no expression language (OR/NOT) in MVP (D-26).
    """

    id: str
    enabled: bool = True
    version: int = 1
    name: str = ""
    action: ClassificationAction = "ANONYMIZE"
    metadata: dict = field(default_factory=dict)
    roles: list[str] = field(default_factory=list)
    regex_patterns: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass
class ClassResult:
    """The outcome of evaluating classification rules against text nodes.

    Records which rules matched and their versions for auditability (D-27).
    """

    action: ClassificationAction = "PASS"
    matched_rule_ids: list[str] = field(default_factory=list)
    matched_rule_versions: list[int] = field(default_factory=list)
