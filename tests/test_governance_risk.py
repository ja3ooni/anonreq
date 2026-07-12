"""Tests for risk assessment framework with 6 core dimensions.

Uses SQLite in-memory with aiosqlite matching Phase 11 test patterns.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from anonreq.governance.risk import (
    check_config_triggers_reassessment,
    compute_dimension_score,
    compute_overall_risk_score,
    create_risk_assessment,
    flag_reassessment,
    get_risk_assessment,
    update_risk_assessment,
)
from anonreq.models.audit import Base
from anonreq.models.governance import (
    RISK_DIMENSIONS_CORE,
    GovernanceRecordModel,
    ReviewCycleModel,
    RiskDimensionScore,
)


@pytest.fixture
async def engine():
    """Create an in-memory SQLite engine with all tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine):
    """Create an async session bound to the test engine."""
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as s:
        yield s


@pytest.fixture
async def seeded_tenant(session: AsyncSession) -> str:
    """Create a governance record and return its tenant_id."""
    rc = ReviewCycleModel(
        tenant_id="risk-tenant",
        interval_days=90,
        last_review_date=None,
        next_review_date=datetime.now(UTC),
        status="active",
    )
    session.add(rc)
    await session.flush()

    gr = GovernanceRecordModel(
        tenant_id="risk-tenant",
        officers='[{"role": "governance", "name": "A", "email": "a@b.com"}]',
        review_cycle_id=rc.id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        status="active",
    )
    session.add(gr)
    await session.flush()
    return "risk-tenant", gr.id


def sample_dimensions() -> list[RiskDimensionScore]:
    return [
        RiskDimensionScore(
            dimension="privacy", severity=3, likelihood=2, overall_score=0.0
        ),
        RiskDimensionScore(
            dimension="security", severity=4, likelihood=3, overall_score=0.0
        ),
        RiskDimensionScore(
            dimension="bias", severity=2, likelihood=2, overall_score=0.0
        ),
        RiskDimensionScore(
            dimension="explainability",
            severity=2,
            likelihood=1,
            overall_score=0.0,
        ),
        RiskDimensionScore(
            dimension="fairness", severity=1, likelihood=1, overall_score=0.0
        ),
        RiskDimensionScore(
            dimension="safety", severity=5, likelihood=4, overall_score=0.0
        ),
    ]


class TestRiskDimensions:
    """Tests for dimension scoring arithmetic."""

    def test_risk_dimensions_core_list(self):
        """Core dimensions list has 6 entries."""
        assert len(RISK_DIMENSIONS_CORE) == 6
        assert "privacy" in RISK_DIMENSIONS_CORE
        assert "security" in RISK_DIMENSIONS_CORE
        assert "bias" in RISK_DIMENSIONS_CORE
        assert "explainability" in RISK_DIMENSIONS_CORE
        assert "fairness" in RISK_DIMENSIONS_CORE
        assert "safety" in RISK_DIMENSIONS_CORE

    def test_dimension_score_computation(self):
        """Each dimension: overall_score = severity * likelihood / 25."""
        score = compute_dimension_score(3, 2)
        assert score == 0.24  # 3*2/25 = 0.24

        score = compute_dimension_score(5, 5)
        assert score == 1.0  # 5*5/25 = 1.0

        score = compute_dimension_score(1, 1)
        assert score == 0.04  # 1*1/25 = 0.04

    def test_dimension_score_range(self):
        """Dimension scores are between 0.04 and 1.0."""
        minimum = compute_dimension_score(1, 1)
        maximum = compute_dimension_score(5, 5)
        assert minimum == 0.04
        assert maximum == 1.0

    def test_overall_risk_score_weighted_average(self):
        """Overall risk score is the weighted average across dimensions."""
        dims = sample_dimensions()
        for d in dims:
            d.overall_score = compute_dimension_score(d.severity, d.likelihood)

        overall = compute_overall_risk_score(dims)

        expected = sum(d.overall_score for d in dims) / len(dims)
        assert overall == round(expected, 4)

    def test_overall_risk_score_empty(self):
        """Empty dimensions returns 0.0."""
        assert compute_overall_risk_score([]) == 0.0

    def test_risk_dimension_score_validation(self):
        """Severity/likelihood outside 1-5 raises ValueError."""
        with pytest.raises(ValueError):  # noqa: PT011
            RiskDimensionScore(
                dimension="privacy",
                severity=0,
                likelihood=2,
                overall_score=0.0,
            )
        with pytest.raises(ValueError):  # noqa: PT011
            RiskDimensionScore(
                dimension="privacy",
                severity=3,
                likelihood=6,
                overall_score=0.0,
            )


