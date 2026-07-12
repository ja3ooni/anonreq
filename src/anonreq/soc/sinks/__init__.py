"""SIEM sink base abstractions for the SOC Integration Service.

Provides:
- ``SinkBase``: Runtime-checkable protocol for all SIEM sink implementations
- ``SinkStatus``: Dataclass for per-sink health status
- ``SinkHealth``: Enum for sink health states
"""

from __future__ import annotations

from dataclasses import dataclass, field  # noqa: F401
from datetime import datetime
from enum import Enum, StrEnum  # noqa: F401
from typing import Any, Protocol, runtime_checkable


class SinkHealth(StrEnum):
    """Sink health state."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class SinkStatus:
    """Per-sink health and operational status.

    Attributes:
        healthy: Whether the sink is operating normally.
        reachable: Whether the sink endpoint is reachable.
        last_successful_delivery: Timestamp of last successful event send.
        last_error: Error message from last failed delivery attempt.
        buffer_size: Current number of events in the per-sink buffer.
    """

    healthy: bool = True
    reachable: bool = True
    last_successful_delivery: datetime | None = None
    last_error: str | None = None
    buffer_size: int = 0


@runtime_checkable
class SinkBase(Protocol):
    """Protocol that all SIEM sink implementations must satisfy.

    Attributes:
        name: Human-readable name for this sink instance.
        sink_type: Machine-readable sink type identifier.
        enabled: Whether this sink is active.
    """

    name: str
    sink_type: str
    enabled: bool

    async def start(self) -> None:
        """Start the sink — open connections, create clients."""
        ...

    async def stop(self) -> None:
        """Stop the sink — close connections, clean up."""
        ...

    async def send_event(self, event: Any) -> bool:
        """Send a normalized event to this sink.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            True if delivery was successful, False otherwise.
        """
        ...

    async def health_check(self) -> SinkStatus:
        """Check sink connectivity and return current status.

        Returns:
            Current ``SinkStatus`` with reachability and error info.
        """
        ...

    async def format_event(self, event: Any) -> str | bytes | dict:
        """Format a NormalizedEvent into the sink's wire format.

        Args:
            event: A ``NormalizedEvent`` instance.

        Returns:
            Formatted event in the sink's specific wire format.
        """
        ...
