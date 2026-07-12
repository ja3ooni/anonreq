"""Property-based tests for DLP invariants (Plan 13-04, Task 3).

Uses Hypothesis to prove DLP invariants hold across random inputs:

- Invariant 1: DLP action monotonicity — more sensitive content never reduces
  action severity
- Invariant 2: Exfiltration encoding detection — known encoding patterns are
  always detected (Base64, hex, JWT, PEM)
- Invariant 3: Contextual tightening — tightening only, never loosening
- Invariant 4: Tenant isolation — tenant A custom patterns never affect
  tenant B
- Invariant 5: Empty/basic content handling — benign content produces no
  DLP detection
"""

from __future__ import annotations

import pytest
import yaml
from hypothesis import assume, given
from hypothesis import strategies as st

from anonreq.models.dlp import DLPAction, DLPCategory, DLPDetection

# ===========================================================================
# Strategies
# ===========================================================================

encoding_strategies = st.sampled_from(["base64", "hex", "jwt", "pem"])
action_strategies = st.sampled_from(list(DLPAction))


@pytest.fixture(scope="module")
def dlp_config():
    with open("config/dlp.yaml") as f:
        data = yaml.safe_load(f)
    return data["dlp"]


@pytest.fixture(scope="module")
def mitre_config():
    with open("config/mitre_attack.yaml") as f:
        data = yaml.safe_load(f)
    return data["mitre_attack"]


# ===========================================================================
# Invariant 1: DLP detection monotonicity
# ===========================================================================


class TestDLPMonotonicity:
    """DLP detection is monotonic — more sensitive content never reduces
    action severity."""

    def test_max_action_is_most_restrictive(self):
        """_compute_max_action returns the most restrictive action."""
        from anonreq.services.dlp_engine import DLPEngine

        engine = DLPEngine({"core_categories": {}})

        # BLOCK > QUARANTINE > REDACT > ANONYMIZE > ALLOW
        detections = [
            DLPDetection(
                category=DLPCategory.PII,
                action=DLPAction.ANONYMIZE,
                match_text="test",
                confidence=0.9,
                start=0, end=4,
                pattern_id="test",
            ),
            DLPDetection(
                category=DLPCategory.CREDENTIALS,
                action=DLPAction.BLOCK,
                match_text="secret",
                confidence=0.9,
                start=0, end=6,
                pattern_id="test2",
            ),
        ]
        max_action = engine._compute_max_action(detections)
        assert max_action == DLPAction.BLOCK

    def test_allow_is_least_restrictive(self):
        """ALLOW is lowest in the action hierarchy."""
        from anonreq.services.dlp_engine import DLPEngine

        engine = DLPEngine({"core_categories": {}})

        detections = [
            DLPDetection(
                category=DLPCategory.PII,
                action=DLPAction.ALLOW,
                match_text="ok",
                confidence=0.9,
                start=0, end=2,
                pattern_id="test",
            ),
        ]
        max_action = engine._compute_max_action(detections)
        assert max_action == DLPAction.ALLOW

    @given(action_strategies, action_strategies)
    def test_tightening_is_monotonic(self, base_action: DLPAction, tighter_action: DLPAction):
        """Tightening never loosens: adding a more restrictive action
        results in max action >= base."""
        from anonreq.services.dlp_engine import DLPEngine

        engine = DLPEngine({"core_categories": {}})

        detections = [
            DLPDetection(
                category=DLPCategory.PII,
                action=base_action,
                match_text="base",
                confidence=0.9,
                start=0, end=4,
                pattern_id="test",
            ),
            DLPDetection(
                category=DLPCategory.CREDENTIALS,
                action=tighter_action,
                match_text="secret",
                confidence=0.9,
                start=0, end=6,
                pattern_id="test2",
            ),
        ]
        max_action = engine._compute_max_action(detections)
        action_rank = {
            DLPAction.ALLOW: 0,
            DLPAction.ANONYMIZE: 1,
            DLPAction.REDACT: 2,
            DLPAction.QUARANTINE: 3,
            DLPAction.BLOCK: 4,
        }
        # Adding any action should never produce a less restrictive result
        assert action_rank[max_action] >= action_rank[base_action]


