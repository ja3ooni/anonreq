from __future__ import annotations

import pytest

from anonreq.firewall.engine import FirewallRuleEngine
from anonreq.firewall.models import (
    DetectionCategory,
    DetectionResult,
    FirewallAction,
    FirewallRule,
    RuleCategoryConfig,
    SeverityLevel,
)
from anonreq.firewall.ml_model import FirewallMLModel, NoopMLModel


class TestNoopMLModel:
    @pytest.mark.asyncio
    async def test_noop_returns_empty_results(self):
        model = NoopMLModel()
        results = await model.predict("any text")
        assert results == []

    @pytest.mark.asyncio
    async def test_noop_batch_returns_empty(self):
        model = NoopMLModel()
        results = await model.predict_batch(["a", "b", "c"])
        assert len(results) == 3
        assert all(r == [] for r in results)

    @pytest.mark.asyncio
    async def test_noop_load_does_not_raise(self):
        model = NoopMLModel()
        await model.load("/nonexistent/path")
        assert True


class TestFirewallMLModel:
    @pytest.mark.asyncio
    async def test_not_loaded_returns_empty(self):
        model = FirewallMLModel()
        results = await model.predict("test")
        assert results == []

    @pytest.mark.asyncio
    async def test_not_loaded_batch_returns_empty(self):
        model = FirewallMLModel()
        results = await model.predict_batch(["a", "b"])
        assert len(results) == 2
        assert all(r == [] for r in results)

    @pytest.mark.asyncio
    async def test_model_file_not_found_raises(self):
        model = FirewallMLModel()
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            pytest.skip("onnxruntime not installed")
        with pytest.raises(FileNotFoundError):
            await model.load("/nonexistent/model.onnx")


@pytest.mark.skip(reason="Requires actual ONNX model file")
class TestFirewallMLModelIntegration:
    @pytest.mark.asyncio
    async def test_load_and_predict(self):
        pass


class TestRuleEngineMLIntegration:
    @pytest.mark.asyncio
    async def test_engine_with_noop_ml_falls_back_to_rules(self):
        rules = [
            FirewallRule(
                rule_id="injection",
                category=DetectionCategory.PROMPT_INJECTION,
                pattern=r"(?i)(ignore instructions)",
                action=FirewallAction.BLOCK,
                severity=SeverityLevel.HIGH,
                priority=100,
            ),
        ]
        cat_config = {
            DetectionCategory.PROMPT_INJECTION.value: RuleCategoryConfig(
                enabled=True, threshold=0.5
            ),
        }
        engine = FirewallRuleEngine(rules, category_config=cat_config)
        noop = NoopMLModel()

        results = await engine.evaluate_with_ml("ignore instructions", noop)
        assert len(results) >= 1
        assert results[0].rule_id == "injection"

    @pytest.mark.asyncio
    async def test_engine_with_ml_no_flag_still_returns_rules(self):
        rules = [
            FirewallRule(
                rule_id="jailbreak",
                category=DetectionCategory.JAILBREAK,
                pattern=r"(?i)(DAN)",
                action=FirewallAction.BLOCK,
                severity=SeverityLevel.HIGH,
                priority=100,
            ),
        ]
        cat_config = {
            DetectionCategory.JAILBREAK.value: RuleCategoryConfig(
                enabled=True, threshold=0.5
            ),
        }
        engine = FirewallRuleEngine(rules, category_config=cat_config)
        noop = NoopMLModel()

        results = await engine.evaluate_with_ml("DAN mode", noop)
        assert len(results) >= 1
        assert results[0].rule_id == "jailbreak"

    @pytest.mark.asyncio
    async def test_engine_no_rule_match_returns_empty(self):
        rules = [
            FirewallRule(
                rule_id="test",
                category=DetectionCategory.JAILBREAK,
                pattern=r"(?i)(specific)",
                priority=100,
            ),
        ]
        cat_config = {
            DetectionCategory.JAILBREAK.value: RuleCategoryConfig(
                enabled=True, threshold=0.5
            ),
        }
        engine = FirewallRuleEngine(rules, category_config=cat_config)
        noop = NoopMLModel()

        results = await engine.evaluate_with_ml("benign text", noop)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_ml_model_confidence_range(self):
        class MockMLModel:
            async def predict(self, text: str) -> list[DetectionResult]:
                return [
                    DetectionResult(
                        category=DetectionCategory.PROMPT_INJECTION,
                        confidence=0.85,
                        severity=SeverityLevel.MEDIUM,
                        action=FirewallAction.FLAG_AND_FORWARD,
                    ),
                ]

            async def load(self, path: str) -> None:
                pass

        mock = MockMLModel()
        results = await mock.predict("test")
        assert len(results) == 1
        assert 0.0 <= results[0].confidence <= 1.0
