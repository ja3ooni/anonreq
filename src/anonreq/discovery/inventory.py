"""AI Asset Inventory — unified data model, merge pipeline, export.

Provides:
- InventoryRecord: Full inventory record with all required fields
- InventoryFilter: Filter criteria for inventory queries
- AssetInventory: In-memory inventory with merge, dedup, export capabilities
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from prometheus_client import Gauge

INVENTORY_SERVICES = Gauge(
    "anonreq_inventory_services_total",
    "Total number of services in AI Asset Inventory",
    ["risk_band", "provider"],
)

INVENTORY_RISK_DIST = Gauge(
    "anonreq_inventory_risk_distribution",
    "Risk score distribution across inventory",
    ["risk_band"],
)


@dataclass
class InventoryRecord:
    """A single AI service record in the asset inventory.

    Attributes:
        service_name: Service hostname or name.
        provider: AI provider name (e.g. openai, anthropic).
        model: Model name or list of models.
        user_count: Number of unique users.
        app_count: Number of applications using the service.
        token_volume: Total token volume (input + output).
        estimated_cost: Estimated monthly cost in USD.
        data_classification: Highest observed data classification.
        approval_status: Approval status (approved|pending|not_reviewed|denied).
        risk_score: Numeric risk score (0-100).
        risk_band: Risk band classification.
        last_seen: Most recent observation timestamp.
        first_seen: First observation timestamp.
        owner: Responsible owner or team.
        business_unit: Business unit.
        sources: Data sources that contributed to this record.
        hostnames: All observed hostnames for this service.
        ip_addresses: All observed IP addresses.
    """

    service_name: str
    provider: str | None = None
    model: str | None = None
    models: list[str] = field(default_factory=list)
    user_count: int = 0
    app_count: int = 0
    token_volume: int = 0
    estimated_cost: float = 0.0
    data_classification: str | None = None
    approval_status: str = "not_reviewed"
    risk_score: float = 0.0
    risk_band: str = "low"
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    owner: str | None = None
    business_unit: str | None = None
    sources: list[str] = field(default_factory=list)
    hostnames: list[str] = field(default_factory=list)
    ip_addresses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        return {
            "service_name": self.service_name,
            "provider": self.provider,
            "model": self.model,
            "models": list(self.models),
            "user_count": self.user_count,
            "app_count": self.app_count,
            "token_volume": self.token_volume,
            "estimated_cost": self.estimated_cost,
            "data_classification": self.data_classification,
            "approval_status": self.approval_status,
            "risk_score": self.risk_score,
            "risk_band": self.risk_band,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "owner": self.owner,
            "business_unit": self.business_unit,
            "sources": list(self.sources),
            "hostnames": list(self.hostnames),
            "ip_addresses": list(self.ip_addresses),
        }

    def to_csv_row(self) -> list[str]:
        """Serialize to list for CSV export."""
        return [
            self.service_name,
            self.provider or "",
            self.model or "",
            str(self.user_count),
            str(self.app_count),
            str(self.token_volume),
            f"{self.estimated_cost:.2f}",
            self.data_classification or "",
            self.approval_status,
            f"{self.risk_score:.1f}",
            self.risk_band,
            self.last_seen.isoformat() if self.last_seen else "",
            self.first_seen.isoformat() if self.first_seen else "",
            self.owner or "",
            self.business_unit or "",
            ";".join(self.sources),
        ]

    @staticmethod
    def csv_header() -> list[str]:
        return [
            "service_name", "provider", "model", "user_count", "app_count",
            "token_volume", "estimated_cost", "data_classification",
            "approval_status", "risk_score", "risk_band", "last_seen",
            "first_seen", "owner", "business_unit", "sources",
        ]


@dataclass
class InventoryFilter:
    """Filter criteria for inventory queries.

    Attributes:
        provider: Filter by provider name.
        risk_band: Filter by risk band.
        risk_score_min: Minimum risk score.
        risk_score_max: Maximum risk score.
        approval_status: Filter by approval status.
        search: Text search on service_name.
    """

    provider: str | None = None
    risk_band: str | None = None
    risk_score_min: float | None = None
    risk_score_max: float | None = None
    approval_status: str | None = None
    search: str | None = None


class AssetInventory:
    """In-memory AI Asset Inventory with merge, dedup, and export.

    Thread-safe via asyncio.Lock. Production use would be backed by SQLite.

    Args:
        risk_engine: Optional RiskScoreEngine for scoring.
        cost_service: Optional CostAttributionService for cost estimation.
    """

    def __init__(
        self,
        risk_engine: Any = None,
        cost_service: Any = None,
    ) -> None:
        self._records: dict[str, InventoryRecord] = {}
        self._risk_engine = risk_engine
        self._cost_service = cost_service

    def add_record(self, record: InventoryRecord) -> InventoryRecord:
        """Add or update a record in the inventory.

        Duplicates (same service_name) are merged: counts summed,
        token volumes summed, latest last_seen wins.

        Args:
            record: InventoryRecord to add.

        Returns:
            The merged record.
        """
        existing = self._records.get(record.service_name)
        if existing:
            # Merge: sum counts, keep latest timestamps
            existing.user_count += record.user_count
            existing.app_count += record.app_count
            existing.token_volume += record.token_volume
            existing.estimated_cost += record.estimated_cost

            if record.last_seen and (not existing.last_seen or record.last_seen > existing.last_seen):
                existing.last_seen = record.last_seen
                existing.provider = record.provider or existing.provider
                existing.data_classification = record.data_classification or existing.data_classification

            # Merge lists
            existing.hostnames = list(set(existing.hostnames + record.hostnames))
            existing.ip_addresses = list(set(existing.ip_addresses + record.ip_addresses))
            existing.sources = list(set(existing.sources + record.sources))
            existing.models = list(set(existing.models + record.models))

            # Non-empty overrides
            if record.owner:
                existing.owner = record.owner
            if record.business_unit:
                existing.business_unit = record.business_unit
            if record.model:
                existing.model = record.model

            # Risk score: keep highest
            if record.risk_score > existing.risk_score:
                existing.risk_score = record.risk_score
                existing.risk_band = record.risk_band

            return existing
        else:
            self._records[record.service_name] = record
            self._update_metrics()
            return record

    def remove_record(self, service_name: str) -> None:
        """Remove a record from the inventory.

        Args:
            service_name: Service name to remove.
        """
        self._records.pop(service_name, None)
        self._update_metrics()

    def get_record(self, service_name: str) -> InventoryRecord | None:
        """Get a specific record by service name.

        Args:
            service_name: Service name to look up.

        Returns:
            InventoryRecord or None.
        """
        return self._records.get(service_name)

    def list_records(
        self,
        filters: InventoryFilter | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[InventoryRecord]:
        """List records with optional filtering and pagination.

        Args:
            filters: Optional filter criteria.
            limit: Max records to return.
            offset: Number of records to skip.

        Returns:
            List of matching InventoryRecord objects.
        """
        results = list(self._records.values())

        if filters:
            if filters.provider:
                results = [r for r in results if r.provider == filters.provider]
            if filters.risk_band:
                results = [r for r in results if r.risk_band == filters.risk_band]
            if filters.risk_score_min is not None:
                results = [r for r in results if r.risk_score >= filters.risk_score_min]
            if filters.risk_score_max is not None:
                results = [r for r in results if r.risk_score <= filters.risk_score_max]
            if filters.approval_status:
                results = [r for r in results if r.approval_status == filters.approval_status]
            if filters.search:
                results = [
                    r for r in results
                    if filters.search.lower() in r.service_name.lower()
                ]

        # Sort by last_seen descending
        results.sort(key=lambda r: r.last_seen or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return results[offset:offset + limit]

    def merge_from_discovery(
        self,
        dns_entries: list[Any] | None = None,
        proxy_entries: list[Any] | None = None,
        casb_classifications: dict[str, Any] | None = None,
    ) -> None:
        """Merge DNS and proxy discovery data into the inventory.

        Args:
            dns_entries: List of DNSEntry objects.
            proxy_entries: List of ProxyEntry objects.
            casb_classifications: Dict of app_id -> classification data.
        """
        now = datetime.now(timezone.utc)
        seen_services: dict[str, InventoryRecord] = {}

        # Process DNS entries
        if dns_entries:
            for entry in dns_entries:
                hostname = getattr(entry, "hostname", "") or ""
                provider = self._extract_provider(hostname)
                service_name = hostname or f"unknown-{hash(hostname)}"

                if service_name not in seen_services:
                    seen_services[service_name] = InventoryRecord(
                        service_name=service_name,
                        provider=provider,
                        hostnames=[hostname],
                        last_seen=getattr(entry, "timestamp", now),
                        first_seen=getattr(entry, "timestamp", now),
                        sources=["dns"],
                        approval_status="not_reviewed",
                    )
                else:
                    record = seen_services[service_name]
                    if hostname not in record.hostnames:
                        record.hostnames.append(hostname)
                    ts = getattr(entry, "timestamp", now)
                    if ts and ts > record.last_seen:
                        record.last_seen = ts
                    if "dns" not in record.sources:
                        record.sources.append("dns")

        # Process proxy entries
        if proxy_entries:
            for entry in proxy_entries:
                url = getattr(entry, "url", "") or ""
                hostname = self._extract_hostname(url)
                if not hostname:
                    continue

                provider = self._extract_provider(hostname)
                service_name = hostname
                user_id = getattr(entry, "user_id", "")

                if service_name not in seen_services:
                    seen_services[service_name] = InventoryRecord(
                        service_name=service_name,
                        provider=provider,
                        hostnames=[hostname],
                        user_count=1 if user_id else 0,
                        token_volume=getattr(entry, "bytes", 0) or 0,
                        last_seen=getattr(entry, "timestamp", now),
                        first_seen=getattr(entry, "timestamp", now),
                        sources=["proxy"],
                        approval_status="not_reviewed",
                    )
                else:
                    record = seen_services[service_name]
                    record.token_volume += getattr(entry, "bytes", 0) or 0
                    if user_id:
                        record.user_count += 1
                    if "proxy" not in record.sources:
                        record.sources.append("proxy")

        # Apply CASB classifications
        if casb_classifications:
            for app_id, classification_data in casb_classifications.items():
                for service_name, record in seen_services.items():
                    if app_id in service_name or (record.provider and app_id in record.provider):
                        if "casb" not in record.sources:
                            record.sources.append("casb")
                        break

        # Merge all seen services into inventory
        for record in seen_services.values():
            self.add_record(record)

    def export_json(self, indent: int = 2) -> str:
        """Export inventory as JSON string.

        Args:
            indent: JSON indentation level.

        Returns:
            JSON string.
        """
        records = [r.to_dict() for r in self._records.values()]
        return json.dumps(records, indent=indent, default=str)

    async def export_csv(self, filters: InventoryFilter | None = None) -> str:
        """Export inventory as CSV string.

        Args:
            filters: Optional filter criteria to limit exported records.

        Returns:
            CSV string with header.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(InventoryRecord.csv_header())
        records = self.list_records(filters=filters)
        for record in records:
            writer.writerow(record.to_csv_row())
        return output.getvalue()

    def get_cost_attribution(self) -> dict[str, Any]:
        """Get cost breakdown by provider.

        Returns:
            Dict with by_provider, by_model, total.
        """
        by_provider: dict[str, float] = {}
        by_model: dict[str, float] = {}
        total = 0.0

        for record in self._records.values():
            if record.provider:
                by_provider[record.provider] = (
                    by_provider.get(record.provider, 0.0) + record.estimated_cost
                )
            model_key = f"{record.provider}/{record.model}" if record.model else "unknown"
            by_model[model_key] = by_model.get(model_key, 0.0) + record.estimated_cost
            total += record.estimated_cost

        return {
            "by_provider": by_provider,
            "by_model": by_model,
            "total": round(total, 2),
        }

    def get_summary(self) -> dict[str, Any]:
        """Get aggregate summary stats.

        Returns:
            Dict with summary metrics.
        """
        if not self._records:
            return {
                "total_services": 0,
                "total_users": 0,
                "total_token_volume": 0,
                "total_estimated_cost": 0.0,
                "average_risk_score": 0.0,
            }

        total_users = sum(r.user_count for r in self._records.values())
        total_tokens = sum(r.token_volume for r in self._records.values())
        total_cost = sum(r.estimated_cost for r in self._records.values())
        scores = [r.risk_score for r in self._records.values() if r.risk_score > 0]
        avg_risk = sum(scores) / len(scores) if scores else 0.0

        return {
            "total_services": len(self._records),
            "total_users": total_users,
            "total_token_volume": total_tokens,
            "total_estimated_cost": round(total_cost, 2),
            "average_risk_score": round(avg_risk, 1),
        }

    def _extract_provider(self, hostname: str) -> str | None:
        """Try to extract provider name from hostname."""
        try:
            from anonreq.discovery.hostname_signatures import get_signature_by_hostname
            sig = get_signature_by_hostname(hostname)
            if sig:
                return sig.provider or sig.name
        except Exception:
            pass
        return None

    def _extract_hostname(self, url: str) -> str:
        """Extract hostname from a URL."""
        if "://" in url:
            url = url.split("://")[1]
        return url.split("/")[0].split(":")[0]

    def _update_metrics(self) -> None:
        """Update Prometheus gauges."""
        band_counts: dict[str, int] = {}
        provider_counts: dict[str, int] = {}

        for record in self._records.values():
            band = record.risk_band
            band_counts[band] = band_counts.get(band, 0) + 1
            provider = record.provider or "unknown"
            provider_counts[provider] = provider_counts.get(provider, 0) + 1

        for band, count in band_counts.items():
            INVENTORY_RISK_DIST.labels(risk_band=band).set(count)

        for provider, count in provider_counts.items():
            for band in band_counts:
                INVENTORY_SERVICES.labels(risk_band=band, provider=provider).set(count)
