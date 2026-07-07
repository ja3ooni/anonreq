from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


InferenceSessionFactory = Callable[[str], Any]


@dataclass(frozen=True)
class StructuralClassification:
    detected: bool
    score: float
    detection_type: str | None = None
    rule_id: str | None = None


class ONNXClassifier:
    """Small local ONNX classifier wrapper with lazy, injectable session loading."""

    def __init__(
        self,
        model_path: str,
        session: Any | None = None,
        session_factory: InferenceSessionFactory | None = None,
    ) -> None:
        self.model_path = model_path
        self._session = session
        self._session_factory = session_factory
        self._input_name: str | None = None
        self._output_name: str | None = None
        if session is not None:
            self._bind_session(session)

    def load(self) -> None:
        if self._session is not None:
            return
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"ONNX firewall model not found: {self.model_path}")
        factory = self._session_factory
        if factory is None:
            import onnxruntime as ort

            factory = ort.InferenceSession
        self._bind_session(factory(self.model_path))

    def predict(self, text: str) -> np.ndarray:
        self.load()
        if self._session is None or self._input_name is None:
            raise RuntimeError("ONNX classifier session is not loaded")
        tokens = np.array([self._tokenize(text)], dtype=np.int64)
        output_names = [self._output_name] if self._output_name else None
        outputs = self._session.run(output_names, {self._input_name: tokens})
        if not outputs:
            return np.array([], dtype=np.float32)
        return np.asarray(outputs[0], dtype=np.float32).flatten()

    def score(self, text: str) -> float:
        vector = self.predict(text)
        if vector.size == 0:
            return 0.0
        return float(max(0.0, min(1.0, np.max(vector))))

    def _bind_session(self, session: Any) -> None:
        self._session = session
        inputs = session.get_inputs()
        outputs = session.get_outputs() if hasattr(session, "get_outputs") else []
        self._input_name = inputs[0].name
        self._output_name = outputs[0].name if outputs else None

    def _tokenize(self, text: str, max_tokens: int = 128) -> list[int]:
        tokens = re.findall(r"[a-z0-9_]+", text.casefold())[:max_tokens]
        ids = [abs(hash(token)) % 30000 + 4 for token in tokens]
        if not ids:
            ids = [0]
        if len(ids) < max_tokens:
            ids.extend([0] * (max_tokens - len(ids)))
        return ids


class StructuralClassifier:
    """Fast local pre-classifier for obvious injection and jailbreak structures."""

    _RULES: tuple[tuple[str, str, str, float], ...] = (
        (
            "STRUCT-001",
            "prompt_injection",
            r"(?i)\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above)\b.{0,40}\b(instruction|message|prompt)s?\b",
            0.91,
        ),
        (
            "STRUCT-002",
            "role_manipulation",
            r"(?i)\b(you\s+are\s+now|from\s+now\s+on|pretend\s+to\s+be|act\s+as)\b",
            0.88,
        ),
        (
            "STRUCT-003",
            "jailbreak",
            r"(?i)\b(DAN|do\s+anything\s+now|developer\s+mode|jailbreak)\b",
            0.94,
        ),
        (
            "STRUCT-004",
            "model_theft_attempt",
            r"(?i)\b(reveal|print|show)\b.{0,40}\b(system\s+prompt|hidden\s+instruction|developer\s+message)\b",
            0.93,
        ),
    )

    def __init__(self) -> None:
        self._compiled = [(rid, dtype, re.compile(pattern), score) for rid, dtype, pattern, score in self._RULES]

    def classify(self, text: str) -> StructuralClassification:
        for rule_id, detection_type, pattern, score in self._compiled:
            if pattern.search(text):
                return StructuralClassification(
                    detected=True,
                    score=score,
                    detection_type=detection_type,
                    rule_id=rule_id,
                )
        return StructuralClassification(detected=False, score=0.0)
