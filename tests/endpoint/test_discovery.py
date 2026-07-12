"""Tests for AI application discovery on endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestAppDiscoveryKnownApps:
    """Test detection of known AI desktop applications."""

    def test_known_apps_list_contains_expected(self):
        """Known apps list contains expected AI applications."""
        from anonreq.endpoint.discovery import KNOWN_AI_APPS

        assert len(KNOWN_AI_APPS) >= 4
        names = {app["name"] for app in KNOWN_AI_APPS}
        assert "Cursor" in names
        assert "Claude Desktop" in names
        assert "ChatGPT Desktop" in names

    def test_discover_apps_returns_list_of_apps(self):
        """discover_apps returns a list of discovered AI app dicts."""
        from anonreq.endpoint.discovery import AppDiscovery

        discovery = AppDiscovery()
        apps = discovery.discover_apps()
        assert isinstance(apps, list)

    @patch("anonreq.endpoint.discovery.AppDiscovery._enumerate_processes")
    def test_detects_cursor(self, mock_enum):
        """Cursor process is identified as Cursor AI app."""
        from anonreq.endpoint.discovery import AppDiscovery

        mock_enum.return_value = [
            {"name": "Cursor", "pid": 1234, "path": "/Applications/Cursor.app"},
        ]
        discovery = AppDiscovery()
        apps = discovery.discover_apps()

        assert len(apps) == 1
        assert apps[0]["app_name"] == "Cursor"
        assert apps[0]["pid"] == 1234

    @patch("anonreq.endpoint.discovery.AppDiscovery._enumerate_processes")
    def test_detects_claude_desktop(self, mock_enum):
        """Claude Desktop process is identified correctly."""
        from anonreq.endpoint.discovery import AppDiscovery

        mock_enum.return_value = [
            {"name": "Claude", "pid": 5678, "path": "/Applications/Claude.app"},
        ]
        discovery = AppDiscovery()
        apps = discovery.discover_apps()

        assert len(apps) == 1
        assert apps[0]["app_name"] == "Claude Desktop"
        assert apps[0]["pid"] == 5678

    @patch("anonreq.endpoint.discovery.AppDiscovery._enumerate_processes")
    def test_detects_chatgpt_desktop(self, mock_enum):
        """ChatGPT Desktop process is identified correctly."""
        from anonreq.endpoint.discovery import AppDiscovery

        mock_enum.return_value = [
            {"name": "ChatGPT", "pid": 9012, "path": "/Applications/ChatGPT.app"},
        ]
        discovery = AppDiscovery()
        apps = discovery.discover_apps()

        assert len(apps) == 1
        assert apps[0]["app_name"] == "ChatGPT Desktop"
        assert apps[0]["pid"] == 9012

    @patch("anonreq.endpoint.discovery.AppDiscovery._enumerate_processes")
    def test_detects_vscode_copilot(self, mock_enum):
        """VS Code (with Copilot extension) is detected."""
        from anonreq.endpoint.discovery import AppDiscovery

        mock_enum.return_value = [
            {
                "name": "Code",
                "pid": 3456,
                "path": "/Applications/Visual Studio Code.app",
                "extensions": ["GitHub.copilot"],
            },
        ]
        discovery = AppDiscovery()
        apps = discovery.discover_apps()

        assert len(apps) == 1
        assert apps[0]["app_name"] == "VS Code (Copilot)"
        assert apps[0]["pid"] == 3456


class TestAppDiscoveryUnknown:
    """Test that non-AI processes are not detected."""

    @patch("anonreq.endpoint.discovery.AppDiscovery._enumerate_processes")
    def test_unknown_process_ignored(self, mock_enum):
        """Non-AI processes are not returned as discovered apps."""
        from anonreq.endpoint.discovery import AppDiscovery

        mock_enum.return_value = [
            {"name": "Terminal", "pid": 7890, "path": "/System/Applications/Utilities/Terminal.app"},  # noqa: E501
            {"name": "Finder", "pid": 1111, "path": "/System/Library/CoreServices/Finder.app"},
        ]
        discovery = AppDiscovery()
        apps = discovery.discover_apps()

        assert len(apps) == 0

    @patch("anonreq.endpoint.discovery.AppDiscovery._enumerate_processes")
    def test_vscode_without_copilot_ignored(self, mock_enum):
        """VS Code without Copilot extension is not detected."""
        from anonreq.endpoint.discovery import AppDiscovery

        mock_enum.return_value = [
            {
                "name": "Code",
                "pid": 3456,
                "path": "/Applications/Visual Studio Code.app",
                "extensions": [],
            },
        ]
        discovery = AppDiscovery()
        apps = discovery.discover_apps()

        assert len(apps) == 0


class TestAppDiscoveryAudit:
    """Test audit event emission from discovery."""

    def test_emit_discovered_events(self):
        """Emit audit events for each discovered app."""
        from anonreq.endpoint.discovery import AppDiscovery

        audit_logger = MagicMock()
        discovery = AppDiscovery(audit_logger=audit_logger)

        with patch.object(discovery, "_enumerate_processes") as mock_enum:
            mock_enum.return_value = [
                {"name": "Cursor", "pid": 1234, "path": "/Applications/Cursor.app"},
            ]
            apps = discovery.discover_and_emit()

        assert len(apps) == 1
        audit_logger.info.assert_called_once()
        call_args = audit_logger.info.call_args
        assert call_args[0][0] == "ai_app_discovered"
        assert call_args[1]["app_name"] == "Cursor"
        assert call_args[1]["pid"] == 1234

    def test_no_audit_when_no_apps(self):
        """No audit event when no AI apps discovered."""
        from anonreq.endpoint.discovery import AppDiscovery

        audit_logger = MagicMock()
        discovery = AppDiscovery(audit_logger=audit_logger)

        with patch.object(discovery, "_enumerate_processes") as mock_enum:
            mock_enum.return_value = []
            apps = discovery.discover_and_emit()

        assert len(apps) == 0
        audit_logger.info.assert_not_called()

    def test_audit_no_raw_process_path(self):
        """Audit event must not contain raw process paths (PII concern)."""
        from anonreq.endpoint.discovery import AppDiscovery

        audit_logger = MagicMock()
        discovery = AppDiscovery(audit_logger=audit_logger)

        with patch.object(discovery, "_enumerate_processes") as mock_enum:
            mock_enum.return_value = [
                {"name": "Cursor", "pid": 1234, "path": "/Users/john/Applications/Cursor.app"},
            ]
            discovery.discover_and_emit()

        call_args = audit_logger.info.call_args
        event_fields = call_args[1]
        # Process path must NOT be in audit event
        assert "path" not in event_fields

    def test_app_discovery_event_schema(self):
        """Discovered app event follows expected schema."""
        from anonreq.endpoint.discovery import AppDiscovery

        discovery = AppDiscovery()
        with patch.object(discovery, "_enumerate_processes") as mock_enum:
            mock_enum.return_value = [
                {"name": "Cursor", "pid": 1234, "path": "/Applications/Cursor.app"},
            ]
            apps = discovery.discover_apps()

        app = apps[0]
        assert "app_name" in app
        assert "pid" in app
        assert "bundle_id" in app
        assert "version" in app
        assert "detected_at" in app
