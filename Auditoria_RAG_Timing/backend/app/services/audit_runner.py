import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.audit import AuditResult, AuditSession
from app.models.dataset import Dataset
from app.models.target import Target
from app.services.dataset_service import load_dataset_file
from app.services.http_measurement import create_http_client, measure_target


async def run_audit_job(ctx, session_id: str) -> None:
    async with AsyncSessionLocal() as session:
        await run_audit(session, uuid.UUID(session_id))


async def run_audit(session: AsyncSession, session_id: uuid.UUID) -> None:
    audit = await session.get(AuditSession, session_id)
    if audit is None:
        return
    if audit.status == "ABORT_REQUESTED":
        audit.status = "ABORTED"
        audit.completed_at = datetime.now(timezone.utc)
        await session.commit()
        return

    target = await session.get(Target, audit.target_id)
    dataset = await session.get(Dataset, audit.dataset_id)
    if target is None or dataset is None:
        audit.status = "FAILED"
        audit.error_message = "Target or dataset not found"
        audit.completed_at = datetime.now(timezone.utc)
        await session.commit()
        return

    queries = load_dataset_file(dataset.file_path)
    rng = random.Random(audit.random_seed)
    rng.shuffle(queries)

    audit.status = "RUNNING"
    audit.started_at = datetime.now(timezone.utc)
    audit.progress_total = len(queries)
    audit.progress_current = 0
    await session.commit()

    try:
        async with create_http_client(target) as client:
            calibration_ok = 0
            for _ in range(audit.calibration_requests):
                result = await measure_target(client, target, f"warm-up-{uuid.uuid4()}")
                if not result.is_error:
                    calibration_ok += 1
            if calibration_ok == 0:
                audit.status = "FAILED"
                audit.error_message = "Calibration failed completely"
                audit.completed_at = datetime.now(timezone.utc)
                await session.commit()
                return

            consecutive_errors = 0
            for index, query in enumerate(queries, start=1):
                await session.refresh(audit)
                if audit.status == "ABORT_REQUESTED":
                    audit.status = "ABORTED"
                    audit.completed_at = datetime.now(timezone.utc)
                    await session.commit()
                    return

                measurement = await measure_target(client, target, query.query)
                consecutive_errors = consecutive_errors + 1 if measurement.is_error else 0
                session.add(
                    AuditResult(
                        session_id=audit.id,
                        request_index=index,
                        query_text=query.query,
                        frequency_tag=query.frequency,
                        length_tag=query.length,
                        latency_ms=measurement.latency_ms,
                        ttfb_ms=measurement.ttfb_ms,
                        full_response_ms=measurement.full_response_ms,
                        status_code=measurement.status_code,
                        response_size_bytes=measurement.response_size_bytes,
                        is_error=measurement.is_error,
                        error_type=measurement.error_type,
                        error_message=measurement.error_message,
                    )
                )
                audit.progress_current = index
                if index % 10 == 0:
                    await session.commit()
                if consecutive_errors >= 20:
                    audit.status = "FAILED"
                    audit.error_message = "20 consecutive request errors"
                    audit.completed_at = datetime.now(timezone.utc)
                    await session.commit()
                    return
        audit.status = "COMPLETED"
        audit.completed_at = datetime.now(timezone.utc)
        await session.commit()
    except Exception as exc:
        audit.status = "FAILED"
        audit.error_message = str(exc)
        audit.completed_at = datetime.now(timezone.utc)
        await session.commit()