class TestRiskAssessmentCRUD:
    """Tests for risk assessment create, read, update operations."""

    async def test_create_risk_assessment_stores_6_dimensions(
        self, session: AsyncSession, seeded_tenant
    ):
        """Test 1: create_risk_assessment stores 6 core dimensions."""
        tenant_id, gov_record_id = seeded_tenant
        dims = sample_dimensions()

        assessment = await create_risk_assessment(
            session, tenant_id, gov_record_id, dims
        )

        assert assessment.id > 0
        assert assessment.tenant_id == tenant_id
        assert len(assessment.dimensions) == 6
        assert assessment.reassessment_required is False
        assert assessment.governance_record_id == gov_record_id

    async def test_overall_risk_score_computed_correctly(
        self, session: AsyncSession, seeded_tenant
    ):
        """Test 2: overall_risk_score computed correctly."""
        tenant_id, gov_record_id = seeded_tenant
        dims = sample_dimensions()

        assessment = await create_risk_assessment(
            session, tenant_id, gov_record_id, dims
        )

        for d in assessment.dimensions:
            expected = round(
                (d.severity * d.likelihood) / 25.0, 4
            )
            assert d.overall_score == expected

        expected_overall = sum(
            d.overall_score for d in assessment.dimensions
        ) / len(assessment.dimensions)
        assert assessment.overall_risk_score == round(expected_overall, 4)

    async def test_get_risk_assessment_by_tenant(
        self, session: AsyncSession, seeded_tenant
    ):
        """Test 4: get_risk_assessment returns assessment by tenant_id."""
        tenant_id, gov_record_id = seeded_tenant
        dims = sample_dimensions()

        await create_risk_assessment(session, tenant_id, gov_record_id, dims)

        fetched = await get_risk_assessment(session, tenant_id)
        assert fetched is not None
        assert fetched.tenant_id == tenant_id
        assert len(fetched.dimensions) == 6

    async def test_get_risk_assessment_nonexistent(
        self, session: AsyncSession
    ):
        """get_risk_assessment for non-existent tenant returns None."""
        fetched = await get_risk_assessment(session, "no-such-tenant")
        assert fetched is None

    async def test_update_risk_assessment_recomputes_score(
        self, session: AsyncSession, seeded_tenant
    ):
        """Test 5: update_risk_assessment modifies dimensions and recomputes."""
        tenant_id, gov_record_id = seeded_tenant
        dims = sample_dimensions()

        await create_risk_assessment(session, tenant_id, gov_record_id, dims)

        updated_dims = sample_dimensions()
        for d in updated_dims:
            d.severity = 5
            d.likelihood = 5
            d.overall_score = 1.0

        updated = await update_risk_assessment(
            session, tenant_id, updated_dims
        )

        all_expected = 1.0
        assert updated.overall_risk_score == all_expected
        for d in updated.dimensions:
            assert d.severity == 5
            assert d.likelihood == 5

    async def test_update_nonexistent_raises(
        self, session: AsyncSession
    ):
        """Update on non-existent assessment raises ValueError."""
        with pytest.raises(ValueError, match="No risk assessment"):
            await update_risk_assessment(session, "ghost", sample_dimensions())

    async def test_missing_core_dimension_raises(
        self, session: AsyncSession, seeded_tenant
    ):
        """Missing a core dimension raises ValueError."""
        tenant_id, gov_record_id = seeded_tenant
        dims = [
            RiskDimensionScore(
                dimension="privacy", severity=2, likelihood=2, overall_score=0.0
            ),
        ]
        with pytest.raises(ValueError, match="Missing core dimensions"):
            await create_risk_assessment(
                session, tenant_id, gov_record_id, dims
            )


