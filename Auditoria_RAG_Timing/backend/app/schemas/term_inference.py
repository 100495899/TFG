import random
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


Classification = Literal["likely_present", "likely_absent", "inconclusive"]
ClosestReference = Literal["high", "medium", "low"]


class TermsPayload(BaseModel):
    terms: list[str] = Field(default_factory=list, max_length=100)
    custom_queries: dict[str, list[str]] = Field(default_factory=dict, max_length=100)
    negative_controls: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def require_terms_or_custom_queries(self) -> "TermsPayload":
        if not self.terms and not self.custom_queries:
            raise ValueError("terms or custom_queries is required")
        return self


class TermInferenceStartResponse(BaseModel):
    session_id: uuid.UUID


class TermInferenceSessionRead(BaseModel):
    id: uuid.UUID
    target_id: uuid.UUID
    source_audit_id: uuid.UUID | None
    source_type: str
    source_label: str
    status: str
    progress_current: int
    progress_total: int
    random_seed: int
    probes_per_round: int
    max_probes_per_term: int
    warning_message: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class TermInferenceListItem(TermInferenceSessionRead):
    target_name: str
    result_count: int


class TermInferenceStatusRead(BaseModel):
    id: uuid.UUID
    status: str
    progress_current: int
    progress_total: int
    warning_message: str | None
    error_message: str | None


class TermInferenceResultRead(BaseModel):
    id: uuid.UUID
    term: str
    is_control: bool
    classification: Classification | None
    observed_mean_ttfb_ms: float | None
    observed_std_ttfb_ms: float | None
    valid_measurements: int
    total_measurements: int
    distance_to_threshold_ms: float | None
    closest_reference: ClosestReference | None
    error_count: int

    model_config = {"from_attributes": True}


class TermInferenceMeasurementRead(BaseModel):
    id: uuid.UUID
    result_id: uuid.UUID
    request_index: int
    round_number: int
    query_text: str
    latency_ms: float | None
    ttfb_ms: float | None
    full_response_ms: float | None
    status_code: int | None
    response_size_bytes: int | None
    is_error: bool
    error_type: str | None
    error_message: str | None
    timestamp: datetime

    model_config = {"from_attributes": True}


class CalibrationProfileRead(BaseModel):
    high_mean_ms: float
    medium_mean_ms: float | None
    low_mean_ms: float
    threshold_ms: float
    gray_zone_ms: float


class TermInferenceResultsPage(BaseModel):
    session: TermInferenceSessionRead
    profile: CalibrationProfileRead
    results: list[TermInferenceResultRead]
    measurements: list[TermInferenceMeasurementRead]


class TermInferenceJsonStart(BaseModel):
    target_id: uuid.UUID
    source_audit_id: uuid.UUID
    terms_payload: TermsPayload
    random_seed: int = Field(default_factory=lambda: random.randint(1, 2_147_483_647), ge=1, le=2_147_483_647)
    probes_per_round: int = Field(default=6, ge=1, le=30)
    max_probes_per_term: int = Field(default=30, ge=1, le=100)
