"""Create tenant table for multi-tenant segregation.

Revision ID: 003
Revises: 002
Create Date: 2026-07-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), unique=True, nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("kms_key_arn", sa.String(512), nullable=True),
        sa.Column("spend_limits_json", sa.Text(), nullable=True),
        sa.Column("rate_limits_json", sa.Text(), nullable=True),
        sa.Column("allowed_providers_json", sa.Text(), nullable=True),
        sa.Column("allowed_models_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_tenant_tenant_id", "tenant", ["tenant_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("idx_tenant_tenant_id")
    op.drop_table("tenant")
