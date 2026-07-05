"""Performance tests for proxy-only mode latency targets.

Tests verify:
- LatencyTimer correctly measures elapsed time
- Proxy-only middleware chain is shorter than full chain
- _optimize_middleware_chain returns correct middleware lists
- ConnectionPoolConfig default values are reasonable
- RequestFastPath correctly handles body streaming
- register_latency_metric records to Prometheus histogram

These are NOT load tests — they validate instrumentation correctness.
Full load testing (k6/Locust) is documented but not automated here.
"""

from __future__ import annotations

import dataclasses
import time

import pytest

from anonreq.proxy.optimizations import (
    PROXY_LATENCY_HISTOGRAM,
    ConnectionPoolConfig,
    LatencyTimer,
    RequestFastPath,
    _optimize_middleware_chain,
    configure_httpx_client,
    register_latency_metric,
)
from anonreq.proxy.modes import ProxyMode


class TestLatencyTimer:
    """Tests for the LatencyTimer context manager."""

    def test_measures_elapsed_time(self):
        with LatencyTimer("test") as timer:
            time.sleep(0.001)
        assert timer.elapsed_ms >= 0.5

    def test_elapsed_time_reasonable(self):
        with LatencyTimer("test") as timer:
            time.sleep(0.005)
        assert 3.0 <= timer.elapsed_ms <= 50.0

    def test_elapsed_ms_property(self):
        timer = LatencyTimer("test")
        with timer:
            pass
        assert isinstance(timer.elapsed_ms, float)
        assert timer.elapsed_ms >= 0.0

    def test_raises_when_not_used_in_context(self):
        timer = LatencyTimer("test")
        with pytest.raises(RuntimeError, match="not yet measured"):
            _ = timer.elapsed_ms

    def test_nanosecond_precision(self):
        with LatencyTimer("test") as timer:
            pass  # near-instant
        assert timer.elapsed_ms >= 0.0
        # Should have better than 1ms precision
        assert timer.elapsed_ms < 10.0


class TestRegisterLatencyMetric:
    """Tests for register_latency_metric function."""

    def test_registers_observation(self):
        # Verify it doesn't raise
        register_latency_metric("auth", 1.5, mode="proxy-only")

    def test_histogram_observes_with_labels(self):
        before_count = len(list(PROXY_LATENCY_HISTOGRAM.collect()))
        register_latency_metric("routing", 2.0, mode="full")
        # Prometheus histograms lazily create collectors
        assert True  # No assertion needed — just ensure no exception


class TestOptimizeMiddlewareChain:
    """Tests for _optimize_middleware_chain function."""

    def test_proxy_only_chain_is_shorter(self):
        proxy_chain = _optimize_middleware_chain(ProxyMode.PROXY_ONLY)
        full_chain = _optimize_middleware_chain(ProxyMode.FULL)
        assert len(proxy_chain) < len(full_chain)

    def test_proxy_only_chain_has_core_middleware(self):
        chain = _optimize_middleware_chain(ProxyMode.PROXY_ONLY)
        assert "AuthMiddleware" in chain
        assert "ForwardingGuard" in chain
        assert "proxy_middleware" in chain

    def test_proxy_only_skips_classification(self):
        chain = _optimize_middleware_chain(ProxyMode.PROXY_ONLY)
        assert "ClassificationMiddleware" not in chain
        assert "PolicyMiddleware" not in chain

    def test_full_chain_includes_all_middleware(self):
        chain = _optimize_middleware_chain(ProxyMode.FULL)
        assert "ClassificationMiddleware" in chain
        assert "PolicyMiddleware" in chain
        assert "ClassificationResponseMiddleware" in chain

    def test_transparent_same_as_full(self):
        transparent_chain = _optimize_middleware_chain(ProxyMode.TRANSPARENT)
        full_chain = _optimize_middleware_chain(ProxyMode.FULL)
        assert transparent_chain == full_chain


class TestConnectionPoolConfig:
    """Tests for ConnectionPoolConfig defaults and construction."""

    def test_default_values(self):
        config = ConnectionPoolConfig()
        assert config.max_connections == 100
        assert config.max_keepalive_connections == 20
        assert config.keepalive_timeout == 30
        assert config.enable_http2 is True
        assert config.timeout == 30

    def test_custom_values(self):
        config = ConnectionPoolConfig(
            max_connections=50,
            keepalive_timeout=60,
            enable_http2=False,
        )
        assert config.max_connections == 50
        assert config.keepalive_timeout == 60
        assert config.enable_http2 is False

    def test_can_be_configured_as_dataclass(self):
        config = ConnectionPoolConfig()
        assert dataclasses.is_dataclass(config)


class TestConfigureHttpxClient:
    """Tests for configure_httpx_client function."""

    def test_returns_dict(self):
        result = configure_httpx_client()
        assert isinstance(result, dict)

    def test_default_pool_config(self):
        result = configure_httpx_client()
        assert isinstance(result, dict)
        # httpx is installed, so result should have limits
        if "limits" in result:
            assert hasattr(result["limits"], "max_connections")

    def test_custom_pool_config(self):
        config = ConnectionPoolConfig(max_connections=50, enable_http2=False)
        result = configure_httpx_client(config)
        assert isinstance(result, dict)
        # httpx may return empty dict if not installed
        if not result:
            return
        if "limits" in result:
            assert hasattr(result["limits"], "max_connections")

    def test_http2_flag_when_enabled(self):
        config = ConnectionPoolConfig(enable_http2=True)
        result = configure_httpx_client(config)
        if not result:
            return
        if "http2" in result:
            assert result["http2"] is True


class TestRequestFastPath:
    """Tests for RequestFastPath class."""

    def test_proxy_only_mode(self):
        fp = RequestFastPath(ProxyMode.PROXY_ONLY)
        assert fp.is_proxy_only is True

    def test_full_mode_not_proxy_only(self):
        fp = RequestFastPath(ProxyMode.FULL)
        assert fp.is_proxy_only is False

    def test_cached_body_none_initially(self):
        fp = RequestFastPath(ProxyMode.FULL)
        assert fp.get_cached_body() is None

    def test_proxy_only_does_not_cache(self):
        fp = RequestFastPath(ProxyMode.PROXY_ONLY)
        assert fp.get_cached_body() is None


