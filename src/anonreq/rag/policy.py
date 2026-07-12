"""Retrieval Policy Engine — policy evaluation for RAG chunk access.

Provides:
- ChunkContext: metadata about a retrieved chunk
- UserContext: user identity and permissions
- RetrievalPolicyEngine: evaluates 4 rules against chunk+user context
- PolicyRuleResult: per-rule evaluation outcome
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

_CLASSIFICATION_ORDER = [
    "Internal",
    "Confidential",
    "Highly Restricted",
]


class ClassificationLevel(StrEnum):
    INTERNAL = "Internal"
    CONFIDENTIAL = "Confidential"
    HIGHLY_RESTRICTED = "Highly Restricted"


def _classification_rank(level: str) -> int:
    try:
        return _CLASSIFICATION_ORDER.index(level)
    except ValueError:
        return 0


@dataclass
class ChunkContext:
    """Metadata about a retrieved chunk for policy evaluation.

    Attributes:
        chunk_id: Unique chunk identifier.
        content: The chunk text content.
        classification_level: Data classification level.
        entity_types_present: Entity types detected in the chunk.
        source_app_id: Source application that created the chunk.
        business_unit: Business unit that owns the data.
        allowed_roles: Roles permitted to access this chunk.
    """

    chunk_id: str
    content: str
    classification_level: str = "Internal"
    entity_types_present: list[str] = field(default_factory=list)
    source_app_id: str = ""
    business_unit: str = ""
    allowed_roles: list[str] = field(default_factory=list)


@dataclass
class UserContext:
    """User identity and permissions for policy evaluation.

    Attributes:
        user_id: Unique user identifier.
        roles: Roles assigned to the user.
        clearance: User's clearance level.
        applications: Applications the user is authorized to use.
        business_unit: User's business unit.
    """

    user_id: str
    roles: list[str]
    applications: list[str]
    clearance: str = "Internal"
    business_unit: str = ""


@dataclass
class PolicyRuleResult:
    """Result of evaluating a single policy rule.

    Attributes:
        rule_id: Identifier for the rule.
        denied: Whether the rule denied access.
        reason: Human-readable reason for the decision.
    """

    rule_id: str
    denied: bool
    reason: str = ""


@dataclass
class PolicyEvaluationResult:
    """Overall result of policy evaluation for a chunk.

    Attributes:
        allowed: Whether the chunk is allowed.
        denied_rules: List of rules that denied access.
    """

    allowed: bool
    denied_rules: list[PolicyRuleResult] = field(default_factory=list)


class RetrievalPolicyEngine:
    """Evaluates retrieval policy rules against chunk and user context.

    Rules evaluated:
        - RULE-001 (classification_clearance): deny if chunk > user clearance
        - RULE-002 (entity_type_restriction): deny if user roles exclude chunk entity types
        - RULE-003 (cross_app_isolation): deny if chunk app not in user apps
        - RULE-004 (business_unit_isolation): deny cross-BU for >= Confidential

    Args:
        config: Optional dict with enabled_rules list.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        all_rules = [
            "classification_clearance",
            "entity_type_restriction",
            "cross_app_isolation",
            "business_unit_isolation",
        ]
        self._enabled_rules = config.get("enabled_rules", all_rules)

    def evaluate(
        self,
        chunk: ChunkContext,
        user: UserContext,
    ) -> PolicyEvaluationResult:
        """Evaluate all enabled rules against a chunk+user pair.

        Args:
            chunk: The retrieved chunk context.
            user: The requesting user context.

        Returns:
            PolicyEvaluationResult with allow/deny decision.
        """
        denied: list[PolicyRuleResult] = []

        for rule_id in self._enabled_rules:
            if rule_id == "classification_clearance":
                result = self._rule_classification_clearance(chunk, user)
            elif rule_id == "entity_type_restriction":
                result = self._rule_entity_type_restriction(chunk, user)
            elif rule_id == "cross_app_isolation":
                result = self._rule_cross_app_isolation(chunk, user)
            elif rule_id == "business_unit_isolation":
                result = self._rule_business_unit_isolation(chunk, user)
            else:
                continue

            if result.denied:
                denied.append(result)

        return PolicyEvaluationResult(
            allowed=len(denied) == 0,
            denied_rules=denied,
        )

    def filter_chunks(
        self,
        chunks: list[ChunkContext],
        user: UserContext,
    ) -> tuple[list[ChunkContext], list[ChunkContext]]:
        """Filter chunks into allowed and denied lists.

        Args:
            chunks: List of chunk contexts to evaluate.
            user: The requesting user context.

        Returns:
            Tuple of (allowed_chunks, denied_chunks).
        """
        allowed: list[ChunkContext] = []
        denied: list[ChunkContext] = []

        for chunk in chunks:
            result = self.evaluate(chunk, user)
            if result.allowed:
                allowed.append(chunk)
            else:
                denied.append(chunk)

        return allowed, denied

    def _rule_classification_clearance(
        self,
        chunk: ChunkContext,
        user: UserContext,
    ) -> PolicyRuleResult:
        """RULE-001: Deny if chunk classification > user clearance."""
        chunk_rank = _classification_rank(chunk.classification_level)
        user_rank = _classification_rank(user.clearance)
        if chunk_rank > user_rank:
            return PolicyRuleResult(
                rule_id="classification_clearance",
                denied=True,
                reason=(
                    f"Chunk classification '{chunk.classification_level}' "
                    f"exceeds user clearance '{user.clearance}'"
                ),
            )
        return PolicyRuleResult(rule_id="classification_clearance", denied=False)

    def _rule_entity_type_restriction(
        self,
        chunk: ChunkContext,
        user: UserContext,
    ) -> PolicyRuleResult:
        """RULE-002: Deny if user roles exclude chunk entity types."""
        if not chunk.allowed_roles:
            return PolicyRuleResult(rule_id="entity_type_restriction", denied=False)
        if not any(role in user.roles for role in chunk.allowed_roles):
            return PolicyRuleResult(
                rule_id="entity_type_restriction",
                denied=True,
                reason=(
                    f"User roles {user.roles} not in "
                    f"allowed roles {chunk.allowed_roles}"
                ),
            )
        return PolicyRuleResult(rule_id="entity_type_restriction", denied=False)

    def _rule_cross_app_isolation(
        self,
        chunk: ChunkContext,
        user: UserContext,
    ) -> PolicyRuleResult:
        """RULE-003: Deny if chunk source_app not in user's applications."""
        if not chunk.source_app_id:
            return PolicyRuleResult(rule_id="cross_app_isolation", denied=False)
        if chunk.source_app_id not in user.applications:
            return PolicyRuleResult(
                rule_id="cross_app_isolation",
                denied=True,
                reason=(
                    f"Chunk source app '{chunk.source_app_id}' "
                    f"not in user applications {user.applications}"
                ),
            )
        return PolicyRuleResult(rule_id="cross_app_isolation", denied=False)

    def _rule_business_unit_isolation(
        self,
        chunk: ChunkContext,
        user: UserContext,
    ) -> PolicyRuleResult:
        """RULE-004: Deny cross-BU access for >= Confidential chunks."""
        if not chunk.business_unit or not user.business_unit:
            return PolicyRuleResult(rule_id="business_unit_isolation", denied=False)
        if chunk.business_unit == user.business_unit:
            return PolicyRuleResult(rule_id="business_unit_isolation", denied=False)
        chunk_rank = _classification_rank(chunk.classification_level)
        confidential_rank = _classification_rank("Confidential")
        if chunk_rank >= confidential_rank:
            return PolicyRuleResult(
                rule_id="business_unit_isolation",
                denied=True,
                reason=(
                    f"Cross-BU access denied: chunk BU '{chunk.business_unit}' "
                    f"!= user BU '{user.business_unit}' for "
                    f"classification '{chunk.classification_level}'"
                ),
            )
        return PolicyRuleResult(rule_id="business_unit_isolation", denied=False)
