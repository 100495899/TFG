import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TermInferenceStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    ABORT_REQUESTED = "ABORT_REQUESTED"
    ABORTED = "ABORTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TermClassification(StrEnum):
    LIKELY_PRESENT = "likely_present"
    LIKELY_ABSENT = "likely_absent"
    INCONCLUSIVE = "inconclusive"


class TermInferenceSession(Base):
    __tablename__ = "term_inference_sessions"
    __table_args__ = (
        CheckConstraint(
            "status in ('PENDING', 'RUNNING', 'ABORT_REQUESTED', 'ABORTED', 'COMPLETED', 'FAILED')",
            name="ck_term_inference_sessions_status",
        ),
        CheckConstraint(
            "source_type in ('audit', 'summary_csv')",
            name="ck_term_inference_sessions_source_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("targets.id"))
    source_audit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("audit_sessions.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(30))
    source_label: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), index=True, default=TermInferenceStatus.PENDING)
    calibration_profile: Mapped[dict[str, Any]] = mapped_column(JSONB)
    terms_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    random_seed: Mapped[int] = mapped_column(Integer)
    initial_probes_per_term: Mapped[int] = mapped_column(Integer, default=6)
    additional_probes_per_round: Mapped[int] = mapped_column(Integer, default=4)
    max_probes_per_term: Mapped[int] = mapped_column(Integer, default=30)
    calibration_health_controls: Mapped[int] = mapped_column(Integer, default=5)
    warning_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    target = relationship("Target")
    source_audit = relationship("AuditSession")
    results: Mapped[list["TermInferenceResult"]] = relationship(cascade="all, delete-orphan")


class TermInferenceResult(Base):
    __tablename__ = "term_inference_results"
    __table_args__ = (
        CheckConstraint(
            "classification is null or classification in ('likely_present', 'likely_absent', 'inconclusive')",
            name="ck_term_inference_results_classification",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("term_inference_sessions.id", ondelete="CASCADE"), index=True)
    term: Mapped[str] = mapped_column(String(80), index=True)
    is_control: Mapped[bool] = mapped_column(Boolean, default=False)
    classification: Mapped[str | None] = mapped_column(String(30), nullable=True)
    observed_mean_ttfb_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_std_ttfb_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    valid_measurements: Mapped[int] = mapped_column(Integer, default=0)
    total_measurements: Mapped[int] = mapped_column(Integer, default=0)
    distance_to_threshold_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    closest_reference: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    measurements: Mapped[list["TermInferenceMeasurement"]] = relationship(cascade="all, delete-orphan")


class TermInferenceMeasurement(Base):
    __tablename__ = "term_inference_measurements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("term_inference_results.id", ondelete="CASCADE"), index=True)
    request_index: Mapped[int] = mapped_column(Integer)
    round_number: Mapped[int] = mapped_column(Integer)
    query_text: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    ttfb_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    full_response_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_error: Mapped[bool] = mapped_column(Boolean, default=False)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
