from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ToolPolicy = Literal["allow", "allow_with_audit", "require_approval", "block"]


class ToolGovernanceConfig(BaseModel):
    model_config = {"extra": "forbid"}

    per_tool_policies: dict[str, ToolPolicy] = Field(default_factory=dict)
    schema_registry: dict[str, dict[str, Any]] = Field(default_factory=dict)
    default_tool_policy: ToolPolicy = "allow_with_audit"
    block_unknown_tools: bool = True
    arg_injection_scan_enabled: bool = True
    result_detection_enabled: bool = True
    error_redaction_enabled: bool = True
