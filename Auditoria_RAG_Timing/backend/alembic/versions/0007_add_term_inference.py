"""add term inference sessions

Revision ID: 0007_add_term_inference
Revises: 0006_remove_dataset_schema
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_add_term_inference"
down_revision = "0006_remove_dataset_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "term_inference_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("targets.id"), nullable=False),
        sa.Column("source_audit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("audit_sessions.id"), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, index=True),
        sa.Column("calibration_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("terms_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("progress_current", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("initial_probes_per_term", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("additional_probes_per_round", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("max_probes_per_term", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("confidence_level", sa.Float(), nullable=False, server_default="0.95"),
        sa.Column("calibration_health_controls", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("warning_message", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('PENDING', 'RUNNING', 'ABORT_REQUESTED', 'ABORTED', 'COMPLETED', 'FAILED')",
            name="ck_term_inference_sessions_status",
        ),
        sa.CheckConstraint("source_type in ('audit', 'summary_csv')", name="ck_term_inference_sessions_source_type"),
    )
    op.create_table(
        "term_inference_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("term_inference_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("term", sa.String(length=120), nullable=False, index=True),
        sa.Column("is_control", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("classification", sa.String(length=30), nullable=True),
        sa.Column("observed_mean_ttfb_ms", sa.Float(), nullable=True),
        sa.Column("observed_std_ttfb_ms", sa.Float(), nullable=True),
        sa.Column("valid_measurements", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_measurements", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("distance_to_threshold_ms", sa.Float(), nullable=True),
        sa.Column("closest_reference", sa.String(length=20), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "classification is null or classification in ('likely_present', 'likely_absent', 'inconclusive')",
            name="ck_term_inference_results_classification",
        ),
    )
    op.create_table(
        "term_inference_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("term_inference_results.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("request_index", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("ttfb_ms", sa.Float(), nullable=True),
        sa.Column("full_response_ms", sa.Float(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_size_bytes", sa.Integer(), nullable=True),
        sa.Column("is_error", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_type", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("term_inference_measurements")
    op.drop_table("term_inference_results")
    op.drop_table("term_inference_sessions")
