"""Endpoint Agent — local traffic capture, AI app discovery, and telemetry.

Provides:
- EndpointAgent: async lifecycle manager for the endpoint agent
- AppDiscovery: local process scanner for AI desktop applications
- TrafficCapture: packet/network capture with AI provider filtering (macOS)
- EndpointConfig: YAML + env var configuration
"""

from anonreq.endpoint.agent import EndpointAgent
from anonreq.endpoint.config import EndpointConfig, load_config
from anonreq.endpoint.discovery import KNOWN_AI_APPS, AppDiscovery

__all__ = [
    "KNOWN_AI_APPS",
    "AppDiscovery",
    "EndpointAgent",
    "EndpointConfig",
    "load_config",
]
