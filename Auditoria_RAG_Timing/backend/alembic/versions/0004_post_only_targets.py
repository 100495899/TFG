"""restrict targets to POST requests

Revision ID: 0004_post_only_targets
Revises: 0003_grouped_datasets
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_post_only_targets"
down_revision = "0003_grouped_datasets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM targets
                WHERE http_method <> 'POST' OR payload_template IS NULL
            ) THEN
                RAISE EXCEPTION
                    'All targets must use POST and define payload_template before applying migration 0004';
            END IF;
        END
        $$;
        """
    )
    op.drop_constraint("ck_targets_http_method", "targets", type_="check")
    op.drop_column("targets", "http_method")
    op.alter_column("targets", "payload_template", existing_type=postgresql.JSONB(), nullable=False)


def downgrade() -> None:
    op.add_column(
        "targets",
        sa.Column("http_method", sa.String(length=10), nullable=False, server_default=sa.text("'POST'")),
    )
    op.create_check_constraint("ck_targets_http_method", "targets", "http_method in ('GET', 'POST')")
    op.alter_column("targets", "payload_template", existing_type=postgresql.JSONB(), nullable=True)
