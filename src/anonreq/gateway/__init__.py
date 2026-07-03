"""Gateway package — AI traffic detection, routing, and passthrough modes."""

from anonreq.gateway.detector import AIDetector, MCPInspector, MCPMessage, ProviderMatch, TrafficClassification
from anonreq.gateway.router import RouteEntry, RouteMatch, RouteTable
from anonreq.gateway.passthrough import GatewayStatus, ProxyMode, ProxyOnlyHandler

__all__ = [
    "AIDetector",
    "MCPInspector",
    "MCPMessage",
    "ProviderMatch",
    "TrafficClassification",
    "RouteEntry",
    "RouteMatch",
    "RouteTable",
    "GatewayStatus",
    "ProxyMode",
    "ProxyOnlyHandler",
]
