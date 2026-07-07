"""AI Application Discovery — local process scanner.

Scans running processes to detect known AI desktop applications
(Cursor, Claude Desktop, ChatGPT Desktop, VS Code with Copilot).
Emits audit-safe events with metadata only (no process paths).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from anonreq.discovery.hostname_matcher import HostnameMatcher

# Known AI application signatures.
# Each entry defines how to identify the app from process info.
# bundle_id is used on macOS, process_name is cross-platform.
KNOWN_AI_APPS: list[dict[str, Any]] = [
    {
        "name": "Cursor",
        "process_names": ["Cursor"],
        "bundle_id": "com.todesktop.230113mto6h4b5r",
    },
    {
        "name": "Claude Desktop",
        "process_names": ["Claude", "Claude Desktop"],
        "bundle_id": "com.anthropic.claudedesktop",
    },
    {
        "name": "ChatGPT Desktop",
        "process_names": ["ChatGPT"],
        "bundle_id": "com.openai.chat",
    },
    {
        "name": "VS Code (Copilot)",
        "process_names": ["Code", "Code - Insiders", "VSCodium"],
        "bundle_id": "com.microsoft.VSCode",
        "requires_extension": "GitHub.copilot",
    },
]


class AppDiscovery:
    """Scans local processes for known AI applications.

    Args:
        audit_logger: Optional structured logger for audit events.
            Must implement .info(event_type, **fields).
    """

    def __init__(self, audit_logger: Any = None) -> None:
        self._audit_logger = audit_logger

    def discover_apps(self) -> list[dict[str, Any]]:
        """Scan running processes and return discovered AI apps.

        Returns:
            List of app dicts with keys: app_name, pid, bundle_id,
            version, detected_at.
        """
        processes = self._enumerate_processes()
        apps: list[dict[str, Any]] = []

        for proc in processes:
            app = self._match_app(proc)
            if app is not None:
                apps.append(app)

        return apps

    def discover_and_emit(self) -> list[dict[str, Any]]:
        """Scan, return apps, and emit audit events for new discoveries.

        Returns:
            List of discovered app dicts.
        """
        apps = self.discover_apps()
        for app in apps:
            self._emit_discovered(app)
        return apps

    def _match_app(self, proc: dict[str, Any]) -> dict[str, Any] | None:
        """Match a process dict against known AI app signatures.

        Args:
            proc: Process dict with at least "name" key.

        Returns:
            App dict if matched, None otherwise.
        """
        proc_name = proc.get("name", "")
        proc_extensions = proc.get("extensions", [])

        for known in KNOWN_AI_APPS:
            if proc_name not in known["process_names"]:
                continue

            # If app requires a specific extension, check for it
            requires_ext = known.get("requires_extension")
            if requires_ext and requires_ext not in proc_extensions:
                continue

            return {
                "app_name": known["name"],
                "pid": proc.get("pid"),
                "bundle_id": known.get("bundle_id", ""),
                "version": proc.get("version", ""),
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }

        return None

    def _emit_discovered(self, app: dict[str, Any]) -> None:
        """Emit ai_app_discovered audit event.

        Emits metadata only — no process paths or raw user info.

        Args:
            app: App dict from discover_apps().
        """
        if self._audit_logger is None:
            return

        # Audit-safe fields only — no paths, no raw user data
        self._audit_logger.info(
            "ai_app_discovered",
            app_name=app["app_name"],
            pid=app["pid"],
            bundle_id=app.get("bundle_id", ""),
            version=app.get("version", ""),
            detected_at=app["detected_at"],
        )

    def _enumerate_processes(self) -> list[dict[str, Any]]:
        """Enumerate running processes on the local system.

        This method is the platform-specific hook. The base implementation
        returns an empty list. Subclasses or platform modules override this.

        Returns:
            List of process dicts with at least "name" and "pid" keys.
        """
        return []


class HostnameMatcher:
    """Wraps discovery HostnameMatcher for reuse in traffic capture.

    Provides a simplified interface for checking whether a hostname
    belongs to a known AI provider.
    """

    def __init__(self) -> None:
        from anonreq.discovery.hostname_matcher import HostnameMatcher as _HostnameMatcher
        from anonreq.discovery.hostname_signatures import AI_SIGNATURES

        self._matcher = _HostnameMatcher(signatures=AI_SIGNATURES)

    def match(self, hostname: str) -> str | None:
        """Check if a hostname belongs to a known AI provider.

        Args:
            hostname: Hostname to check.

        Returns:
            Provider name string if matched, None otherwise.
        """
        result = self._matcher.match(hostname)
        if result is not None:
            return result.provider
        return None
