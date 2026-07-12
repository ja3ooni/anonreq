from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FIREWALL_DECISIONS(StrEnum):  # noqa: N801
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class FirewallConfig(BaseModel):
    """Runtime configuration for the Phase 21 inline AI firewall."""

    model_config = {"extra": "forbid"}

    enabled: bool = True
    jailbreak_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    injection_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    override_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    latency_budget_ms: int = Field(default=20, ge=1)
    classifier_model_path: str = "/etc/anonreq/firewall/model.onnx"
    jailbreak_db_path: str = "/etc/anonreq/firewall/jailbreak_db.json"
    embedding_model: str = "all-MiniLM-L6-v2"
    fail_open: bool = False
    mitre_atlas_path: str = "config/mitre_atlas.yaml"
