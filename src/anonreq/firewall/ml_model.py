from __future__ import annotations

from typing import Any, Protocol

from anonreq.firewall.models import DetectionCategory, DetectionResult, FirewallAction, SeverityLevel


class MLModel(Protocol):
    async def predict(self, text: str) -> list[DetectionResult]:
        ...

    async def load(self, path: str) -> None:
        ...


class NoopMLModel:
    def __init__(self) -> None:
        self._loaded = True

    async def load(self, path: str) -> None:
        pass

    async def predict(self, text: str) -> list[DetectionResult]:
        return []

    async def predict_batch(self, texts: list[str]) -> list[list[DetectionResult]]:
        return [[] for _ in texts]


class FirewallMLModel:
    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path
        self._session: Any = None
        self._input_name: str | None = None
        self._output_name: str | None = None

    async def load(self, path: str) -> None:
        import onnxruntime

        self._session = onnxruntime.InferenceSession(path)
        self._input_name = self._session.get_inputs()[0].name
        self._output_name = self._session.get_outputs()[0].name

    async def predict(self, text: str) -> list[DetectionResult]:
        if self._session is None:
            return []

        tokens = self._tokenize(text)
        import numpy as np

        input_array = np.array([tokens], dtype=np.int64)
        outputs = self._session.run(
            [self._output_name],
            {self._input_name: input_array},
        )

        return self._parse_output(outputs[0])

    async def predict_batch(self, texts: list[str]) -> list[list[DetectionResult]]:
        if self._session is None:
            return [[] for _ in texts]

        import numpy as np

        batch_tokens = [self._tokenize(t) for t in texts]
        input_array = np.array(batch_tokens, dtype=np.int64)
        outputs = self._session.run(
            [self._output_name],
            {self._input_name: input_array},
        )

        results: list[list[DetectionResult]] = []
        for logits in outputs:
            results.append(self._parse_output(logits))
        return results

    def _tokenize(self, text: str) -> list[int]:
        ids: list[int] = []
        for ch in text.strip().lower().split()[:512]:
            ids.append(hash(ch) % 10000 + 4)
        if not ids:
            ids = [0]
        return ids

    def _parse_output(self, logits: Any) -> list[DetectionResult]:
        import numpy as np

        categories = list(DetectionCategory)
        results: list[DetectionResult] = []

        if isinstance(logits, (list, np.ndarray)) and len(logits) > 0:
            if hasattr(logits, "shape") and len(logits.shape) == 2:
                probs = logits[0]
            else:
                probs = logits

            probs = np.array(probs, dtype=np.float64)
            if len(probs.shape) > 0:
                probs = probs.flatten()

            for idx, cat in enumerate(categories):
                if idx < len(probs):
                    confidence = float(min(1.0, max(0.0, probs[idx])))
                    if confidence >= 0.5:
                        results.append(
                            DetectionResult(
                                category=cat,
                                confidence=confidence,
                                rule_id=None,
                                severity=SeverityLevel.MEDIUM,
                                action=FirewallAction.FLAG_AND_FORWARD,
                                matched_text_snippet=None,
                            )
                        )

        return results