class TestReassessmentFlag:
    """Tests for reassessment flagging."""

    async def test_flag_reassessment_sets_flag(
        self, session: AsyncSession, seeded_tenant
    ):
        """Test 3: flag_reassessment sets reassessment_required=True."""
        tenant_id, gov_record_id = seeded_tenant
        dims = sample_dimensions()

        await create_risk_assessment(session, tenant_id, gov_record_id, dims)
        flagged = await flag_reassessment(
            session, tenant_id, "Critical config change"
        )

        assert flagged.reassessment_required is True

    async def test_flag_nonexistent_raises(
        self, session: AsyncSession
    ):
        """Flag reassessment on non-existent tenant raises ValueError."""
        with pytest.raises(ValueError, match="No risk assessment"):
            await flag_reassessment(session, "ghost", "test")

    async def test_config_change_triggers_reassessment(
        self, session: AsyncSession, seeded_tenant
    ):
        """Test 6: Config change affecting entity types triggers flag."""
        tenant_id, gov_record_id = seeded_tenant
        dims = sample_dimensions()

        await create_risk_assessment(session, tenant_id, gov_record_id, dims)

        result = await check_config_triggers_reassessment(
            session, tenant_id, ["entity_types", "rate_limit"]
        )
        assert result is True

        assessment = await get_risk_assessment(session, tenant_id)
        assert assessment is not None
        assert assessment.reassessment_required is True

    async def test_config_change_no_trigger(
        self, session: AsyncSession, seeded_tenant
    ):
        """Non-entity config changes don't trigger reassessment."""
        tenant_id, gov_record_id = seeded_tenant
        dims = sample_dimensions()

        await create_risk_assessment(session, tenant_id, gov_record_id, dims)

        result = await check_config_triggers_reassessment(
            session, tenant_id, ["rate_limit", "timeout"]
        )
        assert result is False

        assessment = await get_risk_assessment(session, tenant_id)
        assert assessment is not None
        assert assessment.reassessment_required is False


class TestExtensionDimensions:
    """Tests for tenant extension dimensions."""

    async def test_extension_dimensions_stored_with_core(
        self, session: AsyncSession, seeded_tenant
    ):
        """Test 7: Tenant extension dimensions are stored alongside core."""
        tenant_id, gov_record_id = seeded_tenant
        dims = sample_dimensions()
        extensions = [
            RiskDimensionScore(
                dimension="custom_regulatory",
                severity=3,
                likelihood=2,
                overall_score=0.0,
            ),
            RiskDimensionScore(
                dimension="data_quality",
                severity=2,
                likelihood=3,
                overall_score=0.0,
            ),
        ]

        assessment = await create_risk_assessment(
            session, tenant_id, gov_record_id, dims, extensions
        )

        assert assessment.extensions is not None
        assert len(assessment.extensions) == 2
        assert assessment.extensions[0].dimension == "custom_regulatory"

        all_dims = dims + extensions
        expected_overall = sum(
            compute_dimension_score(d.severity, d.likelihood) for d in all_dims
        ) / len(all_dims)
        assert assessment.overall_risk_score == round(expected_overall, 4)


class TestScoringArithmetic:
    """Standalone scoring arithmetic verification."""

    def test_score_formula_verification(self):
        """Verify the scoring formula with known values."""
        pairs = [
            (1, 1, 0.04),
            (1, 2, 0.08),
            (2, 2, 0.16),
            (3, 3, 0.36),
            (4, 4, 0.64),
            (5, 5, 1.0),
            (3, 2, 0.24),
            (5, 1, 0.20),
            (1, 5, 0.20),
        ]
        for severity, likelihood, expected in pairs:
            score = compute_dimension_score(severity, likelihood)
            assert score == expected, (
                f"severity={severity}, likelihood={likelihood}: "
                f"expected {expected}, got {score}"
            )

    def test_overall_risk_with_extensions(self):
        """Overall risk includes extension dimensions in average."""
        dims = [
            RiskDimensionScore(
                dimension="privacy",
                severity=3,
                likelihood=2,
                overall_score=0.24,
            ),
            RiskDimensionScore(
                dimension="security",
                severity=4,
                likelihood=3,
                overall_score=0.48,
            ),
        ]
        overall = compute_overall_risk_score(dims)
        assert overall == 0.36  # (0.24 + 0.48) / 2
