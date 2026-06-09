import csv
import io
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditResult, AuditSession


async def export_results_csv(session: AsyncSession, session_id: uuid.UUID) -> str:
    rows = (await session.execute(select(AuditResult).where(AuditResult.session_id == session_id).order_by(AuditResult.request_index))).scalars().all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "request_index",
        "query_text",
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
        "timestamp",
    ])
    for row in rows:
        writer.writerow([
            row.request_index,
            row.query_text,
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
            row.timestamp.isoformat(),
        ])
    return output.getvalue()


async def export_results_json(session: AsyncSession, session_id: uuid.UUID) -> str:
    audit = await session.get(AuditSession, session_id)
    rows = (await session.execute(select(AuditResult).where(AuditResult.session_id == session_id).order_by(AuditResult.request_index))).scalars().all()
    payload = {
        "session": {
            "id": str(audit.id),
            "target_id": str(audit.target_id),
            "dataset_id": str(audit.dataset_id),
            "status": audit.status,
            "random_seed": audit.random_seed,
        } if audit else None,
        "results": [
            {
                "request_index": row.request_index,
                "query_text": row.query_text,
                "frequency_tag": row.frequency_tag,
                "length_tag": row.length_tag,
                "latency_ms": row.latency_ms,
                "ttfb_ms": row.ttfb_ms,
                "full_response_ms": row.full_response_ms,
                "status_code": row.status_code,
                "response_size_bytes": row.response_size_bytes,
                "is_error": row.is_error,
                "error_type": row.error_type,
                "error_message": row.error_message,
                "timestamp": row.timestamp.isoformat(),
            }
            for row in rows
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
