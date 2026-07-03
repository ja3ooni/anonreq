"""Create audit_event table with SHA-384 hash chain support.

Revision ID: 001
Revises: None
Create Date: 2026-07-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(64), unique=True, nullable=False),
        sa.Column("prev_hash", sa.String(96), nullable=True),
        sa.Column("hash", sa.String(96), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("policy_id", sa.String(64), nullable=True),
        sa.Column("decision", sa.String(32), nullable=True),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("operator_id", sa.String(64), nullable=True),
        sa.Column("change_type", sa.String(64), nullable=True),
        sa.Column("prev_value_hash", sa.String(96), nullable=True),
        sa.Column("new_value_hash", sa.String(96), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="2557"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_event_tenant_id", "audit_event", ["tenant_id"])
    op.create_index("idx_audit_event_timestamp", "audit_event", ["timestamp"])
    op.create_index("idx_audit_event_event_type", "audit_event", ["event_type"])


def downgrade() -> None:
    op.drop_index("idx_audit_event_event_type")
    op.drop_index("idx_audit_event_timestamp")
    op.drop_index("idx_audit_event_tenant_id")
    op.drop_table("audit_event")
