from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DetectionCategory(StrEnum):
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    SYSTEM_PROMPT_EXTRACTION = "system_prompt_extraction"
    INSTRUCTION_OVERRIDE = "instruction_override"
    ROLE_ESCALATION = "role_escalation"
    HIDDEN_TOOL_INVOCATION = "hidden_tool_invocation"
    SECRET_EXFILTRATION = "secret_exfiltration"


class SeverityLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FirewallAction(StrEnum):
    BLOCK = "BLOCK"
    FLAG_AND_FORWARD = "FLAG_AND_FORWARD"
    MONITOR = "MONITOR"


class FirewallRule(BaseModel):
    model_config = {"extra": "forbid"}

    rule_id: str
    category: DetectionCategory
    enabled: bool = True
    pattern: str | None = None
    description: str | None = None
    semantic_description: str | None = None
    action: FirewallAction = FirewallAction.BLOCK
    severity: SeverityLevel = SeverityLevel.HIGH
    priority: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class DetectionResult(BaseModel):
    model_config = {"extra": "forbid"}

    category: DetectionCategory
    confidence: float = Field(ge=0.0, le=1.0)
    rule_id: str | None = None
    severity: SeverityLevel
    action: FirewallAction
    matched_text_snippet: str | None = None


class RuleCategoryConfig(BaseModel):
    model_config = {"extra": "forbid"}

    enabled: bool = True
    threshold: float = Field(default=0.85, ge=0.0, le=1.0)


class SeverityActionMapping(BaseModel):
    model_config = {"extra": "forbid"}

    high: FirewallAction = FirewallAction.BLOCK
    medium: FirewallAction = FirewallAction.FLAG_AND_FORWARD
    low: FirewallAction = FirewallAction.MONITOR
