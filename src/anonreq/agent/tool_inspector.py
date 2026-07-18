from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from anonreq.agent.config import ToolGovernanceConfig
from anonreq.agent.mcp_parser import MCPParser
from anonreq.agent.metrics import agent_governance_duration_ms, agent_tool_calls_inspected_total
from anonreq.agent.schema import InspectionResult, ToolCall

INJECTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bignore\s+(all\s+)?previous\s+instructions\b", re.I), "prompt_injection"),
    (re.compile(r"\bdrop\s+table\b|\bunion\s+select\b|;\s*shutdown\b", re.I), "sql_injection"),
    (re.compile(r"\brm\s+-rf\b|\bcurl\b.*\|\s*(sh|bash)\b", re.I), "command_injection"),
    (re.compile(r"\bos\.system\b|\bsubprocess\.", re.I), "code_execution"),
    (re.compile(r"<script\b|javascript:", re.I), "script_injection"),
)


class ToolCallInspector:
    def __init__(
        self,
        firewall: Any,
        schema_registry: dict[str, dict[str, Any]],
        config: ToolGovernanceConfig,
    ) -> None:
        self._firewall = firewall
        self._config = config
        self._schema_registry = {**config.schema_registry, **schema_registry}
        self._mcp_parser = MCPParser()
        self.tenant_id = "default"

    async def inspect_call(self, tool_call: ToolCall) -> InspectionResult:
        policy = self._config.per_tool_policies.get(tool_call.tool_name)
        if policy is None and self._config.block_unknown_tools:
            return self._record(InspectionResult(
                action="block",
                reason="unknown tool blocked by governance policy",
                confidence=1.0,
                mitre_atlas_id="AML-T0018",
                audit_event_type="agent_tool_call_injected",
                metadata={"policy": "unknown_tool_block"},
            ))

        effective_policy = policy or self._config.default_tool_policy
        if effective_policy == "block":
            return self._record(InspectionResult(
                action="block",
                reason="tool blocked by governance policy",
                confidence=1.0,
                mitre_atlas_id="AML-T0018",
                audit_event_type="agent_tool_call_injected",
                metadata={"policy": "block"},
            ))
        if effective_policy == "require_approval":
            return self._record(InspectionResult(
                action="block",
                reason="tool requires human approval before execution",
                confidence=1.0,
                mitre_atlas_id="AML-T0018",
                audit_event_type="agent_tool_call_injected",
                metadata={"policy": "require_approval"},
            ))

        schema = self._schema_registry.get(tool_call.tool_name)
        if schema is not None:
            errors = self._validate_schema(tool_call.arguments, schema)
            if errors:
                return self._record(InspectionResult(
                    action="block",
                    reason=f"schema validation failed: {'; '.join(errors)}",
                    confidence=1.0,
                    mitre_atlas_id="AML-T0018",
                    audit_event_type="agent_tool_call_injected",
                    metadata={"violation_count": len(errors)},
                ))

        threats = []
        if self._config.arg_injection_scan_enabled:
            threats = await self.scan_arguments(tool_call.arguments)
        if threats:
            max_confidence = max(float(t.get("confidence", 0.9)) for t in threats)
            return self._record(InspectionResult(
                action="block",
                reason="injection detected in tool arguments",
                confidence=max_confidence,
                mitre_atlas_id="AML-T0018",
                audit_event_type="agent_tool_call_injected",
                metadata={"threat_count": len(threats), "categories": sorted({t["category"] for t in threats})},  # noqa: E501
            ))

        return self._record(InspectionResult(
            action="allow",
            reason="tool call allowed",
            confidence=0.0,
            audit_event_type="agent_tool_call_allowed" if effective_policy == "allow_with_audit" else None,  # noqa: E501
            metadata={"policy": effective_policy},
        ))

    async def scan_arguments(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        text = json.dumps(arguments, sort_keys=True, default=str)
        threats = self._scan_local_patterns(text)

        if self._firewall is not None and hasattr(self._firewall, "evaluate"):
            firewall_results = await self._firewall.evaluate(text)
            threats.extend(self._normalize_firewall_results(firewall_results))

        return threats

    def _validate_schema(self, arguments: dict[str, Any], schema: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if schema.get("type") and schema["type"] != "object":
            errors.append("top-level schema must be object")
            return errors

        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for name in required:
            if name not in arguments:
                errors.append(f"missing required field {name}")

        for name, value in arguments.items():
            prop_schema = properties.get(name)
            if prop_schema is None:
                if schema.get("additionalProperties") is False:
                    errors.append(f"unexpected field {name}")
                continue
            expected_type = prop_schema.get("type")
            if expected_type and not self._matches_json_type(value, expected_type):
                errors.append(f"field {name} expected {expected_type}")

        return errors

    def _matches_json_type(self, value: Any, expected_type: str | Iterable[str]) -> bool:
        expected = {expected_type} if isinstance(expected_type, str) else set(expected_type)
        return any(
            (t == "string" and isinstance(value, str))
            or (t == "integer" and isinstance(value, int) and not isinstance(value, bool))
            or (t == "number" and isinstance(value, (int, float)) and not isinstance(value, bool))
            or (t == "boolean" and isinstance(value, bool))
            or (t == "object" and isinstance(value, dict))
            or (t == "array" and isinstance(value, list))
            or (t == "null" and value is None)
            for t in expected
        )

    def _scan_local_patterns(self, text: str) -> list[dict[str, Any]]:
        threats: list[dict[str, Any]] = []
        for pattern, category in INJECTION_PATTERNS:
            if pattern.search(text):
                threats.append({"category": category, "confidence": 0.95})
        return threats

    def _normalize_firewall_results(self, results: Any) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for result in results or []:
            action = getattr(result, "action", None)
            action_value = getattr(action, "value", str(action))
            category = getattr(result, "category", "prompt_injection")
            category_value = getattr(category, "value", str(category))
            if action_value == "BLOCK":
                normalized.append({
                    "category": category_value,
                    "confidence": float(getattr(result, "confidence", 0.9)),
                })
        return normalized

    def _record(self, result: InspectionResult) -> InspectionResult:
        agent_tool_calls_inspected_total.labels(action=result.action, tenant_id=self.tenant_id).inc()  # noqa: E501
        agent_governance_duration_ms.labels(operation="call_inspect").observe(0)
        return result
