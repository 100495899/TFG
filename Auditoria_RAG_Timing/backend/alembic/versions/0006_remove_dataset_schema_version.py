"""remove redundant dataset schema version

Revision ID: 0006_remove_dataset_schema
Revises: 0005_remove_audit_delays
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_remove_dataset_schema"
down_revision = "0005_remove_audit_delays"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("datasets", "schema_version")


def downgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column(
            "schema_version",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'grouped-es-v1'"),
        ),
    )
