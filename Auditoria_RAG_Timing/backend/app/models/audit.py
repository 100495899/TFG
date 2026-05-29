import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    ABORT_REQUESTED = "ABORT_REQUESTED"
    ABORTED = "ABORTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AuditSession(Base):
    __tablename__ = "audit_sessions"
    __table_args__ = (
        CheckConstraint(
            "status in ('PENDING', 'RUNNING', 'ABORT_REQUESTED', 'ABORTED', 'COMPLETED', 'FAILED')",
            name="ck_audit_sessions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("targets.id"))
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"))
    status: Mapped[str] = mapped_column(String(30), index=True, default=AuditStatus.PENDING)
    delay_min_ms: Mapped[int] = mapped_column(Integer, default=0)
    delay_max_ms: Mapped[int] = mapped_column(Integer, default=0)
    calibration_requests: Mapped[int] = mapped_column(Integer, default=0)
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    random_seed: Mapped[int] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    target = relationship("Target")
    dataset = relationship("Dataset")
    results: Mapped[list["AuditResult"]] = relationship(cascade="all, delete-orphan")


class AuditResult(Base):
    __tablename__ = "audit_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("audit_sessions.id", ondelete="CASCADE"), index=True)
    request_index: Mapped[int] = mapped_column(Integer)
    query_text: Mapped[str] = mapped_column(Text)
    frequency_tag: Mapped[str] = mapped_column(String(30), index=True)
    length_tag: Mapped[str] = mapped_column(String(30))
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    ttfb_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    full_response_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_error: Mapped[bool] = mapped_column(Boolean, default=False)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
