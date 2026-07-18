from __future__ import annotations

import json
import re
from typing import Any

from anonreq.multimodal.models import ContentType, UnifiedDetectionResult

SENSITIVE_KEY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ssn"),
    re.compile(r"social.security"),
    re.compile(r"password"),
    re.compile(r"secret"),
    re.compile(r"token"),
    re.compile(r"api.key"),
    re.compile(r"credit.card"),
    re.compile(r"bank.account"),
    re.compile(r"pin"),
    re.compile(r"cvv"),
    re.compile(r"passport"),
    re.compile(r"license.number"),
    re.compile(r"medical.record"),
    re.compile(r"dob"),
]


class JsonAnalyzer:
    def __init__(
        self,
        detection_engine: Any | None = None,
        max_depth: int = 50,
    ) -> None:
        self._detection_engine = detection_engine
        self._max_depth = max_depth

    async def analyze(
        self,
        json_data: str | bytes | dict[str, Any],
        path: str = "$",
    ) -> UnifiedDetectionResult:
        result = UnifiedDetectionResult(content_type=ContentType.APPLICATION_JSON)

        if isinstance(json_data, (str, bytes)):
            try:
                parsed = json.loads(json_data)
            except (json.JSONDecodeError, ValueError) as exc:
                result.analyzer_metadata = {"error": str(exc)}
                return result
        else:
            parsed = json_data

        entities: list[dict[str, Any]] = []
        await self._walk_node(parsed, path, 0, entities, result)
        result.entities = entities
        return result

    async def _walk_node(
        self,
        node: Any,
        path: str,
        depth: int,
        entities: list[dict[str, Any]],
        result: UnifiedDetectionResult,
    ) -> None:
        if depth > self._max_depth:
            return

        if isinstance(node, dict):
            for key, value in node.items():
                child_path = f"{path}.{key}"
                is_sensitive = self._is_sensitive_key(key)
                await self._walk_node(value, child_path, depth + 1, entities, result)

                if isinstance(value, str) and is_sensitive:
                    await self._analyze_string(value, child_path, entities, is_sensitive=True)

        elif isinstance(node, list):
            for i, item in enumerate(node):
                child_path = f"{path}[{i}]"
                await self._walk_node(item, child_path, depth + 1, entities, result)

        elif isinstance(node, str):
            await self._analyze_string(node, path, entities, is_sensitive=False)

    def _is_sensitive_key(self, key: str) -> bool:
        lowered = key.lower().replace("_", ".")
        return any(pattern.search(lowered) for pattern in SENSITIVE_KEY_PATTERNS)

    async def _analyze_string(
        self,
        value: str,
        path: str,
        entities: list[dict[str, Any]],
        is_sensitive: bool = False,
    ) -> None:
        if self._detection_engine is None:
            return

        detections = await self._detection_engine.analyze_text(value)
        for det in detections:
            item = dict(det)
            item["json_path"] = path
            if is_sensitive:
                score = item.get("score", 0.0)
                item["score"] = min(score + 0.15, 1.0)
                item["sensitive_key_boosted"] = True
            entities.append(item)
