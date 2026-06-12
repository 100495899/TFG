import itertools
import uuid
from collections.abc import Callable

import numpy as np
from scipy import stats
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditResult, AuditSession
from app.models.dataset import Dataset
from app.models.target import Target
from app.schemas.audit import (
    AnalysisPoint,
    AuditSummary,
    AuditSummaryMetadata,
    ComparisonStats,
    GroupStats,
)

FREQUENCIES = ("high", "medium", "low")
LENGTHS = ("short", "medium", "long")


def _safe_float(value) -> float | None:
    if value is None or np.isnan(value):
        return None
    return float(value)


def _evidence(p_value: float | None, d: float | None, count_a: int, count_b: int) -> str:
    if count_a < 30 or count_b < 30 or p_value is None or d is None:
        return "insufficient"
    abs_d = abs(d)
    if p_value < 0.001 and abs_d >= 0.8:
        return "strong"
    if p_value < 0.01 and abs_d >= 0.5:
        return "moderate"
    if p_value < 0.05 and abs_d >= 0.2:
        return "weak"
    return "insufficient"


def _filter_upper_percentile(
    values: list[float],
    percentile: float = 99,
    minimum_sample_size: int = 100,
) -> tuple[list[float], float | None]:
    if not values:
        return [], None
    if len(values) < minimum_sample_size:
        return values.copy(), None
    threshold = float(np.percentile(np.array(values, dtype=float), percentile))
    return [value for value in values if value <= threshold], threshold


def _group_stats(
    rows: list[AuditResult],
    values: list[float],
    *,
    frequency: str | None = None,
    length: str | None = None,
    outlier_count: int = 0,
    p99_threshold_ms: float | None = None,
) -> GroupStats:
    arr = np.array(values, dtype=float)
    error_count = sum(1 for row in rows if row.is_error)
    return GroupStats(
        frequency=frequency,
        length=length,
        count=len(values),
        raw_count=len(rows),
        error_count=error_count,
        outlier_count=outlier_count,
        mean_ms=_safe_float(np.mean(arr)) if len(arr) else None,
        median_ms=_safe_float(np.median(arr)) if len(arr) else None,
        std_ms=_safe_float(np.std(arr)) if len(arr) else None,
        p25_ms=_safe_float(np.percentile(arr, 25)) if len(arr) else None,
        p75_ms=_safe_float(np.percentile(arr, 75)) if len(arr) else None,
        p95_ms=_safe_float(np.percentile(arr, 95)) if len(arr) else None,
        min_ms=_safe_float(np.min(arr)) if len(arr) else None,
        max_ms=_safe_float(np.max(arr)) if len(arr) else None,
        p99_threshold_ms=p99_threshold_ms,
        error_rate=(error_count / len(rows)) if rows else 0.0,
    )


def _clean_values_by_cell(
    rows: list[AuditResult],
    value_getter: Callable[[AuditResult], float | None],
) -> tuple[dict[tuple[str, str], list[float]], dict[tuple[str, str], float | None]]:
    cleaned: dict[tuple[str, str], list[float]] = {}
    thresholds: dict[tuple[str, str], float | None] = {}
    for frequency in FREQUENCIES:
        for length in LENGTHS:
            values = [
                float(value)
                for row in rows
                if row.frequency_tag == frequency
                and row.length_tag == length
                and not row.is_error
                and (value := value_getter(row)) is not None
            ]
            cleaned[(frequency, length)], thresholds[(frequency, length)] = _filter_upper_percentile(values)
    return cleaned, thresholds


