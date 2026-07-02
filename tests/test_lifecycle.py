"""Tests for lifecycle management service with approval gates.

Uses fakeredis-backed cache matching conftest patterns.
"""

from __future__ import annotations

import pytest

from anonreq.services.lifecycle import (
    LifecycleService,
    LifecycleStage,
    LifecycleState,
)


@pytest.fixture
async def lifecycle_service(cache_manager):
    svc = LifecycleService(cache_manager)
    # Clean slate
    await svc._redis.delete("anonreq:lifecycle:acme-corp")
    await svc._redis.delete("anonreq:lifecycle:acme-corp:transitions")
    yield svc


class TestLifecycleStages:
    async def test_default_stage_is_design(self, lifecycle_service):
        stage = await lifecycle_service.get_current_stage("acme-corp")
        assert stage == LifecycleStage.DESIGN

    async def test_valid_transition_design_to_review(self, lifecycle_service):
        state = await lifecycle_service.transition(
            "acme-corp",
            to_stage=LifecycleStage.REVIEW,
            approved_by="alice@acme.com",
            notes="Ready for review",
        )
        assert state.current_stage == LifecycleStage.REVIEW
        assert len(state.transitions) == 1

    async def test_valid_transition_review_to_testing(self, lifecycle_service):
        await lifecycle_service.transition("acme-corp", LifecycleStage.REVIEW, "alice@acme.com")
        state = await lifecycle_service.transition("acme-corp", LifecycleStage.TESTING, "bob@acme.com")
        assert state.current_stage == LifecycleStage.TESTING

    async def test_valid_transition_testing_to_production(self, lifecycle_service):
        await lifecycle_service.transition("acme-corp", LifecycleStage.REVIEW, "a")
        await lifecycle_service.transition("acme-corp", LifecycleStage.TESTING, "b")
        state = await lifecycle_service.transition("acme-corp", LifecycleStage.PRODUCTION, "c")
        assert state.current_stage == LifecycleStage.PRODUCTION

    async def test_valid_transition_production_to_retired(self, lifecycle_service):
        await lifecycle_service.transition("acme-corp", LifecycleStage.REVIEW, "a")
        await lifecycle_service.transition("acme-corp", LifecycleStage.TESTING, "b")
        await lifecycle_service.transition("acme-corp", LifecycleStage.PRODUCTION, "c")
        state = await lifecycle_service.transition("acme-corp", LifecycleStage.RETIRED, "d")
        assert state.current_stage == LifecycleStage.RETIRED

    async def test_invalid_transition_raises(self, lifecycle_service):
        with pytest.raises(ValueError, match="Cannot transition"):
            await lifecycle_service.transition("acme-corp", LifecycleStage.PRODUCTION)

    async def test_invalid_transition_design_to_production(self, lifecycle_service):
        with pytest.raises(ValueError, match="Cannot transition"):
            await lifecycle_service.transition("acme-corp", LifecycleStage.PRODUCTION)

    async def test_invalid_transition_retired_to_testing(self, lifecycle_service):
        await lifecycle_service.transition("acme-corp", LifecycleStage.REVIEW, "a")
        await lifecycle_service.transition("acme-corp", LifecycleStage.TESTING, "b")
        await lifecycle_service.transition("acme-corp", LifecycleStage.PRODUCTION, "c")
        await lifecycle_service.transition("acme-corp", LifecycleStage.RETIRED, "d")
        with pytest.raises(ValueError, match="Cannot transition"):
            await lifecycle_service.transition("acme-corp", LifecycleStage.TESTING)

    async def test_transition_requires_approval_gate(self, lifecycle_service):
        state = await lifecycle_service.transition(
            "acme-corp",
            LifecycleStage.REVIEW,
            approved_by="alice@acme.com",
            notes="Design approved by governance team",
        )
        assert state.current_stage == LifecycleStage.REVIEW
        assert state.transitions[0].approved_by == "alice@acme.com"
        assert state.transitions[0].notes == "Design approved by governance team"

    async def test_cannot_transition_from_retired_to_retired(self, lifecycle_service):
        await lifecycle_service.transition("acme-corp", LifecycleStage.REVIEW, "a")
        await lifecycle_service.transition("acme-corp", LifecycleStage.TESTING, "b")
        await lifecycle_service.transition("acme-corp", LifecycleStage.PRODUCTION, "c")
        await lifecycle_service.transition("acme-corp", LifecycleStage.RETIRED, "d")
        with pytest.raises(ValueError, match="Cannot transition"):
            await lifecycle_service.transition("acme-corp", LifecycleStage.RETIRED)


class TestLifecycleHistory:
    async def test_transition_history_tracked(self, lifecycle_service):
        await lifecycle_service.transition("acme-corp", LifecycleStage.REVIEW, "alice", "v1")
        await lifecycle_service.transition("acme-corp", LifecycleStage.TESTING, "bob", "v2")

        history = await lifecycle_service.get_transition_history("acme-corp")
        assert len(history) == 2
        assert history[0].to_stage == LifecycleStage.REVIEW
        assert history[1].to_stage == LifecycleStage.TESTING

    async def test_transition_history_empty_for_new_tenant(self, lifecycle_service):
        history = await lifecycle_service.get_transition_history("no-such")
        assert history == []

    async def test_transition_history_ordered(self, lifecycle_service):
        await lifecycle_service.transition("acme-corp", LifecycleStage.REVIEW, "a")
        import asyncio
        await asyncio.sleep(0.01)
        await lifecycle_service.transition("acme-corp", LifecycleStage.TESTING, "b")

        history = await lifecycle_service.get_transition_history("acme-corp")
        assert history[0].timestamp <= history[1].timestamp

    async def test_state_version_increments(self, lifecycle_service):
        s1 = await lifecycle_service.transition("acme-corp", LifecycleStage.REVIEW, "a")
        assert s1.version == 1
        s2 = await lifecycle_service.transition("acme-corp", LifecycleStage.TESTING, "b")
        assert s2.version == 2


class TestLifecycleState:
    async def test_get_state_returns_none_for_new(self, lifecycle_service):
        state = await lifecycle_service.get_state("no-such")
        assert state is None

    async def test_get_state_after_transition(self, lifecycle_service):
        await lifecycle_service.transition("acme-corp", LifecycleStage.REVIEW, "alice")
        state = await lifecycle_service.get_state("acme-corp")
        assert state is not None
        assert state.current_stage == LifecycleStage.REVIEW
        assert state.tenant_id == "acme-corp"
