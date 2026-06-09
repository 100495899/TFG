import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TargetBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    endpoint_url: str
    headers: dict[str, str] = Field(default_factory=dict)
    payload_template: dict[str, Any]
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    verify_tls: bool = True

    @field_validator("endpoint_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("endpoint_url must start with http:// or https://")
        return value


class TargetCreate(TargetBase):
    pass


class TargetUpdate(TargetBase):
    pass


class TargetRead(BaseModel):
    id: uuid.UUID
    name: str
    endpoint_url: str
    headers: dict[str, str]
    payload_template: dict[str, Any]
    timeout_seconds: int
    verify_tls: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TargetTestRequest(BaseModel):
    query: str = "Esto es una prueba"


class TargetTestResponse(BaseModel):
    ok: bool
    status_code: int | None
    ttfb_ms: float | None
    full_response_ms: float | None
    response_size_bytes: int | None
    error_type: str | None
    error_message: str | None
