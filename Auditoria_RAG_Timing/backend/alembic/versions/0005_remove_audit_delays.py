"""remove artificial delays from audit sessions

Revision ID: 0005_remove_audit_delays
Revises: 0004_post_only_targets
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_remove_audit_delays"
down_revision = "0004_post_only_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("audit_sessions", "delay_max_ms")
    op.drop_column("audit_sessions", "delay_min_ms")


def downgrade() -> None:
    op.add_column(
        "audit_sessions",
        sa.Column("delay_min_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "audit_sessions",
        sa.Column("delay_max_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
