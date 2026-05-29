import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"


class Target(Base):
    __tablename__ = "targets"
    __table_args__ = (CheckConstraint("http_method in ('GET', 'POST')", name="ck_targets_http_method"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    endpoint_url: Mapped[str] = mapped_column(Text)
    http_method: Mapped[str] = mapped_column(String(10))
    headers_encrypted: Mapped[str] = mapped_column(Text, default="")
    payload_template: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    verify_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
