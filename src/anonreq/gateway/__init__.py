"""Gateway package — AI traffic detection, routing, and passthrough modes."""

from anonreq.gateway.detector import (
    AIDetector,
    MCPInspector,
    MCPMessage,
    ProviderMatch,
    TrafficClassification,
)
from anonreq.gateway.passthrough import GatewayStatus, ProxyMode, ProxyOnlyHandler
from anonreq.gateway.router import RouteEntry, RouteMatch, RouteTable

__all__ = [
    "AIDetector",
    "GatewayStatus",
    "MCPInspector",
    "MCPMessage",
    "ProviderMatch",
    "ProxyMode",
    "ProxyOnlyHandler",
    "RouteEntry",
    "RouteMatch",
    "RouteTable",
    "TrafficClassification",
]
