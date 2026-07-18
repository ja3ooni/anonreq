from __future__ import annotations

import inspect
import re
import time
from typing import Any

from anonreq.agent.config import ToolGovernanceConfig
from anonreq.agent.metrics import agent_governance_duration_ms, agent_tool_results_sanitized_total
from anonreq.agent.schema import ToolResult
from anonreq.models.detection import DetectionResult
from anonreq.tokenization.tokenizer import Tokenizer

REDACTED_ERROR = "[REDACTED_ERROR]"
STACK_TRACE_RE = re.compile(
    r"Traceback \(most recent call last\):[\s\S]*"
    r"|^\s*File \".*\", line \d+, in .*$"
    r"|^\s*at .*\(.*:\d+\)",
    re.MULTILINE,
)
INTERNAL_IP_RE = re.compile(
    r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3})\b"
)
ENV_VAR_RE = re.compile(r"\$[A-Z_][A-Z0-9_]+|%[A-Z_][A-Z0-9_]+%")
ERROR_PATTERNS = (STACK_TRACE_RE, INTERNAL_IP_RE, ENV_VAR_RE)


class ToolResultSanitizer:
    def __init__(
        self,
        detection_engine: Any,
        tokenization_engine: Any,
        config: ToolGovernanceConfig,
    ) -> None:
        self._detection_engine = detection_engine
        self._tokenizer = tokenization_engine or Tokenizer()
        self._config = config
        self.audit_events: list[str] = []
        self.token_mappings: dict[str, str] = {}
        self.tenant_id = "default"

    async def sanitize_result(self, result: ToolResult) -> ToolResult:
        started = time.perf_counter()
        self.audit_events = []
        self.token_mappings = {}
        if hasattr(self._tokenizer, "initialize_session"):
            self._tokenizer.initialize_session()

        content = await self._traverse_and_sanitize(result.content)
        redacted = "agent_tool_error_redacted" in self.audit_events
        sanitized = ToolResult(
            tool_name=result.tool_name,
            content=content,
            id=result.id,
            type=result.type,
        )
        if self.token_mappings and "agent_tool_result_sanitized" not in self.audit_events:
            self.audit_events.append("agent_tool_result_sanitized")
        if redacted:
            agent_tool_results_sanitized_total.labels(
                entity_type="redacted_error",
                tenant_id=self.tenant_id,
            ).inc()
        for entity_type in self._mapping_entity_types():
            agent_tool_results_sanitized_total.labels(
                entity_type=entity_type,
                tenant_id=self.tenant_id,
            ).inc()
        agent_governance_duration_ms.labels(operation="result_sanitize").observe(
            (time.perf_counter() - started) * 1000.0
        )
        return sanitized

    def _redact_errors(self, value: str) -> str:
        redacted = value
        for pattern in ERROR_PATTERNS:
            redacted = pattern.sub(REDACTED_ERROR, redacted)
        if redacted != value and "agent_tool_error_redacted" not in self.audit_events:
            self.audit_events.append("agent_tool_error_redacted")
        return redacted

    async def _traverse_and_sanitize(self, obj: Any, path: str = "") -> Any:
        if isinstance(obj, dict):
            return {
                key: await self._traverse_and_sanitize(value, f"{path}.{key}" if path else str(key))
                for key, value in obj.items()
            }
        if isinstance(obj, list):
            return [
                await self._traverse_and_sanitize(value, f"{path}[{index}]")
                for index, value in enumerate(obj)
            ]
        if isinstance(obj, str):
            return await self._sanitize_string(obj)
        return obj

    async def _sanitize_string(self, value: str) -> str:
        sanitized = self._redact_errors(value) if self._config.error_redaction_enabled else value
        if not self._config.result_detection_enabled:
            return sanitized

        detections = await self._detect(sanitized)
        if not detections:
            return sanitized

        tokenized, mapping = self._tokenizer.tokenize(sanitized, detections)
        if mapping:
            self.token_mappings.update(mapping)
            if "agent_tool_result_sanitized" not in self.audit_events:
                self.audit_events.append("agent_tool_result_sanitized")
        return str(tokenized)

    def _mapping_entity_types(self) -> set[str]:
        entity_types: set[str] = set()
        for token in self.token_mappings:
            if token.startswith("[") and "_" in token:
                entity_types.add(token[1:].split("_", 1)[0].lower())
        return entity_types or ({"none"} if not self.token_mappings else set())

    async def _detect(self, value: str) -> list[dict[str, Any]]:
        if self._detection_engine is None:
            return []
        detector = getattr(self._detection_engine, "detect", None)
        if detector is None:
            return []

        raw = detector(value)
        detections = await raw if inspect.isawaitable(raw) else raw
        return [self._normalize_detection(item) for item in detections or []]

    def _normalize_detection(self, item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return {
                "entity_type": str(item.get("entity_type", "SENSITIVE")),
                "start": int(item.get("start", 0)),
                "end": int(item.get("end", 0)),
                "score": float(item.get("score", 1.0)),
                "source": item.get("source", "ner"),
            }
        if isinstance(item, DetectionResult):
            return {
                "entity_type": item.entity_type,
                "start": item.start,
                "end": item.end,
                "score": item.score,
                "source": item.source,
            }
        return {
            "entity_type": str(getattr(item, "entity_type", "SENSITIVE")),
            "start": int(getattr(item, "start", 0)),
            "end": int(getattr(item, "end", 0)),
            "score": float(getattr(item, "score", 1.0)),
            "source": str(getattr(item, "source", "ner")),
        }
