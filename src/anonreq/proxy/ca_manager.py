"""CA certificate manager with dual-path management and hot-reload.

Supports:
- API-based upload (``upload_ca_cert``) that validates the cert+key pair
  and writes PEM files to a configurable directory.
- Filesystem-based file watch (via ``watchdog``) that detects new or
  modified CA certificates and triggers a hot-reload.
- In-memory metadata store keyed by certificate serial number.
"""

from __future__ import annotations

import asyncio
import logging
import os
import stat
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from anonreq.exceptions import AnonReqError

try:
    from watchdog.events import FileModifiedEvent, FileCreatedEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    Observer = None
    FileSystemEventHandler = object

logger = logging.getLogger(__name__)


class CAManagerError(AnonReqError):
    """Raised when a CA management operation fails."""

    def __init__(self, message: str = "CA management error") -> None:
        super().__init__(
            message=message,
            error_type="ca_manager_error",
            status_code=500,
            code="ca_manager_error",
        )


def _generate_self_signed_ca(cn: str = "AnonReq CA") -> tuple[Any, Any, bytes, bytes]:
    """Generate a self-signed CA certificate and key for testing.

    Returns:
        A tuple of (cert, private_key, cert_pem_bytes, key_pem_bytes).
    """
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
    ])
    now = datetime.now(timezone.utc)
    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now.replace(year=now.year + 10))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
    )
    cert = cert_builder.sign(key, hashes.SHA256())
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return cert, key, cert_pem, key_pem


def _extract_cert_meta(
    cert: x509.Certificate,
    label: str = "",
    uploaded_at: str | None = None,
) -> dict[str, Any]:
    """Extract metadata dict from an X.509 certificate."""
    try:
        not_after = cert.not_valid_after_utc.isoformat()
    except AttributeError:
        not_after = cert.not_valid_after.isoformat()
    try:
        not_before = cert.not_valid_before_utc.isoformat()
    except AttributeError:
        not_before = cert.not_valid_before.isoformat()
    return {
        "serial": cert.serial_number,
        "subject": cert.subject.rfc4514_string(),
        "issuer": cert.issuer.rfc4514_string(),
        "not_before": not_before,
        "not_after": not_after,
        "label": label,
        "uploaded_at": uploaded_at or datetime.now(timezone.utc).isoformat(),
    }


class _CAFileHandler(FileSystemEventHandler):
    """Watchdog event handler that triggers CAManager reload on file changes."""

    def __init__(self, manager: "CAManager", debounce: float = 2.0) -> None:
        self.manager = manager
        self.debounce = debounce
        self._last_trigger: float = 0.0

    def on_modified(self, event) -> None:
        if not event.is_directory and event.src_path.endswith((".pem", ".key")):
            self._debounced_reload(event.src_path)

    def on_created(self, event) -> None:
        if not event.is_directory and event.src_path.endswith((".pem", ".key")):
            self._debounced_reload(event.src_path)

    def _debounced_reload(self, path: str) -> None:
        now = time.monotonic()
        if now - self._last_trigger < self.debounce:
            return
        self._last_trigger = now
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.manager.reload()))
        except RuntimeError:
            pass


