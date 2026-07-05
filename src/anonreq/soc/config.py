"""SOC integration configuration model.

Per D-004, D-025:
- ``SOCConfig``: Top-level configuration for the SOC integration service
- ``gateway_version`` and ``appliance_instance_id`` populated at startup
"""

from __future__ import annotations

import socket

from pydantic import BaseModel, Field

from anonreq.__about__ import __version__


class SOCConfig(BaseModel):
    """Configuration for the SOC Integration Service.

    Attributes:
        enabled: Master enable/disable for the SOC integration service.
        event_bus_maxsize: Maximum pending events in the asyncio.Queue
            before detection engines start getting backpressure.
        gateway_version: AnonReq gateway version string, populated at
            startup from ``anonreq.__about__.__version__``.
        appliance_instance_id: Unique identifier for this appliance
            instance. Defaults to ``socket.gethostname()``.
    """

    enabled: bool = True
    event_bus_maxsize: int = 10000
    gateway_version: str = Field(default_factory=lambda: __version__)
    appliance_instance_id: str = Field(
        default_factory=lambda: socket.gethostname()
    )
