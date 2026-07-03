"""Policy Enforcement Evidence Store.

Generates and manages deterministic, tamper-evident compliance evidence
records and Merkle-style manifests of policy decisions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from anonreq.policy.models import PolicyAction, PolicyDecision, PolicyRule
from anonreq.policy.store import PolicyStore


def _hash_policy_state(rules: list[PolicyRule]) -> str:
    """Generate a deterministic SHA-256 hash of the rules list.

    Sorts serialized rule objects to remain independent of rules list ordering.
    """
    serialized_rules = []
    for rule in rules:
        dump = rule.model_dump()
        canonical = json.dumps(dump, sort_keys=True, separators=(",", ":"))
        serialized_rules.append(canonical)

    serialized_rules.sort()
    joined = "".join(serialized_rules)
    return hashlib.sha256(joined.encode()).hexdigest()


class PolicyEvidence(BaseModel):
    """Pydantic model representing compliance evidence for a policy decision."""

    model_config = {"extra": "forbid"}

    evidence_id: str
    timestamp: datetime
    tenant_id: str
    policy_version: str
    policy_hash: str
    rule_count: int
    enabled_rule_count: int
    action: PolicyAction | None
    decision_id: str | None = None
    metadata: dict = {}


class EvidenceStore:
    """In-memory ephemeral store for policy enforcement evidence."""

    def __init__(self, policy_store: PolicyStore) -> None:
        """Initialize with a PolicyStore dependency."""
        self._store = policy_store
        self._records: dict[str, PolicyEvidence] = {}

    async def record_decision_evidence(self, tenant_id: str, decision: PolicyDecision) -> PolicyEvidence:
        """Generate and store an evidence record based on the current policy state."""
        # Load current rules for the tenant
        rules = await self._store.load_policies(tenant_id)
        enabled_rules = [r for r in rules if r.enabled]

        # Compute deterministic policy hash and version
        policy_hash = _hash_policy_state(rules)
        policy_version = policy_hash[:16]

        evidence_id = str(uuid4())
        # Use decision.enforcement as decision_id if appropriate, or generate one
        decision_id = decision.enforcement if (decision.enforcement and decision.enforcement != "503") else uuid4().hex[:16]

        record = PolicyEvidence(
            evidence_id=evidence_id,
            timestamp=decision.decision_ts,
            tenant_id=tenant_id,
            policy_version=policy_version,
            policy_hash=policy_hash,
            rule_count=len(rules),
            enabled_rule_count=len(enabled_rules),
            action=decision.action,
            decision_id=decision_id,
            metadata={
                "matched_rule_ids": decision.matched_rule_ids,
            },
        )

        self._records[evidence_id] = record
        return record

    async def generate_manifest(self, tenant_id: str) -> dict:
        """Generate a Merkle-style manifest of all evidence records for a tenant."""
        tenant_records = [r for r in self._records.values() if r.tenant_id == tenant_id]
        # Sort by timestamp and ID for determinism
        tenant_records.sort(key=lambda x: (x.timestamp.isoformat(), x.evidence_id))

        # Calculate Merkle-style root hash of the evidence records
        hashes = [r.policy_hash for r in tenant_records]
        joined_hashes = "".join(hashes)
        merkle_root = hashlib.sha256(joined_hashes.encode()).hexdigest()

        return {
            "tenant_id": tenant_id,
            "merkle_root": merkle_root,
            "records": [r.model_dump() for r in tenant_records],
        }

    async def get_evidence(self, evidence_id: str) -> PolicyEvidence | None:
        """Retrieve an evidence record by ID."""
        return self._records.get(evidence_id)