# ===========================================================================
# Invariant 2: Exfiltration encoding detection
# ===========================================================================


class TestExfiltrationEncodingDetection:
    """Known encoding patterns are always detected for their encoding type."""

    @pytest.mark.asyncio
    @given(encoding_strategies)
    async def test_known_encoding_detected(self, encoding_type: str):
        """Each known encoding type is detected by the exfiltration detector."""
        from anonreq.services.exfiltration_detector import ExfiltrationDetector

        config = {
            "exfiltration": {
                "detection": {
                    "methods": {
                        "base64": {
                            "enabled": True,
                            "min_length": 4,
                            "pattern": "[A-Za-z0-9+/]{4,}={0,2}",
                            "entropy_threshold": 4.5,
                        },
                        "hex": {
                            "enabled": True,
                            "min_length": 4,
                            "pattern": "[0-9a-fA-F]{4,}",
                        },
                        "jwt": {
                            "enabled": True,
                            "pattern": "[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+",
                        },
                        "pem": {
                            "enabled": True,
                            "pattern": "-----BEGIN [A-Z ]+-----",
                        },
                    },
                    "entropy": {"enabled": False},
                    "heuristics": {"enabled": False},
                }
            }
        }

        detector = ExfiltrationDetector(config)

        test_inputs = {
            "base64": "SGVsbG8gV29ybGQgVGhpcyBpcyBhIHRlc3QgbWVzc2FnZQo=",
            "hex": "48656c6c6f20576f726c64205468697320697320612074657374",
            "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNvrPmhg",
            "pem": "-----BEGIN CERTIFICATE-----\nMIIDazCCAlM=\n-----END CERTIFICATE-----",
        }

        assume(encoding_type in test_inputs)
        result = await detector.detect(test_inputs[encoding_type])
        assert any(r.method == encoding_type for r in result), (
            f"{encoding_type} not detected in {test_inputs[encoding_type][:30]}..."
        )


# ===========================================================================
# Invariant 3: Contextual tightening
# ===========================================================================


class TestContextualTightening:
    """Contextual tightening is monotonic — never loosens."""

    @given(action_strategies, action_strategies)
    def test_tightening_never_loosens(self, base_action: DLPAction, tightening_action: DLPAction):
        """Combining any two actions always produces a result >= the max."""
        from anonreq.services.dlp_engine import DLPEngine

        engine = DLPEngine({"core_categories": {}})
        action_rank = {
            DLPAction.ALLOW: 0,
            DLPAction.ANONYMIZE: 1,
            DLPAction.REDACT: 2,
            DLPAction.QUARANTINE: 3,
            DLPAction.BLOCK: 4,
        }

        combined = engine._compute_max_action([
            DLPDetection(
                category=DLPCategory.PII,
                action=base_action,
                match_text="base",
                confidence=0.9,
                start=0, end=4,
                pattern_id="test",
            ),
            DLPDetection(
                category=DLPCategory.CREDENTIALS,
                action=tightening_action,
                match_text="secret",
                confidence=0.9,
                start=0, end=6,
                pattern_id="test2",
            ),
        ])

        # Combined should be >= max of individual ranks
        max_individual = max(action_rank[base_action], action_rank[tightening_action])
        assert action_rank[combined] >= max_individual

    @given(st.lists(action_strategies, min_size=0, max_size=10))
    def test_any_set_is_consistent(self, actions: list[DLPAction]):
        """Any set of actions produces a consistent result (no exceptions)."""
        from anonreq.services.dlp_engine import DLPEngine

        engine = DLPEngine({"core_categories": {}})

        detections = [
            DLPDetection(
                category=DLPCategory.PII,
                action=a,
                match_text=f"t{i}",
                confidence=0.9,
                start=0, end=2,
                pattern_id=f"t{i}",
            )
            for i, a in enumerate(actions)
        ]

        # Should not raise any exception
        if not detections:
            assert True
        else:
            result = engine._compute_max_action(detections)
            assert result in list(DLPAction)


