"""macOS endpoint agent implementation.

Provides:
- TrafficCapture: macOS-specific packet capture with AI traffic filtering
"""

from anonreq.endpoint.macos.capture import TrafficCapture

__all__ = [
    "TrafficCapture",
]
