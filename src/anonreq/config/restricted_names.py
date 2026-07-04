"""Hot-reloadable tenant restricted-names list for MNPI detection.

Phase 15 Financial Services Compliance, D-002, D-003.

Provides ``RestrictedNamesManager`` that:
- Loads tenant-specific restricted names from a YAML configuration file
- Supports case-insensitive substring matching
- Hot-reloads on file modification (mtime-based polling)
- Is thread-safe via ``threading.Lock``

Threat mitigation (T-15-01-03):
- Uses ``yaml.safe_load()`` to prevent code injection
- Hot-reload uses file mtime check (not arbitrary exec)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class RestrictedNamesManager:
    """Manages tenant-specific restricted names with hot-reload support.

    Loads a YAML file of the form::

        tenants:
          tenant-id:
            restricted_names:
              - "Sensitive Project Name"
              - "Secret Deal"

    Provides case-insensitive matching and thread-safe hot-reload
    triggered by file modification time (mtime) changes.

    Args:
        config_path: Path to the restricted names YAML file.
            Defaults to ``config/restricted_names.yaml``.
    """

    def __init__(self, config_path: str = "config/restricted_names.yaml") -> None:
        self._config_path: str = config_path
        self._lock = threading.Lock()
        self._data: dict[str, list[str]] = {}
        self._last_mtime: float = 0.0
        self._load_file()

    @property
    def config_path(self) -> str:
        """Path to the restricted names YAML configuration file."""
        return self._config_path

    def _load_file(self) -> None:
        """Read the YAML file and populate ``_data``.

        Uses ``yaml.safe_load()`` per T-15-01-03. If the file does not
        exist or is corrupted, ``_data`` remains an empty dict and a
        warning is logged.
        """
        try:
            if not os.path.isfile(self._config_path):
                self._data = {}
                return

            raw: dict[str, Any] | None = None
            with open(self._config_path) as f:
                raw = yaml.safe_load(f)

            if raw is None or not isinstance(raw, dict):
                self._data = {}
                return

            tenants = raw.get("tenants", {})
            if not isinstance(tenants, dict):
                self._data = {}
                return

            result: dict[str, list[str]] = {}
            for tenant_id, tenant_cfg in tenants.items():
                if not isinstance(tenant_cfg, dict):
                    continue
                names = tenant_cfg.get("restricted_names", [])
                if isinstance(names, list):
                    result[str(tenant_id)] = [str(n) for n in names]
                else:
                    result[str(tenant_id)] = []
            self._data = result

            try:
                self._last_mtime = os.path.getmtime(self._config_path)
            except OSError:
                self._last_mtime = time.time()

        except yaml.YAMLError:
            logger.warning(
                "Restricted names YAML parse error",
                extra={"config_path": self._config_path},
            )
            self._data = {}
        except OSError:
            logger.warning(
                "Restricted names file read error",
                extra={"config_path": self._config_path},
            )
            self._data = {}

    def load(self) -> dict[str, list[str]]:
        """Return the current restricted-names data.

        Returns:
            A dict mapping ``tenant_id`` to a list of restricted name
            strings. Returns an empty dict if the config could not be
            loaded.
        """
        with self._lock:
            return dict(self._data)

    def get_names(self, tenant_id: str) -> list[str]:
        """Return restricted names for a given tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            A list of restricted name strings (empty list if tenant has
            no restricted names or does not exist).
        """
        with self._lock:
            return list(self._data.get(tenant_id, []))

    def check_name(self, tenant_id: str, text: str) -> bool:
        """Check if *text* matches any restricted name for the tenant.

        Matching is case-insensitive and checks if the restricted name
        contains the query text as a case-insensitive substring (or
        vice versa — the query text is checked as a substring of each
        restricted name).

        Args:
            tenant_id: The tenant identifier.
            text: The text to check (e.g., from a request payload).

        Returns:
            ``True`` if a match is found, ``False`` otherwise.
        """
        if not text or not text.strip():
            return False
        search = text.strip().lower()
        if len(search) < 3:
            return False  # Too short to be meaningful

        with self._lock:
            names = self._data.get(tenant_id, [])
            for name in names:
                if not name:
                    continue
                # Case-insensitive substring match (both directions)
                name_lower = name.lower()
                if search in name_lower or name_lower in search:
                    return True
        return False

    def reload(self) -> bool:
        """Reload the YAML file if it has changed since the last load.

        Checks the file's modification time (mtime) to detect changes.
        If the file does not exist or cannot be read, the data is left
        unchanged and ``False`` is returned.

        Returns:
            ``True`` if the file was reloaded (data changed), ``False``
            if the file has not changed or could not be read.
        """
        try:
            current_mtime = os.path.getmtime(self._config_path)
        except OSError:
            return False

        if current_mtime <= self._last_mtime:
            return False

        # Acquire lock and reload
        with self._lock:
            # Double-check mtime after acquiring lock
            try:
                actual_mtime = os.path.getmtime(self._config_path)
            except OSError:
                return False

            if actual_mtime <= self._last_mtime:
                return False

            old_data = dict(self._data)
            self._load_file()
            return self._data != old_data


def load_restricted_names(
    config_path: str = "config/restricted_names.yaml",
) -> RestrictedNamesManager:
    """Factory function: create a ``RestrictedNamesManager`` instance.

    Args:
        config_path: Path to the restricted names YAML file.

    Returns:
        A new ``RestrictedNamesManager``.
    """
    return RestrictedNamesManager(config_path=config_path)