class CAManager:
    """Manages CA certificates with dual-path upload and file-watch hot-reload.

    Args:
        ca_dir: Directory path for storing CA PEM files.
        debounce: Debounce interval in seconds for file-watch events.
    """

    def __init__(
        self,
        ca_dir: str = "/etc/anonreq/ca",
        debounce: float = 2.0,
    ) -> None:
        self._ca_dir = Path(ca_dir)
        self._ca_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._certs: dict[int, dict[str, Any]] = {}
        self._active_serial: int | None = None

        self._observer: Observer | None = None
        self._start_file_watcher(debounce)

    # ------------------------------------------------------------------
    # File watcher
    # ------------------------------------------------------------------

    def _start_file_watcher(self, debounce: float) -> None:
        """Start watchdog observer on the CA directory (daemon thread)."""
        if Observer is None:
            logger.warning("watchdog not installed — file-watch hot-reload disabled")
            return
        handler = _CAFileHandler(self, debounce=debounce)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._ca_dir), recursive=False)
        self._observer.daemon = True
        self._observer.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload_ca_cert(
        self,
        cert_pem: str,
        key_pem: str,
        label: str = "",
    ) -> dict[str, Any]:
        """Validate and store a CA certificate via the API path.

        Args:
            cert_pem: PEM-encoded certificate string.
            key_pem: PEM-encoded private key string.
            label: Optional human-readable label.

        Returns:
            Metadata dict with ``serial``, ``subject``, ``not_after``.

        Raises:
            CAManagerError: If the cert+key pair is invalid or file write fails.
        """
        try:
            cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
            key = serialization.load_pem_private_key(key_pem.encode("utf-8"), password=None)
        except Exception as exc:
            raise CAManagerError(f"Invalid certificate or key: {exc}") from exc

        if not self._cert_matches_key(cert, key):
            raise CAManagerError("Certificate and private key do not match")

        serial_str = str(cert.serial_number)
        cert_path = self._ca_dir / f"{serial_str}.pem"
        key_path = self._ca_dir / f"{serial_str}.key"

        try:
            cert_path.write_text(cert_pem)
            os.chmod(cert_path, stat.S_IRUSR | stat.S_IWUSR)
            key_path.write_text(key_pem)
            os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError as exc:
            raise CAManagerError(f"Failed to write CA files: {exc}") from exc

        meta = _extract_cert_meta(cert, label=label)
        with self._lock:
            self._certs[cert.serial_number] = meta
            self._active_serial = cert.serial_number

        return {
            "serial": cert.serial_number,
            "subject": meta["subject"],
            "not_after": meta["not_after"],
        }

    async def get_ca_info(self) -> dict[str, Any] | None:
        """Return metadata for the currently active CA certificate.

        Returns:
            Metadata dict or ``None`` if no CA is loaded.
        """
        with self._lock:
            if self._active_serial is None:
                return None
            return self._certs.get(self._active_serial)

    async def list_ca_certs(self) -> list[dict[str, Any]]:
        """Return all known CA certificates sorted by upload time descending.

        Returns:
            List of metadata dicts.
        """
        with self._lock:
            certs = list(self._certs.values())
        certs.sort(key=lambda c: c.get("uploaded_at", ""), reverse=True)
        return certs

    async def reload(
        self,
        cert_path: str | None = None,
        key_path: str | None = None,
    ) -> None:
        """Reload the CA certificate from a specific path or auto-discover.

        On failure the previous CA is preserved and ``CAManagerError`` is
        raised.

        Args:
            cert_path: Explicit certificate path (auto-discover if ``None``).
            key_path: Explicit key path (auto-discover if ``None``).

        Raises:
            CAManagerError: If loading or validation fails.
        """
        if cert_path and key_path:
            paths = [(Path(cert_path), Path(key_path))]
        else:
            paths = self._discover_ca_files()

        last_error: Exception | None = None
        for c_path, k_path in paths:
            try:
                cert_pem = c_path.read_bytes()
                key_pem = k_path.read_bytes()
                cert = x509.load_pem_x509_certificate(cert_pem)
                key = serialization.load_pem_private_key(key_pem, password=None)

                if not self._cert_matches_key(cert, key):
                    raise ValueError("Key does not match certificate")

                meta = _extract_cert_meta(cert)
                with self._lock:
                    self._certs[cert.serial_number] = meta
                    self._active_serial = cert.serial_number
                return
            except Exception as exc:
                last_error = exc
                continue

        raise CAManagerError(
            f"Failed to load CA certificate: {last_error or 'no valid cert found'}"
        ) from last_error

    async def close(self) -> None:
        """Shut down the file watcher and release resources."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _discover_ca_files(self) -> list[tuple[Path, Path]]:
        """Auto-discover latest cert+key pairs in the CA directory.

        Returns sorted list of (cert_path, key_path) pairs, newest first.
        """
        pairs: list[tuple[Path, Path]] = []
        for c_path in sorted(self._ca_dir.glob("*.pem"), reverse=True):
            k_path = c_path.with_suffix(".key")
            if k_path.exists():
                pairs.append((c_path, k_path))
        return pairs

    @staticmethod
    def _cert_matches_key(cert: x509.Certificate, key: Any) -> bool:
        """Check that a private key corresponds to the certificate's public key."""
        try:
            cert_pub = cert.public_key()
            if isinstance(key, rsa.RSAPrivateKey) and isinstance(cert_pub, rsa.RSAPublicKey):
                return (
                    key.public_key().public_numbers().n == cert_pub.public_numbers().n
                    and key.public_key().public_numbers().e == cert_pub.public_numbers().e
                )
            return True
        except Exception:
            return False
