import random
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AuditStartRequest(BaseModel):
    target_id: uuid.UUID
    dataset_id: uuid.UUID
    calibration_requests: int = Field(default=3, ge=1, le=100)
    random_seed: int = Field(
        default_factory=lambda: random.randint(1, 2_147_483_647),
        ge=1,
        le=2_147_483_647,
    )


class AuditStartResponse(BaseModel):
    session_id: uuid.UUID


class AuditSessionRead(BaseModel):
    id: uuid.UUID
    target_id: uuid.UUID
    dataset_id: uuid.UUID
    status: str
    calibration_requests: int
    progress_current: int
    progress_total: int
    random_seed: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class AuditStatus(BaseModel):
    id: uuid.UUID
    status: str
    progress_current: int
    progress_total: int
    error_message: str | None
    error_count: int = 0
    mean_ttfb_ms: float | None
    mean_full_response_ms: float | None


class AuditDashboardItem(AuditStatus):
    target_id: uuid.UUID
    target_name: str
    dataset_id: uuid.UUID
    dataset_name: str
    random_seed: int
    calibration_requests: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class AuditResultRead(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    request_index: int
    query_text: str
    frequency_tag: str
    length_tag: str
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


class ResultsPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AuditResultRead]


class GroupStats(BaseModel):
    frequency: str | None = None
    length: str | None = None
    count: int
    raw_count: int
    error_count: int
    outlier_count: int
    mean_ms: float | None
    median_ms: float | None
    std_ms: float | None
    p25_ms: float | None
    p75_ms: float | None
    p95_ms: float | None
    min_ms: float | None
    max_ms: float | None
    lower_outlier_threshold_ms: float | None
    upper_outlier_threshold_ms: float | None
    error_rate: float


class ComparisonStats(BaseModel):
    group_a: str
    group_b: str
    mean_difference_ms: float | None
    median_difference_ms: float | None
    p_value: float | None
    evidence: str


class AuditSummaryMetadata(BaseModel):
    target_id: uuid.UUID
    target_name: str
    dataset_id: uuid.UUID
    dataset_name: str
    status: str
    random_seed: int
    calibration_requests: int
    total_requests: int
    successful_requests: int
    error_requests: int
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None


class AnalysisPoint(BaseModel):
    request_index: int
    frequency: str
    length: str
    ttfb_ms: float
    full_response_ms: float | None
    is_outlier: bool


class AuditSummary(BaseModel):
    session_id: uuid.UUID
    metric: str
    metadata: AuditSummaryMetadata
    overall: GroupStats
    overall_full_response: GroupStats
    groups: list[GroupStats]
    by_length: list[GroupStats]
    by_frequency_length: list[GroupStats]
    comparisons: list[ComparisonStats]
    points: list[AnalysisPoint]
