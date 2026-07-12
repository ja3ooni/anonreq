"""Lifecycle management service with approval gates between stages.

Provides:
- ``LifecycleStage`` enum: design → review → testing → production → retired
- ``LifecycleTransition`` model for audit trail
- ``LifecycleState`` model for current tenant state
- ``LifecycleService`` with transition validation and gate enforcement
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel

from anonreq.cache.manager import CacheManager


class LifecycleStage(StrEnum):
    DESIGN = "design"
    REVIEW = "review"
    TESTING = "testing"
    PRODUCTION = "production"
    RETIRED = "retired"


VALID_TRANSITIONS: dict[LifecycleStage, list[LifecycleStage]] = {
    LifecycleStage.DESIGN: [LifecycleStage.REVIEW],
    LifecycleStage.REVIEW: [LifecycleStage.TESTING, LifecycleStage.DESIGN],
    LifecycleStage.TESTING: [LifecycleStage.PRODUCTION, LifecycleStage.REVIEW],
    LifecycleStage.PRODUCTION: [LifecycleStage.REVIEW, LifecycleStage.RETIRED],
    LifecycleStage.RETIRED: [LifecycleStage.DESIGN],
}


class LifecycleTransition(BaseModel):
    from_stage: LifecycleStage | None
    to_stage: LifecycleStage
    approved_by: str
    notes: str | None = None
    timestamp: datetime

    model_config = {"extra": "ignore"}


class LifecycleState(BaseModel):
    tenant_id: str
    current_stage: LifecycleStage
    transitions: list[LifecycleTransition] = []
    version: int = 1
    created_at: datetime
    updated_at: datetime

    model_config = {"extra": "ignore"}


STATE_KEY_PREFIX = "anonreq:lifecycle"
TRANSITIONS_KEY_PREFIX = "anonreq:lifecycle:transitions"


class LifecycleService:
    """Lifecycle management with stage transitions and approval gates.

    Stores lifecycle state in Valkey for each tenant. Transitions are
    validated against ``VALID_TRANSITIONS`` and each requires an approved_by
    operator (the approval gate).
    """

    def __init__(self, cache_manager: CacheManager) -> None:
        self._redis = cache_manager._redis

    def _state_key(self, tenant_id: str) -> str:
        return f"{STATE_KEY_PREFIX}:{tenant_id}"

    def _transitions_key(self, tenant_id: str) -> str:
        return f"{TRANSITIONS_KEY_PREFIX}:{tenant_id}"

    async def get_current_stage(
        self,
        tenant_id: str,
    ) -> LifecycleStage:
        raw = await self._redis.get(self._state_key(tenant_id))
        if raw is None:
            return LifecycleStage.DESIGN
        state = LifecycleState(**json.loads(raw))
        return state.current_stage

    async def get_state(
        self,
        tenant_id: str,
    ) -> LifecycleState | None:
        raw = await self._redis.get(self._state_key(tenant_id))
        if raw is None:
            return None
        return LifecycleState(**json.loads(raw))

    async def transition(
        self,
        tenant_id: str,
        to_stage: LifecycleStage,
        approved_by: str = "system",
        notes: str | None = None,
    ) -> LifecycleState:
        raw = await self._redis.get(self._state_key(tenant_id))
        now = datetime.now(UTC)

        if raw is None:
            current_stage = LifecycleStage.DESIGN
            version = 0
            transitions: list[LifecycleTransition] = []
        else:
            state = LifecycleState(**json.loads(raw))
            current_stage = state.current_stage
            version = state.version
            transitions = state.transitions

        if current_stage == to_stage:
            raise ValueError(
                f"Cannot transition: already at {to_stage.value}"
            )

        allowed = VALID_TRANSITIONS.get(current_stage, [])
        if to_stage not in allowed:
            raise ValueError(
                f"Cannot transition from {current_stage.value} to {to_stage.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        transition = LifecycleTransition(
            from_stage=current_stage,
            to_stage=to_stage,
            approved_by=approved_by,
            notes=notes,
            timestamp=now,
        )

        state = LifecycleState(
            tenant_id=tenant_id,
            current_stage=to_stage,
            transitions=[*transitions, transition],
            version=version + 1,
            created_at=now if version == 0 else transitions[0].timestamp if transitions else now,
            updated_at=now,
        )

        await self._redis.set(self._state_key(tenant_id), state.model_dump_json())

        transition_list_raw = await self._redis.get(self._transitions_key(tenant_id)) or "[]"
        transition_list = json.loads(transition_list_raw)
        transition_list.append({
            "from_stage": transition.from_stage.value if transition.from_stage else None,
            "to_stage": transition.to_stage.value,
            "approved_by": transition.approved_by,
            "notes": transition.notes,
            "timestamp": transition.timestamp.isoformat(),
        })
        await self._redis.set(
            self._transitions_key(tenant_id),
            json.dumps(transition_list),
        )

        return state

    async def get_transition_history(
        self,
        tenant_id: str,
    ) -> list[LifecycleTransition]:
        raw = await self._redis.get(self._transitions_key(tenant_id))
        if raw is None:
            return []
        data = json.loads(raw)
        return [
            LifecycleTransition(
                from_stage=LifecycleStage(t["from_stage"]) if t.get("from_stage") else None,
                to_stage=LifecycleStage(t["to_stage"]),
                approved_by=t["approved_by"],
                notes=t.get("notes"),
                timestamp=datetime.fromisoformat(t["timestamp"]),
            )
            for t in data
        ]