async def build_summary(session: AsyncSession, session_id: uuid.UUID) -> AuditSummary:
    audit_row = (
        await session.execute(
            select(AuditSession, Target.name, Dataset.name)
            .join(Target, Target.id == AuditSession.target_id)
            .join(Dataset, Dataset.id == AuditSession.dataset_id)
            .where(AuditSession.id == session_id)
        )
    ).one_or_none()
    if audit_row is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    audit, target_name, dataset_name = audit_row
    rows = (
        await session.execute(
            select(AuditResult)
            .where(AuditResult.session_id == session_id)
            .order_by(AuditResult.request_index)
        )
    ).scalars().all()

    cleaned_ttfb, ttfb_thresholds = _clean_values_by_cell(rows, lambda row: row.ttfb_ms)
    cleaned_full, _ = _clean_values_by_cell(rows, lambda row: row.full_response_ms)
    outlier_indexes = {
        row.request_index
        for row in rows
        if not row.is_error
        and row.ttfb_ms is not None
        and (
            threshold := ttfb_thresholds.get((row.frequency_tag, row.length_tag))
        ) is not None
        and row.ttfb_ms > threshold
    }

    by_frequency_length: list[GroupStats] = []
    for frequency in FREQUENCIES:
        for length in LENGTHS:
            cell_rows = [row for row in rows if row.frequency_tag == frequency and row.length_tag == length]
            values = cleaned_ttfb[(frequency, length)]
            successful_count = sum(1 for row in cell_rows if not row.is_error and row.ttfb_ms is not None)
            by_frequency_length.append(
                _group_stats(
                    cell_rows,
                    values,
                    frequency=frequency,
                    length=length,
                    outlier_count=successful_count - len(values),
                    p99_threshold_ms=ttfb_thresholds[(frequency, length)],
                )
            )

    values_by_group = {
        frequency: [
            value
            for length in LENGTHS
            for value in cleaned_ttfb[(frequency, length)]
        ]
        for frequency in FREQUENCIES
    }
    groups = [
        _group_stats(
            [row for row in rows if row.frequency_tag == frequency],
            values_by_group[frequency],
            frequency=frequency,
            outlier_count=sum(
                group.outlier_count
                for group in by_frequency_length
                if group.frequency == frequency
            ),
        )
        for frequency in FREQUENCIES
    ]
    by_length = [
        _group_stats(
            [row for row in rows if row.length_tag == length],
            [
                value
                for frequency in FREQUENCIES
                for value in cleaned_ttfb[(frequency, length)]
            ],
            length=length,
            outlier_count=sum(
                group.outlier_count
                for group in by_frequency_length
                if group.length == length
            ),
        )
        for length in LENGTHS
    ]
    all_cleaned_ttfb = [
        value
        for frequency in FREQUENCIES
        for length in LENGTHS
        for value in cleaned_ttfb[(frequency, length)]
    ]
    all_cleaned_full = [
        value
        for frequency in FREQUENCIES
        for length in LENGTHS
        for value in cleaned_full[(frequency, length)]
    ]
    overall = _group_stats(rows, all_cleaned_ttfb, outlier_count=len(outlier_indexes))
    overall_full_response = _group_stats(
        rows,
        all_cleaned_full,
        outlier_count=sum(
            1
            for row in rows
            if not row.is_error and row.full_response_ms is not None
        ) - len(all_cleaned_full),
    )

    comparisons: list[ComparisonStats] = []
    for a, b in itertools.combinations(FREQUENCIES, 2):
        va, vb = values_by_group[a], values_by_group[b]
        p_value = effect_size = mean_diff = median_diff = None
        if len(va) >= 2 and len(vb) >= 2:
            mean_diff = float(np.mean(vb) - np.mean(va))
            median_diff = float(np.median(vb) - np.median(va))
            p_value = float(stats.ttest_ind(va, vb, equal_var=False).pvalue)
            pooled = np.sqrt((np.var(va) + np.var(vb)) / 2)
            effect_size = float((np.mean(vb) - np.mean(va)) / pooled) if pooled > 0 else None
        comparisons.append(
            ComparisonStats(
                group_a=a,
                group_b=b,
                mean_difference_ms=mean_diff,
                median_difference_ms=median_diff,
                p_value=p_value,
                effect_size=effect_size,
                evidence=_evidence(p_value, effect_size, len(va), len(vb)),
            )
        )

    duration_seconds = None
    if audit.started_at and audit.completed_at:
        duration_seconds = (audit.completed_at - audit.started_at).total_seconds()
    error_requests = sum(1 for row in rows if row.is_error)
    points = [
        AnalysisPoint(
            request_index=row.request_index,
            frequency=row.frequency_tag,
            length=row.length_tag,
            ttfb_ms=float(row.ttfb_ms),
            full_response_ms=float(row.full_response_ms) if row.full_response_ms is not None else None,
            is_outlier=row.request_index in outlier_indexes,
        )
        for row in rows
        if not row.is_error and row.ttfb_ms is not None
    ]
    return AuditSummary(
        session_id=session_id,
        metric="ttfb_ms",
        metadata=AuditSummaryMetadata(
            target_id=audit.target_id,
            target_name=target_name,
            dataset_id=audit.dataset_id,
            dataset_name=dataset_name,
            status=audit.status,
            random_seed=audit.random_seed,
            calibration_requests=audit.calibration_requests,
            total_requests=len(rows),
            successful_requests=len(rows) - error_requests,
            error_requests=error_requests,
            started_at=audit.started_at,
            completed_at=audit.completed_at,
            duration_seconds=duration_seconds,
        ),
        overall=overall,
        overall_full_response=overall_full_response,
        groups=groups,
        by_length=by_length,
        by_frequency_length=by_frequency_length,
        comparisons=comparisons,
        points=points,
    )
