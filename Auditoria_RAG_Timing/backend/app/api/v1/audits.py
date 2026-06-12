import uuid

from arq import create_pool
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.audit import AuditResult, AuditSession
from app.models.dataset import Dataset
from app.models.target import Target
from app.schemas.audit import (
    AuditDashboardItem,
    AuditSessionRead,
    AuditStartRequest,
    AuditStartResponse,
    AuditStatus,
    ResultsPage,
)
from app.services.export_service import export_results_csv, export_summary_csv
from app.services.statistics_service import build_summary
from app.workers.arq_worker import redis_settings_from_url
from app.core.config import settings

router = APIRouter(prefix="/audits", tags=["audits"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[AuditSessionRead])
async def list_audits(session: AsyncSession = Depends(get_session)) -> list[AuditSession]:
    return (await session.execute(select(AuditSession).order_by(AuditSession.created_at.desc()))).scalars().all()


@router.get("/dashboard", response_model=list[AuditDashboardItem])
async def dashboard_audits(session: AsyncSession = Depends(get_session)) -> list[AuditDashboardItem]:
    rows = (
        await session.execute(
            select(
                AuditSession,
                Target.name,
                Dataset.name,
                func.count(AuditResult.id).filter(AuditResult.is_error.is_(True)),
                func.avg(AuditResult.ttfb_ms).filter(AuditResult.is_error.is_(False)),
                func.avg(AuditResult.full_response_ms).filter(AuditResult.is_error.is_(False)),
            )
            .join(Target, Target.id == AuditSession.target_id)
            .join(Dataset, Dataset.id == AuditSession.dataset_id)
            .outerjoin(AuditResult, AuditResult.session_id == AuditSession.id)
            .group_by(AuditSession.id, Target.name, Dataset.name)
            .order_by(AuditSession.created_at.desc())
        )
    ).all()
    return [
        AuditDashboardItem(
            id=audit.id,
            target_id=audit.target_id,
            target_name=target_name,
            dataset_id=audit.dataset_id,
            dataset_name=dataset_name,
            status=audit.status,
            calibration_requests=audit.calibration_requests,
            progress_current=audit.progress_current,
            progress_total=audit.progress_total,
            random_seed=audit.random_seed,
            error_message=audit.error_message,
            error_count=error_count or 0,
            mean_ttfb_ms=float(mean_ttfb) if mean_ttfb is not None else None,
            mean_full_response_ms=float(mean_full_response) if mean_full_response is not None else None,
            created_at=audit.created_at,
            started_at=audit.started_at,
            completed_at=audit.completed_at,
        )
        for audit, target_name, dataset_name, error_count, mean_ttfb, mean_full_response in rows
    ]


@router.post("/start", response_model=AuditStartResponse)
async def start_audit(payload: AuditStartRequest, session: AsyncSession = Depends(get_session)) -> AuditStartResponse:
    target = await session.get(Target, payload.target_id)
    dataset = await session.get(Dataset, payload.dataset_id)
    if not target or not dataset:
        raise HTTPException(status_code=404, detail="Target or dataset not found")
    audit = AuditSession(
        target_id=payload.target_id,
        dataset_id=payload.dataset_id,
        status="PENDING",
        calibration_requests=payload.calibration_requests,
        progress_total=dataset.total_queries,
        random_seed=payload.random_seed,
    )
    session.add(audit)
    await session.commit()
    await session.refresh(audit)
    redis = await create_pool(redis_settings_from_url(settings.redis_url))
    try:
        await redis.enqueue_job("run_audit_job", str(audit.id))
    finally:
        await redis.aclose()
    return AuditStartResponse(session_id=audit.id)


@router.get("/{audit_id}", response_model=AuditSessionRead)
async def get_audit(audit_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> AuditSession:
    audit = await session.get(AuditSession, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    return audit


@router.get("/{audit_id}/status", response_model=AuditStatus)
async def get_status(audit_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> AuditStatus:
    audit = await session.get(AuditSession, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    metrics = (
        await session.execute(
            select(
                func.count().filter(AuditResult.is_error.is_(True)),
                func.avg(AuditResult.ttfb_ms).filter(AuditResult.is_error.is_(False)),
                func.avg(AuditResult.full_response_ms).filter(AuditResult.is_error.is_(False)),
            ).where(AuditResult.session_id == audit_id)
        )
    ).one()
    return AuditStatus(
        id=audit.id,
        status=audit.status,
        progress_current=audit.progress_current,
        progress_total=audit.progress_total,
        error_message=audit.error_message,
        error_count=metrics[0] or 0,
        mean_ttfb_ms=float(metrics[1]) if metrics[1] is not None else None,
        mean_full_response_ms=float(metrics[2]) if metrics[2] is not None else None,
    )


@router.post("/{audit_id}/abort")
async def abort_audit(audit_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict[str, bool]:
    audit = await session.get(AuditSession, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.status in {"PENDING", "RUNNING"}:
        audit.status = "ABORT_REQUESTED"
        await session.commit()
    return {"ok": True}


@router.delete("/{audit_id}")
async def delete_audit(audit_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict[str, bool]:
    audit = await session.get(AuditSession, audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.status in {"PENDING", "RUNNING", "ABORT_REQUESTED"}:
        raise HTTPException(status_code=409, detail="Cannot delete an audit while it is running or queued")
    await session.delete(audit)
    await session.commit()
    return {"ok": True}


@router.get("/{audit_id}/results", response_model=ResultsPage)
async def get_results(
    audit_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    frequency: str | None = None,
    length: str | None = None,
    is_error: bool | None = None,
    status_code: int | None = None,
    session: AsyncSession = Depends(get_session),
) -> ResultsPage:
    query = select(AuditResult).where(AuditResult.session_id == audit_id)
    count_query = select(func.count()).select_from(AuditResult).where(AuditResult.session_id == audit_id)
    for attr, value in [
        (AuditResult.frequency_tag, frequency),
        (AuditResult.length_tag, length),
        (AuditResult.is_error, is_error),
        (AuditResult.status_code, status_code),
    ]:
        if value is not None:
            query = query.where(attr == value)
            count_query = count_query.where(attr == value)
    total = (await session.execute(count_query)).scalar_one()
    rows = (await session.execute(query.order_by(AuditResult.request_index).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return ResultsPage(total=total, page=page, page_size=page_size, items=rows)


@router.get("/{audit_id}/summary")
async def get_summary(audit_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    return await build_summary(session, audit_id)


@router.get("/{audit_id}/export.csv")
async def export_csv(audit_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Response:
    content = await export_results_csv(session, audit_id)
    return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=audit_{audit_id}.csv"})


@router.get("/{audit_id}/export-summary.csv")
async def export_summary(audit_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Response:
    content = await export_summary_csv(session, audit_id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=audit_{audit_id}_summary.csv"},
    )
