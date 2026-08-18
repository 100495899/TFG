import csv
import io
import json
import uuid

from arq import create_pool
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_session
from app.models.target import Target
from app.models.term_inference import (
    TermInferenceMeasurement,
    TermInferenceResult,
    TermInferenceSession,
)
from app.schemas.term_inference import (
    TermInferenceMeasurementRead,
    TermInferenceJsonStart,
    TermInferenceListItem,
    TermInferenceResultRead,
    TermInferenceResultsPage,
    TermInferenceSessionRead,
    TermInferenceStartResponse,
    TermInferenceStatusRead,
    TermsPayload,
)
from app.services.term_inference_service import (
    normalize_terms_payload,
    profile_from_audit,
    profile_from_summary_csv,
)
from app.workers.arq_worker import redis_settings_from_url

router = APIRouter(prefix="/term-inference", tags=["term-inference"], dependencies=[Depends(get_current_user)])
TERM_INFERENCE_HEALTH_CONTROLS = 5
TERM_INFERENCE_HEALTH_CHECK_TOTAL_PROBES = 5
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "ABORTED"}


@router.get("", response_model=list[TermInferenceListItem])
async def list_term_inferences(session: AsyncSession = Depends(get_session)) -> list[TermInferenceListItem]:
    rows = (
        await session.execute(
            select(
                TermInferenceSession,
                Target.name,
                func.count(func.distinct(TermInferenceResult.id)),
                func.count(TermInferenceMeasurement.id),
            )
            .join(Target, Target.id == TermInferenceSession.target_id)
            .outerjoin(TermInferenceResult, TermInferenceResult.session_id == TermInferenceSession.id)
            .outerjoin(TermInferenceMeasurement, TermInferenceMeasurement.result_id == TermInferenceResult.id)
            .group_by(TermInferenceSession.id, Target.name)
            .order_by(TermInferenceSession.created_at.desc())
        )
    ).all()
    items: list[TermInferenceListItem] = []
    for inference, target_name, result_count, measurement_count in rows:
        data = TermInferenceSessionRead.model_validate(inference).model_dump()
        if inference.status in TERMINAL_STATUSES:
            data["progress_current"] = int(measurement_count or 0)
            data["progress_total"] = int(measurement_count or 0)
        items.append(
            TermInferenceListItem(
                **data,
                target_name=target_name,
                result_count=result_count or 0,
            )
        )
    return items


@router.post("/start", response_model=TermInferenceStartResponse)
async def start_term_inference(request: Request, session: AsyncSession = Depends(get_session)) -> TermInferenceStartResponse:
    payload = await _parse_start_request(request)
    target = await session.get(Target, payload["target_id"])
    if target is None:
        raise HTTPException(status_code=404, detail="Target not found")

    if payload["source_audit_id"] and payload["summary_csv"]:
        raise HTTPException(status_code=422, detail="Use either source_audit_id or summary_csv, not both")
    if not payload["source_audit_id"] and not payload["summary_csv"]:
        raise HTTPException(status_code=422, detail="A calibration source is required")

    if payload["source_audit_id"]:
        profile = await profile_from_audit(session, payload["source_audit_id"])
        source_type = "audit"
        source_label = profile.source_label
        source_audit_id = payload["source_audit_id"]
    else:
        upload = payload["summary_csv"]
        content = await upload.read()
        profile = profile_from_summary_csv(content, upload.filename or "summary.csv")
        source_type = "summary_csv"
        source_label = upload.filename or "summary.csv"
        source_audit_id = None

    terms_payload = normalize_terms_payload(payload["terms_payload"])
    inference = TermInferenceSession(
        target_id=payload["target_id"],
        source_audit_id=source_audit_id,
        source_type=source_type,
        source_label=source_label,
        status="PENDING",
        calibration_profile=profile.to_dict(),
        terms_payload=terms_payload,
        random_seed=payload["random_seed"],
        probes_per_round=payload["probes_per_round"],
        max_probes_per_term=payload["max_probes_per_term"],
        progress_total=len(terms_payload["terms"]) * payload["max_probes_per_term"]
        + (TERM_INFERENCE_HEALTH_CHECK_TOTAL_PROBES if terms_payload["negative_controls"] else 0)
        + (payload["max_probes_per_term"] if terms_payload["terms"] and terms_payload["negative_controls"] else 0),
    )
    session.add(inference)
    await session.commit()
    await session.refresh(inference)

    redis = await create_pool(redis_settings_from_url(settings.redis_url))
    try:
        await redis.enqueue_job("run_term_inference_job", str(inference.id))
    finally:
        await redis.aclose()
    return TermInferenceStartResponse(session_id=inference.id)


