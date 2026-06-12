import csv
import io
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditResult
from app.services.statistics_service import build_summary


async def export_results_csv(session: AsyncSession, session_id: uuid.UUID) -> str:
    summary = await build_summary(session, session_id)
    rows = (await session.execute(select(AuditResult).where(AuditResult.session_id == session_id).order_by(AuditResult.request_index))).scalars().all()
    outlier_indexes = {point.request_index for point in summary.points if point.is_outlier}
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "session_id",
        "target_name",
        "dataset_name",
        "audit_status",
        "random_seed",
        "calibration_requests",
        "audit_started_at",
        "audit_completed_at",
        "audit_duration_seconds",
        "request_index",
        "query_text",
        "query_length_chars",
        "frequency_tag",
        "length_tag",
        "latency_ms",
        "ttfb_ms",
        "full_response_ms",
        "status_code",
        "response_size_bytes",
        "is_error",
        "error_type",
        "error_message",
        "is_p99_outlier",
        "timestamp",
    ])
    for row in rows:
        writer.writerow([
            summary.session_id,
            summary.metadata.target_name,
            summary.metadata.dataset_name,
            summary.metadata.status,
            summary.metadata.random_seed,
            summary.metadata.calibration_requests,
            summary.metadata.started_at.isoformat() if summary.metadata.started_at else None,
            summary.metadata.completed_at.isoformat() if summary.metadata.completed_at else None,
            summary.metadata.duration_seconds,
            row.request_index,
            row.query_text,
            len(row.query_text),
            row.frequency_tag,
            row.length_tag,
            row.latency_ms,
            row.ttfb_ms,
            row.full_response_ms,
            row.status_code,
            row.response_size_bytes,
            row.is_error,
            row.error_type,
            row.error_message,
            row.request_index in outlier_indexes,
            row.timestamp.isoformat(),
        ])
    return output.getvalue()


async def export_summary_csv(session: AsyncSession, session_id: uuid.UUID) -> str:
    summary = await build_summary(session, session_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "session_id",
        "target_name",
        "dataset_name",
        "random_seed",
        "audit_duration_seconds",
        "frequency",
        "length",
        "raw_count",
        "filtered_sample_size",
        "error_count",
        "filtered_outliers",
        "mean_ttfb_ms",
        "median_ttfb_ms",
        "std_ttfb_ms",
        "p25_ttfb_ms",
        "p75_ttfb_ms",
        "p95_ttfb_ms",
        "min_ttfb_ms",
        "max_ttfb_ms",
        "p99_filter_threshold_ms",
        "error_rate",
    ])
    for group in summary.by_frequency_length:
        writer.writerow([
            summary.session_id,
            summary.metadata.target_name,
            summary.metadata.dataset_name,
            summary.metadata.random_seed,
            summary.metadata.duration_seconds,
            group.frequency,
            group.length,
            group.raw_count,
            group.count,
            group.error_count,
            group.outlier_count,
            group.mean_ms,
            group.median_ms,
            group.std_ms,
            group.p25_ms,
            group.p75_ms,
            group.p95_ms,
            group.min_ms,
            group.max_ms,
            group.p99_threshold_ms,
            group.error_rate,
        ])
    return output.getvalue()
