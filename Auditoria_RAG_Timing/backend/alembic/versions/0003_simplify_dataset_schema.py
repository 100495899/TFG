"""simplify dataset metadata for grouped format

Revision ID: 0003_grouped_datasets
Revises: 0002_plain_headers
Create Date: 2026-06-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_grouped_datasets"
down_revision = "0002_plain_headers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("datasets", "sha256")
    op.alter_column("datasets", "schema_version", server_default=sa.text("'grouped-es-v1'"))


def downgrade() -> None:
    op.add_column("datasets", sa.Column("sha256", sa.String(length=64), nullable=True))
    op.alter_column("datasets", "schema_version", server_default=sa.text("'flat-v1'"))
    op.execute("UPDATE datasets SET schema_version = 'flat-v1'")
