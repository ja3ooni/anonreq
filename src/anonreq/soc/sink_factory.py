"""Factory for instantiating SIEM sinks from ``SinkDefinition`` config.

Maps sink type strings to their corresponding Python classes and
handles construction from resolved configuration dictionaries.

Usage::

    from anonreq.soc.sink_config import SinkConfigLoader
    from anonreq.soc.sink_factory import build_sinks

    loader = SinkConfigLoader("config/soc-sinks.yaml")
    defs = loader.load()
    router, health_monitor = build_sinks(defs)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, cast

from anonreq.soc.buffer import SinkBuffer
from anonreq.soc.health import SinkHealthMonitor
from anonreq.soc.router import SinkRouter
from anonreq.soc.sink_config import SinkDefinition
from anonreq.soc.sinks import SinkBase

logger = logging.getLogger("anonreq.soc.sink_factory")


def _build_splunk_hec(config: dict[str, Any], name: str) -> SinkBase:
    from anonreq.soc.sinks.splunk_hec import SplunkHECSink

    return SplunkHECSink(
        name=name,
        endpoint=config["endpoint"],
        token=config["token"],
        tls_verify=config.get("tls_verify", True),
        timeout=config.get("timeout", 30),
    )


def _build_qradar_cef(config: dict[str, Any], name: str) -> SinkBase:
    from anonreq.soc.sinks.qradar_cef import QRadarCEFSink

    return QRadarCEFSink(
        name=name,
        host=config["host"],
        port=config.get("port", 514),
        use_tcp=config.get("use_tcp", True),
        source_host=config.get("source_host", "anonreq"),
    )


def _build_sentinel_dcr(config: dict[str, Any], name: str) -> SinkBase:
    from anonreq.soc.sinks.sentinel_dcr import SentinelDCRSink

    return SentinelDCRSink(
        name=name,
        tenant_id=config["tenant_id"],
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        dcr_endpoint=config["dcr_endpoint"],
        dcr_immutable_id=config["dcr_immutable_id"],
        stream_name=config["stream_name"],
        tls_verify=config.get("tls_verify", True),
        timeout=config.get("timeout", 30),
    )


def _build_elastic_bulk(config: dict[str, Any], name: str) -> SinkBase:
    from anonreq.soc.sinks.elastic_bulk import ElasticBulkSink

    return ElasticBulkSink(
        name=name,
        endpoint=config["endpoint"],
        api_key=config["api_key"],
        index_pattern=config.get("index_pattern", "anonreq-ai-security-%Y.%m.%d"),
        tls_verify=config.get("tls_verify", True),
        timeout=config.get("timeout", 30),
    )


def _build_datadog_logs(config: dict[str, Any], name: str) -> SinkBase:
    from anonreq.soc.sinks.datadog_logs import DatadogLogsSink

    return DatadogLogsSink(
        name=name,
        api_key=config["api_key"],
        site=config.get("site", "datadoghq.com"),
        source_tag=config.get("source_tag", "anonreq"),
        tls_verify=config.get("tls_verify", True),
        timeout=config.get("timeout", 30),
    )


def _build_webhook(config: dict[str, Any], name: str) -> SinkBase:
    from anonreq.soc.sinks.webhook import WebhookSink

    return WebhookSink(
        name=name,
        url=config["url"],
        method=config.get("method", "POST"),
        headers=config.get("headers"),
        payload_template=config.get("payload_template"),
        content_type=config.get("content_type", "application/json"),
        timeout=config.get("timeout", 30),
        tls_verify=config.get("tls_verify", True),
    )


_BUILDERS: dict[str, Callable[[dict[str, Any], str], SinkBase]] = {
    "splunk_hec": _build_splunk_hec,
    "qradar_cef": _build_qradar_cef,
    "sentinel_dcr": _build_sentinel_dcr,
    "elastic_bulk": _build_elastic_bulk,
    "datadog_logs": _build_datadog_logs,
    "webhook": _build_webhook,
}


def instantiate_sink(definition: SinkDefinition) -> SinkBase:
    """Create a single sink instance from its definition.

    Args:
        definition: A validated ``SinkDefinition`` with resolved secrets.

    Returns:
        A ``SinkBase``-compatible sink instance.

    Raises:
        ValueError: If the sink type is unknown.
    """
    builder = _BUILDERS.get(definition.type)
    if builder is None:
        raise ValueError(
            f"Unknown sink type '{definition.type}' for sink '{definition.name}'"
        )
    sink = builder(definition.config, definition.name)
    # Set enabled flag (sink constructors default to True)
    sink.enabled = definition.enabled
    return sink


def build_sinks(
    definitions: list[SinkDefinition],
    health_interval: int = 60,
) -> tuple[SinkRouter, Any]:
    """Build a ``SinkRouter`` and ``SinkHealthMonitor`` from sink definitions.

    Each enabled sink is:
    1. Instantiated via its factory builder.
    2. Optionally wrapped in ``SinkBuffer`` if ``buffer_maxsize > 0``.
    3. Registered with the ``SinkRouter``.

    Args:
        definitions: List of ``SinkDefinition`` instances with resolved secrets.
        health_interval: Health check probe interval in seconds.

    Returns:
        Tuple of ``(SinkRouter, SinkHealthMonitor)``.
    """
    router = SinkRouter()

    for definition in definitions:
        sink: SinkBase | SinkBuffer = instantiate_sink(definition)

        # Wrap in buffer if maxsize > 0
        if definition.buffer_maxsize > 0:
            sink = SinkBuffer(sink, maxsize=definition.buffer_maxsize)
            logger.info(
                "Wrapped sink '%s' in SinkBuffer (maxsize=%d)",
                definition.name,
                definition.buffer_maxsize,
            )

        router.register(cast(SinkBase, sink))
        logger.info(
            "Sink '%s' (%s) %s",
            definition.name,
            definition.type,
            "enabled" if definition.enabled else "disabled",
        )

    monitor = SinkHealthMonitor(router=router, interval=health_interval)

    return router, monitor
