"""Create governance_record, review_cycle, and risk_assessment tables.

Revision ID: 002
Revises: 001
Create Date: 2026-07-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_cycle",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("last_review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    )
    op.create_index(
        "idx_review_cycle_tenant_id", "review_cycle", ["tenant_id"]
    )

    op.create_table(
        "governance_record",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), unique=True, nullable=False),
        sa.Column("officers", sa.Text(), nullable=False),
        sa.Column(
            "review_cycle_id", sa.Integer(), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(
            ["review_cycle_id"],
            ["review_cycle.id"],
        ),
    )
    op.create_index(
        "idx_governance_record_tenant_id", "governance_record", ["tenant_id"]
    )

    op.create_table(
        "risk_assessment",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("governance_record_id", sa.Integer(), nullable=False),
        sa.Column("dimensions", sa.Text(), nullable=False),
        sa.Column("extensions", sa.Text(), nullable=True),
        sa.Column("overall_risk_score", sa.Float(), nullable=False),
        sa.Column(
            "reassessment_required",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["governance_record_id"],
            ["governance_record.id"],
        ),
    )
    op.create_index(
        "idx_risk_assessment_tenant_id", "risk_assessment", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_risk_assessment_tenant_id")
    op.drop_table("risk_assessment")
    op.drop_index("idx_governance_record_tenant_id")
    op.drop_table("governance_record")
    op.drop_index("idx_review_cycle_tenant_id")
    op.drop_table("review_cycle")
