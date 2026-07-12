"""Classification engine package.

Per D-22 through D-28:
- YAML DSL with stable rule IDs, enabled, version, conditions
- Action-based precedence: BLOCK > ROUTE_LOCAL > ANONYMIZE > PASS
- Default action for unmatched requests: PASS
"""

from anonreq.classification.engine import ClassificationEngine, ClassificationRule
from anonreq.classification.loader import ClassificationRuleLoader

__all__ = [
    "ClassificationEngine",
    "ClassificationRule",
    "ClassificationRuleLoader",
]
