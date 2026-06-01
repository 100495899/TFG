"""store target headers as plain json

Revision ID: 0002_plain_headers
Revises: 0001_initial
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_plain_headers"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "targets",
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.drop_column("targets", "headers_encrypted")


def downgrade() -> None:
    op.add_column("targets", sa.Column("headers_encrypted", sa.Text(), nullable=False, server_default=""))
    op.drop_column("targets", "headers")
