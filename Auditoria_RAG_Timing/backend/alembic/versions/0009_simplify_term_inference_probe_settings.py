"""simplify term inference probe settings

Revision ID: 0009_term_probe_settings
Revises: 0008_refine_term_inference
Create Date: 2026-06-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0009_term_probe_settings"
down_revision: str | None = "0008_refine_term_inference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "term_inference_sessions",
        "initial_probes_per_term",
        new_column_name="probes_per_round",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.drop_column("term_inference_sessions", "additional_probes_per_round")
    op.drop_column("term_inference_sessions", "calibration_health_controls")


def downgrade() -> None:
    op.alter_column(
        "term_inference_sessions",
        "probes_per_round",
        new_column_name="initial_probes_per_term",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.add_column(
        "term_inference_sessions",
        sa.Column("additional_probes_per_round", sa.Integer(), nullable=False, server_default="4"),
    )
    op.add_column(
        "term_inference_sessions",
        sa.Column("calibration_health_controls", sa.Integer(), nullable=False, server_default="5"),
    )
