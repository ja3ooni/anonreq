"""eDiscovery export service.

Provides:
- ``eDiscoveryService``: Search and export records from lineage, DSAR,
  and retention services in JSON and CSV formats.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any

from anonreq.services.dsar import DSARService
from anonreq.services.lineage import LineageService
from anonreq.services.retention import RetentionService


class eDiscoveryService:
    """eDiscovery search and export across compliance data sources.

    Queries lineage records, DSAR requests, and retention policies
    for a given tenant and exports results as JSON or CSV.
    """

    def __init__(
        self,
        lineage_service: LineageService,
        dsar_service: DSARService,
        retention_service: RetentionService,
    ) -> None:
        self._lineage = lineage_service
        self._dsar = dsar_service
        self._retention = retention_service

    async def search(
        self,
        tenant_id: str,
        record_types: list[str] | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        results: dict[str, list[dict[str, Any]]] = {}
        types = record_types or ["lineage", "dsar", "retention"]

        if "lineage" in types:
            records = await self._lineage.list_records(tenant_id)
            results["lineage"] = [
                r.model_dump(mode="json") for r in records
                if self._matches_date(r.timestamp_request_received, date_from, date_to)
            ]

        if "dsar" in types:
            requests = await self._dsar.list_requests(tenant_id)
            results["dsar"] = [
                r.model_dump(mode="json") for r in requests
            ]

        if "retention" in types:
            policies = await self._retention.list_policies()
            results["retention"] = [
                p.model_dump(mode="json") for p in policies
            ]

        return results

    async def export_json(
        self,
        tenant_id: str,
        record_types: list[str] | None = None,
    ) -> str:
        results = await self.search(tenant_id, record_types)
        return json.dumps(results, indent=2, default=str)

    async def export_csv(
        self,
        tenant_id: str,
        record_types: list[str] | None = None,
    ) -> str:
        results = await self.search(tenant_id, record_types)
        types = record_types or ["lineage", "dsar", "retention"]

        output = io.StringIO()
        writer = csv.writer(output)

        if "lineage" in types and results.get("lineage"):
            lineage = results["lineage"]
            if lineage:
                writer.writerow(lineage[0].keys())
                for row in lineage:
                    writer.writerow(row.values())

        if "dsar" in types and results.get("dsar"):
            dsar = results["dsar"]
            if dsar:
                if output.tell() > 0:
                    output.write("\n")
                writer.writerow(dsar[0].keys())
                for row in dsar:
                    writer.writerow(row.values())

        return output.getvalue()

    @staticmethod
    def _matches_date(
        dt: datetime | str,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> bool:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        if date_from and dt < date_from:
            return False
        if date_to and dt > date_to:
            return False
        return True
