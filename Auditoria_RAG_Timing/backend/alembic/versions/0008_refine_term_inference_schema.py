"""refine term inference schema

Revision ID: 0008_refine_term_inference
Revises: 0007_add_term_inference
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_refine_term_inference"
down_revision = "0007_add_term_inference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("term_inference_sessions", "confidence_level")
    op.alter_column(
        "term_inference_results",
        "term",
        existing_type=sa.String(length=120),
        type_=sa.String(length=80),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "term_inference_results",
        "term",
        existing_type=sa.String(length=80),
        type_=sa.String(length=120),
        existing_nullable=False,
    )
    op.add_column(
        "term_inference_sessions",
        sa.Column("confidence_level", sa.Float(), nullable=False, server_default="0.95"),
    )
