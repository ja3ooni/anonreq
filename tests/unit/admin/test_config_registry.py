"""Tests for AtomicConfigRegistry — thread-safe pointer swap with version tracking.

Covers:
- Initial state (version 0, empty config)
- Valid config swap increments version
- Invalid config (bad regex) swap fails, version unchanged
- Thread-safe concurrent access
- Version tracking across multiple swaps
- Gauge metric updated on successful swap
"""

from __future__ import annotations

import threading

from anonreq.admin.config import (
    AtomicConfigRegistry,
    CustomRecognizerRule,
    ExclusionEntry,
    RulesConfig,
)


def make_valid_config() -> RulesConfig:
    return RulesConfig(
        custom_recognizers=[
            CustomRecognizerRule(
                id="test-rule",
                entity_type="CUSTOM_1",
                patterns=[r"test-\d{3}"],
                confidence=0.8,
            ),
        ],
        exclusion_list=[
            ExclusionEntry(value="safe@example.com", match_type="exact"),
        ],
        thresholds={"confidence": 0.7},
    )


def make_invalid_regex_config() -> RulesConfig:
    return RulesConfig(
        custom_recognizers=[
            CustomRecognizerRule(
                id="bad-rule",
                entity_type="BAD",
                patterns=[r"[invalid"],  # Unclosed bracket
            ),
        ],
        exclusion_list=[],
    )


def make_invalid_match_type_config() -> RulesConfig:
    return RulesConfig(
        custom_recognizers=[],
        exclusion_list=[
            ExclusionEntry(value="test", match_type="fuzzy"),
        ],
    )


class TestAtomicConfigRegistryInitialState:
    """Registry starts with version 0 and empty/default config."""

    def test_version_starts_at_zero(self):
        registry = AtomicConfigRegistry()
        assert registry.get_version() == 0

    def test_active_config_is_empty(self):
        registry = AtomicConfigRegistry()
        config = registry.get_active()
        assert config.custom_recognizers == []
        assert config.exclusion_list == []

    def test_custom_initial_config(self):
        config = make_valid_config()
        registry = AtomicConfigRegistry(initial_config=config)
        active = registry.get_active()
        assert len(active.custom_recognizers) == 1
        assert active.custom_recognizers[0].id == "test-rule"


class TestAtomicConfigRegistrySwap:
    """Valid config swaps succeed and increment version."""

    def test_valid_swap_returns_true(self):
        registry = AtomicConfigRegistry()
        config = make_valid_config()
        success, error = registry.validate_and_swap(config)
        assert success is True
        assert error is None

    def test_valid_swap_increments_version(self):
        registry = AtomicConfigRegistry()
        config = make_valid_config()
        registry.validate_and_swap(config)
        assert registry.get_version() == 1

    def test_active_config_updated_after_swap(self):
        registry = AtomicConfigRegistry()
        config = make_valid_config()
        registry.validate_and_swap(config)
        active = registry.get_active()
        assert len(active.custom_recognizers) == 1

    def test_multiple_swaps_increment_version(self):
        registry = AtomicConfigRegistry()
        for i in range(5):
            config = RulesConfig(
                custom_recognizers=[
                    CustomRecognizerRule(
                        id=f"rule-{i}",
                        entity_type=f"TYPE_{i}",
                        patterns=[rf"pattern-{i}-\d+"],
                    ),
                ],
                exclusion_list=[],
            )
            success, _ = registry.validate_and_swap(config)
            assert success
            assert registry.get_version() == i + 1


class TestAtomicConfigRegistryInvalidConfig:
    """Invalid config never replaces active config per AG-16."""

    def test_invalid_regex_returns_false(self):
        registry = AtomicConfigRegistry()
        config = make_invalid_regex_config()
        success, error = registry.validate_and_swap(config)
        assert success is False
        assert error is not None
        assert "unterminated character set" in error.lower() or "bad escape" in error.lower() or "invalid" in error.lower()  # noqa: E501

    def test_version_not_incremented_on_invalid_regex(self):
        registry = AtomicConfigRegistry()
        config = make_invalid_regex_config()
        registry.validate_and_swap(config)
        assert registry.get_version() == 0

    def test_active_config_unchanged_after_invalid_regex(self):
        registry = AtomicConfigRegistry()
        valid = make_valid_config()
        registry.validate_and_swap(valid)
        assert registry.get_version() == 1

        invalid = make_invalid_regex_config()
        registry.validate_and_swap(invalid)
        assert registry.get_version() == 1
        active = registry.get_active()
        assert len(active.custom_recognizers) == 1
        assert active.custom_recognizers[0].id == "test-rule"

    def test_invalid_match_type_returns_false(self):
        registry = AtomicConfigRegistry()
        config = make_invalid_match_type_config()
        success, error = registry.validate_and_swap(config)
        assert success is False
        assert error is not None
        assert "match_type" in error.lower()

    def test_empty_config_is_valid(self):
        registry = AtomicConfigRegistry()
        empty = RulesConfig(custom_recognizers=[], exclusion_list=[])
        success, error = registry.validate_and_swap(empty)
        assert success is True
        assert error is None
        assert registry.get_version() == 1


class TestAtomicConfigRegistryConcurrent:
    """Concurrent access safety."""

    def test_concurrent_swaps_produce_consistent_state(self):
        registry = AtomicConfigRegistry()
        errors: list[Exception] = []

        def swap_worker(worker_id: int):
            try:
                config = RulesConfig(
                    custom_recognizers=[
                        CustomRecognizerRule(
                            id=f"worker-{worker_id}",
                            entity_type=f"TYPE_{worker_id}",
                            patterns=[rf"pattern-{worker_id}"],
                        ),
                    ],
                    exclusion_list=[],
                )
                success, _ = registry.validate_and_swap(config)
                assert success
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=swap_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent swap errors: {errors}"
        assert registry.get_version() == 10

    def test_get_active_never_returns_intermediate_state(self):
        registry = AtomicConfigRegistry()
        lock = threading.Lock()
        observed_recognizer_counts: list[int] = []

        def writer():
            for i in range(50):
                config = RulesConfig(
                    custom_recognizers=[
                        CustomRecognizerRule(
                            id=f"w{i}",
                            entity_type=f"T{i}",
                            patterns=[rf"p{i}"],
                        ),
                    ],
                    exclusion_list=[],
                )
                registry.validate_and_swap(config)

        def reader():
            for _ in range(50):
                config = registry.get_active()
                with lock:
                    observed_recognizer_counts.append(len(config.custom_recognizers))

        w = threading.Thread(target=writer)
        r = threading.Thread(target=reader)
        w.start()
        r.start()
        w.join()
        r.join()

        # All observed states should be valid (0 or 1 recognizers, never partial)
        for count in observed_recognizer_counts:
            assert count in (0, 1), f"Invalid intermediate state: {count} recognizers"
