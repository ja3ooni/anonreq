"""Classification engine data models.

Per D-22 through D-28:
- ClassificationRule defines a single YAML-based rule with conditions
- ClassResult captures the outcome of classification
- ClassificationAction is a Literal type for the 4-tier action system

Action precedence per D-24: BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS.

Phase 12 additions (CLASS-01, CLASS-02):
- ClassificationLevel: 5-level IntEnum (Public→Highly Restricted)
- ClassificationResult: deterministic max classification outcome
- ENTITY_CLASSIFICATION_MAP: default entity-type-to-level mapping
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Literal

ClassificationAction = Literal["BLOCK", "ROUTE_LOCAL", "ANONYMIZE", "PASS"]
"""The four classification actions (D-24).

- ``BLOCK``: Return HTTP 403, do not forward.
- ``ROUTE_LOCAL``: Forward to configured on-prem endpoint.
- ``ANONYMIZE``: Run full detection + tokenization pipeline.
- ``PASS``: Forward request unchanged.
"""


# ---------------------------------------------------------------------------
# Phase 12: Deterministic Classification (CLASS-01, CLASS-02)
# ---------------------------------------------------------------------------


class ClassificationLevel(IntEnum):
    """Five fixed sensitivity levels (CLASS-01).

    Ordinal values enable deterministic max comparison:
    ``max([INTERNAL, CONFIDENTIAL]) == CONFIDENTIAL``
    """

    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3
    HIGHLY_RESTRICTED = 4


@dataclass
class ClassificationResult:
    """Outcome of deterministic max classification (CLASS-01).

    Attributes:
        highest: The highest sensitivity level detected.
        labels: All detected entity type labels preserved in order.
        detected_levels: Classification level per entity type.
        client_override: Whether client-asserted level increased the result.
        client_asserted_level: The client-asserted level (if applied).
    """

    highest: ClassificationLevel
    labels: list[str]
    detected_levels: list[ClassificationLevel]
    client_override: bool = False
    client_asserted_level: ClassificationLevel | None = None


ENTITY_CLASSIFICATION_MAP: dict[str, ClassificationLevel] = {
    # Internal (Level 1)
    "PERSON": ClassificationLevel.INTERNAL,
    "LOCATION": ClassificationLevel.INTERNAL,
    "DATE_TIME": ClassificationLevel.INTERNAL,
    "NRP": ClassificationLevel.INTERNAL,
    "AGE": ClassificationLevel.INTERNAL,
    "DOMAIN_NAME": ClassificationLevel.INTERNAL,
    "ORGANIZATION": ClassificationLevel.INTERNAL,
    "ZIP_CODE": ClassificationLevel.INTERNAL,
    "IP_ADDRESS": ClassificationLevel.INTERNAL,
    # Confidential (Level 2)
    "EMAIL": ClassificationLevel.CONFIDENTIAL,
    "PHONE": ClassificationLevel.CONFIDENTIAL,
    "URL": ClassificationLevel.CONFIDENTIAL,
    "CRYPTO": ClassificationLevel.CONFIDENTIAL,
    # Restricted (Level 3)
    "CREDIT_CARD": ClassificationLevel.RESTRICTED,
    "CREDIT_CARD_TYPE": ClassificationLevel.RESTRICTED,
    "IBAN": ClassificationLevel.RESTRICTED,
    "SWIFT": ClassificationLevel.RESTRICTED,
    "BANK_ACCOUNT": ClassificationLevel.RESTRICTED,
    "SSN": ClassificationLevel.RESTRICTED,
    "MEDICAL_LICENSE": ClassificationLevel.RESTRICTED,
    "DRIVERS_LICENSE": ClassificationLevel.RESTRICTED,
    "PASSPORT": ClassificationLevel.RESTRICTED,
    "TAX_ID": ClassificationLevel.RESTRICTED,
    "HEALTH_INFO": ClassificationLevel.RESTRICTED,
    # Highly Restricted (Level 4)
    "API_KEY": ClassificationLevel.HIGHLY_RESTRICTED,
    "PASSWORD": ClassificationLevel.HIGHLY_RESTRICTED,
    "AUTH_TOKEN": ClassificationLevel.HIGHLY_RESTRICTED,
    "SOURCE_CODE": ClassificationLevel.HIGHLY_RESTRICTED,
}
"""Default entity-type-to-classification mapping (CLASS-02).

Covers all Phase 2 entity types. Overridable per tenant via Phase 8
policy YAML. Unknown entity types default to INTERNAL.
"""


# ---------------------------------------------------------------------------
# Phase 6: YAML-Based Classification Rules (D-22 through D-28)
# ---------------------------------------------------------------------------


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
