import csv
import io
import json
import uuid

from arq import create_pool
from fastapi import APIRouter, Depends, HTTPException, Request, Response
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


@router.get("", response_model=list[TermInferenceListItem])
async def list_term_inferences(session: AsyncSession = Depends(get_session)) -> list[TermInferenceListItem]:
    rows = (
        await session.execute(
            select(TermInferenceSession, Target.name, func.count(TermInferenceResult.id))
            .join(Target, Target.id == TermInferenceSession.target_id)
            .outerjoin(TermInferenceResult, TermInferenceResult.session_id == TermInferenceSession.id)
            .group_by(TermInferenceSession.id, Target.name)
            .order_by(TermInferenceSession.created_at.desc())
        )
    ).all()
    return [
        TermInferenceListItem(
            **TermInferenceSessionRead.model_validate(inference).model_dump(),
            target_name=target_name,
            result_count=result_count or 0,
        )
        for inference, target_name, result_count in rows
    ]


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
        initial_probes_per_term=payload["initial_probes_per_term"],
        additional_probes_per_round=payload["additional_probes_per_round"],
        max_probes_per_term=payload["max_probes_per_term"],
        calibration_health_controls=payload["calibration_health_controls"],
        progress_total=len(terms_payload["terms"]) * payload["max_probes_per_term"]
        + min(len(terms_payload["negative_controls"]), payload["calibration_health_controls"]) * payload["initial_probes_per_term"],
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
    return TermInferenceStatusRead(
        id=inference.id,
        status=inference.status,
        progress_current=inference.progress_current,
        progress_total=inference.progress_total,
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
    return TermInferenceResultsPage(
        session=TermInferenceSessionRead.model_validate(inference),
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
    source_audit_id = form.get("source_audit_id")
    terms_payload_raw = form.get("terms_payload")
    summary_csv = form.get("summary_csv")
    if isinstance(terms_payload_raw, str):
        try:
            terms_payload = TermsPayload.model_validate(json.loads(terms_payload_raw))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="terms_payload must contain valid JSON") from exc
    else:
        raise HTTPException(status_code=422, detail="terms_payload is required")
    random_seed = form.get("random_seed")
    initial_probes = form.get("initial_probes_per_term")
    additional_probes = form.get("additional_probes_per_round")
    max_probes = form.get("max_probes_per_term")
    health_controls = form.get("calibration_health_controls")
    return {
        "target_id": uuid.UUID(str(form["target_id"])),
        "source_audit_id": uuid.UUID(str(source_audit_id)) if source_audit_id else None,
        "terms_payload": terms_payload,
        "random_seed": int(random_seed) if random_seed not in (None, "") else TermInferenceJsonStart.model_fields["random_seed"].default_factory(),
        "initial_probes_per_term": int(initial_probes) if initial_probes not in (None, "") else TermInferenceJsonStart.model_fields["initial_probes_per_term"].default,
        "additional_probes_per_round": int(additional_probes) if additional_probes not in (None, "") else TermInferenceJsonStart.model_fields["additional_probes_per_round"].default,
        "max_probes_per_term": int(max_probes) if max_probes not in (None, "") else TermInferenceJsonStart.model_fields["max_probes_per_term"].default,
        "calibration_health_controls": int(health_controls) if health_controls not in (None, "") else TermInferenceJsonStart.model_fields["calibration_health_controls"].default,
        "summary_csv": summary_csv if isinstance(summary_csv, StarletteUploadFile) else None,
    }