@router.get("/{inference_id}", response_model=TermInferenceSessionRead)
async def get_term_inference(inference_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> TermInferenceSession:
    inference = await session.get(TermInferenceSession, inference_id)
    if not inference:
        raise HTTPException(status_code=404, detail="Term inference not found")
    return inference


@router.get("/{inference_id}/status", response_model=TermInferenceStatusRead)
async def get_term_inference_status(inference_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> TermInferenceStatusRead:
    inference = await session.get(TermInferenceSession, inference_id)
    if not inference:
        raise HTTPException(status_code=404, detail="Term inference not found")
    progress_current = inference.progress_current
    progress_total = inference.progress_total
    if inference.status in TERMINAL_STATUSES:
        measurement_count = await _measurement_count(session, inference_id)
        progress_current = measurement_count
        progress_total = measurement_count
    return TermInferenceStatusRead(
        id=inference.id,
        status=inference.status,
        progress_current=progress_current,
        progress_total=progress_total,
        warning_message=inference.warning_message,
        error_message=inference.error_message,
    )


@router.post("/{inference_id}/abort")
async def abort_term_inference(inference_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict[str, bool]:
    inference = await session.get(TermInferenceSession, inference_id)
    if not inference:
        raise HTTPException(status_code=404, detail="Term inference not found")
    if inference.status in {"PENDING", "RUNNING"}:
        inference.status = "ABORT_REQUESTED"
        await session.commit()
    return {"ok": True}


@router.delete("/{inference_id}")
async def delete_term_inference(inference_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict[str, bool]:
    inference = await session.get(TermInferenceSession, inference_id)
    if not inference:
        raise HTTPException(status_code=404, detail="Term inference not found")
    if inference.status in {"PENDING", "RUNNING", "ABORT_REQUESTED"}:
        raise HTTPException(status_code=409, detail="Cannot delete a term inference session while it is running or queued")
    await session.delete(inference)
    await session.commit()
    return {"ok": True}


@router.get("/{inference_id}/results", response_model=TermInferenceResultsPage)
async def get_term_inference_results(inference_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> TermInferenceResultsPage:
    inference = await session.get(TermInferenceSession, inference_id)
    if not inference:
        raise HTTPException(status_code=404, detail="Term inference not found")
    results = (
        await session.execute(
            select(TermInferenceResult)
            .where(TermInferenceResult.session_id == inference_id)
            .order_by(TermInferenceResult.is_control, TermInferenceResult.term)
        )
    ).scalars().all()
    measurements = (
        await session.execute(
            select(TermInferenceMeasurement)
            .join(TermInferenceResult, TermInferenceResult.id == TermInferenceMeasurement.result_id)
            .where(TermInferenceResult.session_id == inference_id)
            .order_by(TermInferenceMeasurement.request_index)
        )
    ).scalars().all()
    session_read = TermInferenceSessionRead.model_validate(inference)
    if inference.status in TERMINAL_STATUSES:
        session_read = session_read.model_copy(
            update={
                "progress_current": len(measurements),
                "progress_total": len(measurements),
            }
        )
    return TermInferenceResultsPage(
        session=session_read,
        profile=inference.calibration_profile,
        results=[TermInferenceResultRead.model_validate(result) for result in results],
        measurements=[TermInferenceMeasurementRead.model_validate(measurement) for measurement in measurements],
    )


@router.get("/{inference_id}/export.csv")
async def export_term_inference_csv(inference_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Response:
    inference = await session.get(TermInferenceSession, inference_id)
    if not inference:
        raise HTTPException(status_code=404, detail="Term inference not found")
    results = (
        await session.execute(
            select(TermInferenceResult)
            .where(TermInferenceResult.session_id == inference_id)
            .order_by(TermInferenceResult.is_control, TermInferenceResult.term)
        )
    ).scalars().all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "session_id",
        "target_id",
        "source_type",
        "source_label",
        "term",
        "is_control",
        "classification",
        "observed_mean_ttfb_ms",
        "observed_std_ttfb_ms",
        "valid_measurements",
        "total_measurements",
        "distance_to_threshold_ms",
        "closest_reference",
        "error_count",
    ])
    for result in results:
        writer.writerow([
            inference.id,
            inference.target_id,
            inference.source_type,
            inference.source_label,
            result.term,
            result.is_control,
            result.classification,
            result.observed_mean_ttfb_ms,
            result.observed_std_ttfb_ms,
            result.valid_measurements,
            result.total_measurements,
            result.distance_to_threshold_ms,
            result.closest_reference,
            result.error_count,
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=term_inference_{inference_id}.csv"},
    )


async def _parse_start_request(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = TermInferenceJsonStart.model_validate(await request.json())
        return {
            **body.model_dump(),
            "summary_csv": None,
        }

    form = await request.form()
    target_id_raw = form.get("target_id")
    if not target_id_raw:
        raise HTTPException(status_code=422, detail="target_id is required")
    source_audit_id = form.get("source_audit_id")
    terms_payload_raw = form.get("terms_payload")
    summary_csv = form.get("summary_csv")
    if isinstance(terms_payload_raw, str):
        try:
            terms_payload = TermsPayload.model_validate(json.loads(terms_payload_raw))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="terms_payload must contain valid JSON") from exc
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc
    else:
        raise HTTPException(status_code=422, detail="terms_payload is required")
    random_seed = form.get("random_seed")
    probes_per_round = form.get("probes_per_round")
    max_probes = form.get("max_probes_per_term")
    try:
        target_id = uuid.UUID(str(target_id_raw))
        parsed_source_audit_id = uuid.UUID(str(source_audit_id)) if source_audit_id else None
        parsed_random_seed = int(random_seed) if random_seed not in (None, "") else TermInferenceJsonStart.model_fields["random_seed"].default_factory()
        parsed_probes_per_round = int(probes_per_round) if probes_per_round not in (None, "") else TermInferenceJsonStart.model_fields["probes_per_round"].default
        parsed_max_probes = int(max_probes) if max_probes not in (None, "") else TermInferenceJsonStart.model_fields["max_probes_per_term"].default
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Term inference form contains invalid identifiers or numeric values") from exc
    if not 1 <= parsed_random_seed <= 2_147_483_647:
        raise HTTPException(status_code=422, detail="random_seed must be between 1 and 2147483647")
    if not 1 <= parsed_probes_per_round <= 30:
        raise HTTPException(status_code=422, detail="probes_per_round must be between 1 and 30")
    if not 1 <= parsed_max_probes <= 100:
        raise HTTPException(status_code=422, detail="max_probes_per_term must be between 1 and 100")
    return {
        "target_id": target_id,
        "source_audit_id": parsed_source_audit_id,
        "terms_payload": terms_payload,
        "random_seed": parsed_random_seed,
        "probes_per_round": parsed_probes_per_round,
        "max_probes_per_term": parsed_max_probes,
        "summary_csv": summary_csv if isinstance(summary_csv, StarletteUploadFile) else None,
    }


async def _measurement_count(session: AsyncSession, inference_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count(TermInferenceMeasurement.id))
        .join(TermInferenceResult, TermInferenceResult.id == TermInferenceMeasurement.result_id)
        .where(TermInferenceResult.session_id == inference_id)
    )
    return int(count or 0)
