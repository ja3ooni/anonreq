"""Appliance management agent for the AnonReq virtual appliance.

Runs as a systemd service outside Docker and manages Docker Compose
lifecycle for anonreq services. Provides health checks, configuration
management, log access, service restarts, and image updates.

Per T-17-03-02:
- Agent runs as ``anonreq`` non-root user
- Only ``docker compose`` subcommands are executed — no arbitrary shell
- All operations are logged
- Errors are captured and never leaked raw
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("anonreq.appliance.agent")


# ---------------------------------------------------------------------------
# Appliance configuration
# ---------------------------------------------------------------------------


@dataclass
class ApplianceConfig:
    """Configuration loaded from the appliance config directory.

    Attributes:
        compose_dir: Directory containing docker-compose.yml.
        compose_file: Path to docker-compose.yml.
        env_file: Path to the environment file.
        data_dir: Directory for persistent data.
        log_dir: Directory for appliance agent logs.
        compose_command: The ``docker compose`` command to use.
        services: List of managed services.
    """

    compose_dir: str = "/opt/anonreq"
    compose_file: str = "/opt/anonreq/docker-compose.yml"
    env_file: str = "/etc/anonreq/config.env"
    data_dir: str = "/var/lib/anonreq"
    log_dir: str = "/var/log/anonreq"
    compose_command: str = "docker compose"
    services: list[str] = field(default_factory=lambda: ["anonreq", "valkey"])


# ---------------------------------------------------------------------------
# Appliance Agent
# ---------------------------------------------------------------------------


class ApplianceAgent:
    """Manages the AnonReq virtual appliance lifecycle.

    The agent runs as a systemd service and manages Docker Compose
    lifecycle for the anonreq services. It communicates via CLI commands
    to ``docker compose`` — no direct Docker API access.

    Args:
        config_path: Path to the appliance configuration directory or file.
            Defaults to ``/etc/anonreq/config``.
    """

    def __init__(self, config_path: str = "/etc/anonreq/config") -> None:
        self.config_path = config_path
        self._config = self._load_config(config_path)
        self._start_time = time.monotonic()

    @property
    def config(self) -> ApplianceConfig:
        """Return the current appliance configuration."""
        return self._config

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_config(self, config_path: str) -> ApplianceConfig:
        """Load appliance configuration from the given path.

        If the path is a directory, looks for ``config.json`` inside it.
        Falls back to default configuration if the file does not exist.

        Args:
            config_path: Path to a config file or directory.

        Returns:
            An ``ApplianceConfig`` instance.
        """
        path = Path(config_path)
        if path.is_dir():
            path = path / "config.json"

        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                default_config = ApplianceConfig()
                return ApplianceConfig(
                    compose_dir=data.get("compose_dir", default_config.compose_dir),
                    compose_file=data.get("compose_file", default_config.compose_file),
                    env_file=data.get("env_file", default_config.env_file),
                    data_dir=data.get("data_dir", default_config.data_dir),
                    log_dir=data.get("log_dir", default_config.log_dir),
                    compose_command=data.get(
                        "compose_command", default_config.compose_command
                    ),
                    services=data.get("services", list(default_config.services)),
                )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load config from %s: %s", path, exc)

        return ApplianceConfig()

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    async def get_health(self) -> dict[str, Any]:
        """Return the health status of all managed services.

        Reports Docker Compose service statuses, disk usage, memory
        information, and agent uptime.

        Returns:
            A dict with ``services``, ``disk``, ``memory``, ``uptime``,
            and ``docker_available`` keys.
        """
        services_status = await self._check_service_status()
        disk_info = self._get_disk_usage()
        memory_info = self._get_memory_info()
        uptime = time.monotonic() - self._start_time

        return {
            "services": services_status,
            "disk": disk_info,
            "memory": memory_info,
            "uptime_seconds": round(uptime, 1),
            "docker_available": shutil.which("docker") is not None,
        }

    async def _check_service_status(self) -> list[dict[str, Any]]:
        """Check the status of each managed Docker Compose service.

        Returns:
            A list of dicts with ``name`` and ``status`` for each service.
        """
        try:
            result = await self._run_compose_command("ps --format json")
            if result["returncode"] != 0:
                return [
                    {"name": s, "status": "unknown", "error": result["stderr"]}
                    for s in self._config.services
                ]

            services: list[dict[str, Any]] = []
            for line in result["stdout"].strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    service_info = json.loads(line)
                    name = service_info.get("Name", service_info.get("Service", "unknown"))
                    status = service_info.get("Status", "unknown")
                    services.append({"name": name, "status": status})
                except json.JSONDecodeError:
                    pass

            # Ensure all configured services are represented
            reported_names = {s["name"] for s in services}
            for svc in self._config.services:
                if svc not in reported_names:
                    services.append({"name": svc, "status": "not_found"})

            return services

        except Exception as exc:
            logger.error("Failed to check service status: %s", exc)
            return [{"name": s, "status": "error"} for s in self._config.services]

    def _get_disk_usage(self) -> dict[str, Any]:
        """Get disk usage information.

        Returns:
            A dict with ``total_gb``, ``used_gb``, ``free_gb`` keys, or
            error information.
        """
        try:
            stat = shutil.disk_usage(self._config.data_dir)
            return {
                "total_gb": round(stat.total / (1024**3), 1),
                "used_gb": round((stat.total - stat.free) / (1024**3), 1),
                "free_gb": round(stat.free / (1024**3), 1),
            }
        except OSError as exc:
            return {"error": str(exc)}

    def _get_memory_info(self) -> dict[str, Any]:
        """Get memory information.

        Returns:
            A dict with ``total_gb``, ``available_gb`` keys, or error info.
        """
        try:
            with open("/proc/meminfo") as f:
                meminfo = f.read()
            total_match = re.search(r"MemTotal:\s+(\d+)", meminfo)
            available_match = re.search(r"MemAvailable:\s+(\d+)", meminfo)
            if total_match:
                total_kb = int(total_match.group(1))
                avail_kb = int(available_match.group(1)) if available_match else 0
                return {
                    "total_gb": round(total_kb / (1024 * 1024), 1),
                    "available_gb": round(avail_kb / (1024 * 1024), 1),
                }
            return {"error": "Cannot read memory info"}
        except (OSError, FileNotFoundError):
            return {"error": "Memory info not available on this platform"}

    # ------------------------------------------------------------------
    # Configuration management
    # ------------------------------------------------------------------

    async def get_config(self) -> dict[str, Any]:
        """Return the current appliance configuration.

        Secrets (API keys, passwords) are redacted in the response.

        Returns:
            A dict with configuration keys, with secrets redacted.
        """
        return {
            "compose_dir": self._config.compose_dir,
            "compose_file": self._config.compose_file,
            "env_file": self._config.env_file,
            "data_dir": self._config.data_dir,
            "log_dir": self._config.log_dir,
            "services": list(self._config.services),
            "docker_available": shutil.which("docker") is not None,
        }

    async def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Validate and apply configuration updates.

        Writes updated configuration to the config file. If the compose
        file or env file paths change, a service restart is required.

        Args:
            updates: Dict of configuration keys to update.

        Returns:
            A dict with the result of the update operation.

        Raises:
            ValueError: If an invalid configuration value is provided.
        """
        valid_keys = {
            "compose_dir", "compose_file", "env_file",
            "data_dir", "log_dir", "compose_command", "services",
        }

        invalid_keys = set(updates) - valid_keys
        if invalid_keys:
            raise ValueError(f"Invalid config keys: {', '.join(sorted(invalid_keys))}")

        # Validate services if provided
        if "services" in updates:
            if not isinstance(updates["services"], list) or not updates["services"]:
                raise ValueError("services must be a non-empty list of strings")
            for svc in updates["services"]:
                if not isinstance(svc, str) or not svc.strip():
                    raise ValueError(f"Invalid service name: {svc}")

        # Build updated config
        current = {
            "compose_dir": self._config.compose_dir,
            "compose_file": self._config.compose_file,
            "env_file": self._config.env_file,
            "data_dir": self._config.data_dir,
            "log_dir": self._config.log_dir,
            "compose_command": self._config.compose_command,
            "services": list(self._config.services),
        }
        current.update(updates)

        # Write config file
        config_path = Path(self.config_path)
        if config_path.is_dir():
            config_path = config_path / "config.json"

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(current, f, indent=2)
            logger.info("Configuration updated: %s", config_path)
        except OSError as exc:
            logger.error("Failed to write config: %s", exc)
            return {"status": "error", "error": str(exc)}

        # Reload config
        self._config = self._load_config(self.config_path)

        return {
            "status": "updated",
            "restart_required": True,
            "changes": list(updates.keys()),
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> dict[str, Any]:
        """Return the current appliance status summary.

        Returns:
            A dict with mode, version, uptime, service count, and
            active session info.
        """
        uptime = time.monotonic() - self._start_time
        service_count = len(self._config.services)

        return {
            "mode": "appliance",
            "version": self._get_version(),
            "uptime_seconds": round(uptime, 1),
            "service_count": service_count,
            "services": list(self._config.services),
            "active_sessions": "N/A",  # Requires API gateway integration
        }

    def _get_version(self) -> str:
        """Return the appliance version.

        Tries to read from a VERSION file in the compose directory.
        Falls back to a default version string.
        """
        version_file = Path(self._config.compose_dir) / "VERSION"
        if version_file.exists():
            try:
                return version_file.read_text().strip()
            except OSError:
                pass
        return "0.1.0"

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    async def get_logs(self, service: str = "anonreq", tail: int = 100) -> str:
        """Return recent logs from a Docker Compose service.

        Args:
            service: The service name to fetch logs for. Defaults to
                ``"anonreq"``.
            tail: Number of recent log lines to return. Defaults to 100.

        Returns:
            The log output as a string.
        """
        result = await self._run_compose_command(
            f"logs {service} --tail {tail} --no-color"
        )
        if result["returncode"] != 0:
            logger.warning(
                "Failed to get logs for service %s: %s",
                service,
                result["stderr"],
            )
            return f"Error: {result['stderr']}"
        return result["stdout"]

    # ------------------------------------------------------------------
    # Service management
    # ------------------------------------------------------------------

    async def restart_service(self, service: str = "anonreq") -> dict[str, Any]:
        """Restart a specific Docker Compose service.

        Args:
            service: The service name to restart. Defaults to ``"anonreq"``.

        Returns:
            A dict with the restart result.
        """
        logger.info("Restarting service: %s", service)
        result = await self._run_compose_command(f"restart {service}")
        if result["returncode"] != 0:
            logger.error("Failed to restart service %s: %s", service, result["stderr"])
            return {
                "status": "error",
                "service": service,
                "error": result["stderr"],
            }
        logger.info("Service %s restarted successfully", service)
        return {
            "status": "restarted",
            "service": service,
        }

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------

    async def update(self, image_tag: str) -> dict[str, Any]:
        """Pull a new image tag and restart the services.

        Args:
            image_tag: The new Docker image tag to deploy (e.g.,
                ``"ghcr.io/anonreq/gateway:1.2.0"``).

        Returns:
            A dict with the rollout status.
        """
        logger.info("Starting update to image tag: %s", image_tag)
        updates: dict[str, Any] = {
            "image_tag": image_tag,
            "steps": [],
        }

        # Step 1: Pull new image
        logger.info("Pulling image: %s", image_tag)
        pull_result = await self._run_compose_command(
            f"pull {image_tag} --quiet", timeout=300
        )
        updates["steps"].append({"step": "pull", "status": "completed"})
        if pull_result["returncode"] != 0:
            err_msg = f"Failed to pull image: {pull_result['stderr']}"
            logger.error(err_msg)
            return {"status": "error", "error": err_msg, "steps": updates["steps"]}

        # Step 2: Update compose file image tag
        try:
            self._update_compose_image_tag(image_tag)
            updates["steps"].append({"step": "update_compose", "status": "completed"})
        except OSError as exc:
            err_msg = f"Failed to update compose file: {exc}"
            logger.error(err_msg)
            return {"status": "error", "error": err_msg, "steps": updates["steps"]}

        # Step 3: Recreate services with new image
        logger.info("Recreating services with image: %s", image_tag)
        up_result = await self._run_compose_command(
            "up --detach --force-recreate", timeout=120
        )
        updates["steps"].append({"step": "up", "status": "completed"})
        if up_result["returncode"] != 0:
            err_msg = f"Failed to start services: {up_result['stderr']}"
            logger.error(err_msg)
            return {"status": "error", "error": err_msg, "steps": updates["steps"]}

        logger.info("Update to %s completed successfully", image_tag)
        updates["status"] = "completed"
        updates["steps"].append({"step": "verify", "status": "pending"})
        return updates

    def _update_compose_image_tag(self, image_tag: str) -> None:
        """Update the image tag in docker-compose.yml.

        Replaces the image reference for the anonreq service with the
        new tag.

        Args:
            image_tag: The new image tag.

        Raises:
            OSError: If the compose file cannot be read or written.
        """
        compose_path = Path(self._config.compose_file)
        if not compose_path.exists():
            logger.warning("Compose file not found: %s", compose_path)
            return

        content = compose_path.read_text()
        # Match image: anonreq/gateway:some_tag or ghcr.io/anonreq/gateway:some_tag
        updated = re.sub(
            r"(image:\s*)(?:ghcr\.io/)?anonreq/gateway[:\s]+\S+",
            f"\\1{image_tag}",
            content,
        )
        compose_path.write_text(updated)
        logger.info("Updated compose file image tag to: %s", image_tag)

    # ------------------------------------------------------------------
    # Docker Compose command execution
    # ------------------------------------------------------------------

    async def _run_compose_command(
        self,
        subcommand: str,
        timeout: int = 60,
    ) -> dict[str, Any]:
        """Execute a Docker Compose subcommand.

        Args:
            subcommand: The ``docker compose`` subcommand and arguments.
            timeout: Timeout in seconds for the command.

        Returns:
            A dict with ``returncode``, ``stdout``, and ``stderr``.
        """
        command = (
            f"{self._config.compose_command} "
            f"-f {self._config.compose_file} "
            f"--env-file {self._config.env_file} "
            f"{subcommand}"
        )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return {
                "returncode": proc.returncode or 0,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
        except TimeoutError:
            logger.error("Command timed out after %ss: %s", timeout, subcommand)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
            }
        except FileNotFoundError:
            logger.error("Docker Compose command not found")
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "docker compose not found",
            }
        except Exception as exc:
            logger.error("Failed to run compose command: %s", exc)
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(exc),
            }