# ===========================================================================
# Invariant 4: Tenant isolation
# ===========================================================================


class TestTenantIsolationProperty:
    """Tenant A custom patterns never affect Tenant B."""

    @pytest.mark.asyncio
    async def test_tenant_isolation(self):
        """Custom patterns for tenant A do not trigger for tenant B."""
        from anonreq.services.dlp_engine import DLPEngine

        engine = DLPEngine({"core_categories": {}})

        # Register custom pattern for tenant_a
        engine.load_tenant_patterns("tenant_a", {
            "patterns": [
                {
                    "id": "trading_strategy",
                    "regex": "TRADING_STRATEGY_\\d{6}",
                    "category": "Intellectual Property",
                    "action": "block",
                },
            ],
        })

        # Tenant B should NOT trigger on tenant A's custom pattern
        tenant_b_text = "My TRADING_STRATEGY_202601 is proprietary"
        result_b = await engine.inspect(tenant_b_text, "tenant_b")
        assert result_b.max_action == DLPAction.ALLOW

        # Tenant A SHOULD trigger
        result_a = await engine.inspect(tenant_b_text, "tenant_a")
        assert result_a.max_action != DLPAction.ALLOW

    @pytest.mark.asyncio
    async def test_tenant_b_empty_patterns_not_inherited(self):
        """Tenant B with no custom patterns stays unaffected."""
        from anonreq.services.dlp_engine import DLPEngine

        engine = DLPEngine({"core_categories": {}})

        # Register pattern only for tenant_a
        engine.load_tenant_patterns("tenant_a", {
            "patterns": [
                {
                    "id": "merger_data",
                    "regex": "MERGER_\\d{8}",
                    "category": "Intellectual Property",
                    "action": "block",
                },
            ],
        })

        # Tenant B should have no custom patterns
        assert "tenant_b" not in engine._tenant_patterns


# ===========================================================================
# Invariant 5: Empty/basic content handling
# ===========================================================================


class TestEmptyContentHandling:
    """Empty or basic content produces no DLP detection."""

    @pytest.mark.asyncio
    async def test_empty_string_no_detections(self, dlp_config):
        """Empty string produces no DLP detections."""
        from anonreq.services.dlp_engine import DLPEngine

        engine = DLPEngine(dlp_config)
        result = await engine.inspect("")
        assert result.max_action == DLPAction.ALLOW
        assert len(result.detections) == 0

    @pytest.mark.asyncio
    async def test_simple_text_no_detections(self, dlp_config):
        """Simple benign text produces no DLP detections."""
        from anonreq.services.dlp_engine import DLPEngine

        engine = DLPEngine(dlp_config)
        result = await engine.inspect("Hello, how are you today?")
        assert result.max_action == DLPAction.ALLOW
        assert len(result.detections) == 0

    @pytest.mark.asyncio
    async def test_whitespace_no_detections(self, dlp_config):
        """Whitespace-only content produces no DLP detections."""
        from anonreq.services.dlp_engine import DLPEngine

        engine = DLPEngine(dlp_config)
        result = await engine.inspect("   \n  \t  \n  ")
        assert result.max_action == DLPAction.ALLOW
        assert len(result.detections) == 0

    @pytest.mark.asyncio
    async def test_plain_text_no_false_positives(self, dlp_config):
        """Simple conversational text triggers minimal or no DLP detections."""
        from anonreq.services.dlp_engine import DLPEngine

        engine = DLPEngine(dlp_config)
        # Benign conversational text should not trigger CREDENTIALS or HEALTH
        result = await engine.inspect("I was wondering if you could help me with a question I have about programming")  # noqa: E501
        non_benign = [
            d for d in result.detections
            if d.category in (DLPCategory.CREDENTIALS, DLPCategory.HEALTH,
                              DLPCategory.EXPORT_CONTROLLED, DLPCategory.INTELLECTUAL_PROPERTY,
                              DLPCategory.EXFILTRATION)
        ]
        assert len(non_benign) == 0, f"Benign text triggered non-benign categories: {non_benign}"
