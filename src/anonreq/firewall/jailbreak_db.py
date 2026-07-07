from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import Any


DEFAULT_JAILBREAK_PATTERNS: list[dict[str, Any]] = [
    {
        "pattern_id": "JB-001",
        "technique": "role_bypass",
        "regex": r"(?i)\b(do\s+anything\s+now|dan\s+mode|developer\s+mode)\b",
        "keywords": ["ignore", "policy"],
        "confidence": 0.95,
    },
    {
        "pattern_id": "JB-002",
        "technique": "safety_bypass",
        "regex": r"(?i)\b(bypass|disable|circumvent)\b.{0,80}\b(safety|guardrail|policy|filter)\b",
        "keywords": [],
        "confidence": 0.92,
    },
    {
        "pattern_id": "JB-003",
        "technique": "hypothetical_override",
        "regex": r"(?i)\b(in\s+a\s+hypothetical|fictional\s+scenario)\b.{0,80}\b(ignore|bypass)\b",
        "keywords": [],
        "confidence": 0.88,
    },
]


@dataclass(frozen=True)
class _CompiledPattern:
    source: dict[str, Any]
    regex: Pattern[str] | None
    keywords: tuple[str, ...]


class JailbreakDB:
    """Locally cached jailbreak pattern database.

    The production path points at a policy-pushed JSON file. If that file is not
    present, the class uses a conservative built-in baseline so the firewall can
    still fail closed on obvious jailbreak traffic without external downloads.
    """

    def __init__(self, db_path: str = "/etc/anonreq/firewall/jailbreak_db.json") -> None:
        self.db_path = db_path
        self._patterns: list[dict[str, Any]] = []
        self._compiled: list[_CompiledPattern] = []
        self._loaded = False

    async def load(self) -> None:
        path = Path(self.db_path)
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                patterns = raw.get("patterns", [])
            else:
                patterns = raw
            if not isinstance(patterns, list):
                raise ValueError("jailbreak DB must contain a list of patterns")
            self._patterns = [self._validate_pattern(item) for item in patterns]
        else:
            self._patterns = [dict(item) for item in DEFAULT_JAILBREAK_PATTERNS]
        self._compiled = [self._compile_pattern(item) for item in self._patterns]
        self._loaded = True

    async def reload(self) -> None:
        self._loaded = False
        await self.load()

    def match(self, text: str) -> list[dict[str, Any]]:
        if not self._loaded:
            self._patterns = [dict(item) for item in DEFAULT_JAILBREAK_PATTERNS]
            self._compiled = [self._compile_pattern(item) for item in self._patterns]
            self._loaded = True

        normalized = text.casefold()
        matches: list[dict[str, Any]] = []
        for compiled in self._compiled:
            regex_hit = compiled.regex.search(text) if compiled.regex else None
            keyword_hit = bool(compiled.keywords) and all(k in normalized for k in compiled.keywords)
            if not regex_hit and not keyword_hit:
                continue
            source = compiled.source
            matches.append(
                {
                    "pattern_id": source["pattern_id"],
                    "confidence": float(source.get("confidence", 0.85)),
                    "technique": source.get("technique", "jailbreak"),
                }
            )
        return sorted(matches, key=lambda item: item["confidence"], reverse=True)

    def get_patterns(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._patterns]

    def _validate_pattern(self, item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise ValueError("jailbreak pattern must be an object")
        pattern_id = item.get("pattern_id")
        if not isinstance(pattern_id, str) or not pattern_id:
            raise ValueError("jailbreak pattern requires pattern_id")
        confidence = float(item.get("confidence", 0.85))
        if confidence < 0.0 or confidence > 1.0:
            raise ValueError("jailbreak pattern confidence must be between 0 and 1")
        regex = item.get("regex")
        keywords = item.get("keywords", [])
        if regex is not None and not isinstance(regex, str):
            raise ValueError("jailbreak pattern regex must be a string")
        if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
            raise ValueError("jailbreak pattern keywords must be strings")
        return {
            "pattern_id": pattern_id,
            "technique": str(item.get("technique", "jailbreak")),
            "regex": regex,
            "keywords": keywords,
            "confidence": confidence,
        }

    def _compile_pattern(self, item: dict[str, Any]) -> _CompiledPattern:
        regex = re.compile(item["regex"]) if item.get("regex") else None
        keywords = tuple(k.casefold() for k in item.get("keywords", []))
        return _CompiledPattern(source=item, regex=regex, keywords=keywords)
