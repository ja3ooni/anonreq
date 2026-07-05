"""Appliance management agent for the AnonReq virtual appliance.

Provides the ``ApplianceAgent`` class that manages Docker Compose lifecycle,
health checks, configuration management, and update operations for the
AnonReq gateway running as a virtual appliance (VM/AMI).

Per D-017, D-018, D-019:
- Runs as a systemd service outside Docker
- Manages Docker Compose lifecycle for anonreq services
- Appliance mode may exclude non-essential services (MinIO, Grafana)
"""

from __future__ import annotations
