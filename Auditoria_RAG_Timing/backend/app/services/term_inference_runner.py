import asyncio
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.target import Target
from app.models.term_inference import (
    TermInferenceMeasurement,
    TermInferenceResult,
    TermInferenceSession,
)
from app.services.http_measurement import create_http_client, measure_target
from app.services.term_inference_service import (
    CalibrationProfile,
    build_probe_batch,
    classify_term,
)

HEALTH_CONTROL_COUNT = 5
HEALTH_CHECK_TOTAL_PROBES = 5


async def run_term_inference_job(ctx, session_id: str) -> None:
    async with AsyncSessionLocal() as session:
        await run_term_inference(session, uuid.UUID(session_id))


async def run_term_inference(session: AsyncSession, session_id: uuid.UUID) -> None:
    inference = await session.get(TermInferenceSession, session_id)
    if inference is None:
        return
    if inference.status == "ABORT_REQUESTED":
        inference.status = "ABORTED"
        inference.completed_at = datetime.now(timezone.utc)
        await session.commit()
        return

    target = await session.get(Target, inference.target_id)
    if target is None:
        inference.status = "FAILED"
        inference.error_message = "Target not found"
        inference.completed_at = datetime.now(timezone.utc)
        await session.commit()
        return

    payload = inference.terms_payload
    terms = list(payload.get("terms", []))
    controls = list(payload.get("negative_controls", []))[:HEALTH_CONTROL_COUNT]
    all_terms = terms + controls
    profile = CalibrationProfile.from_dict(inference.calibration_profile)
    rng = random.Random(inference.random_seed)

    inference.status = "RUNNING"
    inference.started_at = datetime.now(timezone.utc)
    inference.progress_current = 0
    inference.progress_total = (
        len(terms) * inference.max_probes_per_term
        + len(controls) * inference.probes_per_round
        + (inference.max_probes_per_term if terms and controls else 0)
    )
    await session.commit()

    results = await _ensure_results(session, inference.id, terms, controls)
    probe_indexes = {term: 0 for term in all_terms}
    request_index = 0
    active_terms = terms.copy()

    try:
        async with create_http_client(target) as client:
            if controls:
                control_batch = build_probe_batch(
                    controls,
                    probe_indexes,
                    HEALTH_CHECK_TOTAL_PROBES,
                    rng,
                    max_total_probes=HEALTH_CHECK_TOTAL_PROBES,
                )
                request_index, aborted = await _execute_batch(
                    session,
                    inference,
                    results,
                    client,
                    target,
                    control_batch,
                    request_index,
                    round_number=0,
                )
                if aborted:
                    return
                await _update_result_stats(session, results, controls, profile, final=True)
                await _update_health_warning(inference, results, controls)
                await session.commit()

            round_number = 1
            while active_terms:
                if await _abort_requested(session, inference.id):
                    await _mark_aborted(session, inference)
                    return

                batch_terms = [
                    term
                    for term in active_terms
                    if probe_indexes[term] < inference.max_probes_per_term
                ]
                if not batch_terms:
                    break
                batch = build_probe_batch(
                    batch_terms,
                    probe_indexes,
                    inference.probes_per_round,
                    rng,
                    inference.max_probes_per_term,
                    controls,
                )
                request_index, aborted = await _execute_batch(
                    session,
                    inference,
                    results,
                    client,
                    target,
                    batch,
                    request_index,
                    round_number=round_number,
                )
                if aborted:
                    return
                await _update_result_stats(
                    session,
                    results,
                    batch_terms,
                    profile,
                    final=False,
                    min_valid_measurements=inference.probes_per_round,
                )
                await _update_result_stats(session, results, controls, profile, final=True)
                active_terms = [
                    term
                    for term in active_terms
                    if results[term].classification == "inconclusive"
                    and probe_indexes[term] < inference.max_probes_per_term
                ]
                round_number += 1
                await session.commit()

            await _finalize_remaining(session, results, terms, profile)
            await _update_result_stats(session, results, controls, profile, final=True)
        if await _abort_requested(session, inference.id):
            await _mark_aborted(session, inference)
            return
        final_progress = await _measurement_count(session, inference.id)
        inference.progress_current = final_progress
        inference.progress_total = final_progress
        inference.status = "COMPLETED"
        inference.completed_at = datetime.now(timezone.utc)
        await session.commit()
    except asyncio.CancelledError:
        inference.status = "FAILED"
        inference.error_message = "Term inference worker was cancelled or exceeded its execution timeout"
        inference.completed_at = datetime.now(timezone.utc)
        await session.commit()
        raise
    except Exception as exc:
        inference.status = "FAILED"
        inference.error_message = str(exc)
        inference.completed_at = datetime.now(timezone.utc)
        await session.commit()


async def _ensure_results(
    session: AsyncSession,
    session_id: uuid.UUID,
    terms: list[str],
    controls: list[str],
) -> dict[str, TermInferenceResult]:
    existing = (
        await session.execute(select(TermInferenceResult).where(TermInferenceResult.session_id == session_id))
    ).scalars().all()
    results = {result.term: result for result in existing}
    for term in terms:
        if term not in results:
            result = TermInferenceResult(session_id=session_id, term=term, is_control=False)
            session.add(result)
            results[term] = result
    for term in controls:
        if term not in results:
            result = TermInferenceResult(session_id=session_id, term=term, is_control=True)
            session.add(result)
            results[term] = result
    await session.flush()
    return results


async def _execute_batch(
    session: AsyncSession,
    inference: TermInferenceSession,
    results: dict[str, TermInferenceResult],
    client,
    target: Target,
    batch: list[tuple[str, str]],
    request_index: int,
    round_number: int,
) -> tuple[int, bool]:
    for term, query_text in batch:
        if await _abort_requested(session, inference.id):
            await _mark_aborted(session, inference)
            return request_index, True

        request_index += 1
        measurement = await measure_target(client, target, query_text)
        session.add(
            TermInferenceMeasurement(
                result_id=results[term].id,
                request_index=request_index,
                round_number=round_number,
                query_text=query_text,
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
        inference.progress_current += 1
        if request_index % 10 == 0:
            await session.commit()
    return request_index, False


async def _abort_requested(session: AsyncSession, inference_id: uuid.UUID) -> bool:
    await session.flush()
    status = await session.scalar(
        select(TermInferenceSession.status).where(TermInferenceSession.id == inference_id)
    )
    return status == "ABORT_REQUESTED"


async def _mark_aborted(session: AsyncSession, inference: TermInferenceSession) -> None:
    final_progress = await _measurement_count(session, inference.id)
    inference.progress_current = final_progress
    inference.progress_total = final_progress
    inference.status = "ABORTED"
    inference.completed_at = datetime.now(timezone.utc)
    await session.commit()


async def _measurement_count(session: AsyncSession, inference_id: uuid.UUID) -> int:
    await session.flush()
    count = await session.scalar(
        select(func.count(TermInferenceMeasurement.id))
        .join(TermInferenceResult, TermInferenceResult.id == TermInferenceMeasurement.result_id)
        .where(TermInferenceResult.session_id == inference_id)
    )
    return int(count or 0)


async def _update_result_stats(
    session: AsyncSession,
    results: dict[str, TermInferenceResult],
    terms: list[str],
    profile: CalibrationProfile,
    *,
    final: bool,
    min_valid_measurements: int = 1,
) -> None:
    for term in terms:
        result = results[term]
        measurements = (
            await session.execute(
                select(TermInferenceMeasurement).where(TermInferenceMeasurement.result_id == result.id)
            )
        ).scalars().all()
        values = [float(item.ttfb_ms) for item in measurements if not item.is_error and item.ttfb_ms is not None]
        classification, mean, std, distance, closest = classify_term(values, profile)
        if len(values) < min_valid_measurements and not final:
            classification = "inconclusive"
        result.classification = classification if final or classification != "inconclusive" else "inconclusive"
        result.observed_mean_ttfb_ms = mean
        result.observed_std_ttfb_ms = std
        result.valid_measurements = len(values)
        result.total_measurements = len(measurements)
        result.distance_to_threshold_ms = distance
        result.closest_reference = closest
        result.error_count = sum(1 for item in measurements if item.is_error)


async def _finalize_remaining(
    session: AsyncSession,
    results: dict[str, TermInferenceResult],
    terms: list[str],
    profile: CalibrationProfile,
) -> None:
    await _update_result_stats(session, results, terms, profile, final=True)
    for term in terms:
        if results[term].classification is None:
            results[term].classification = "inconclusive"


async def _update_health_warning(
    inference: TermInferenceSession,
    results: dict[str, TermInferenceResult],
    controls: list[str],
) -> None:
    if not controls:
        return
    unexpected = [
        term
        for term in controls
        if results[term].classification == "likely_present"
    ]
    if unexpected:
        inference.warning_message = (
            "Some negative controls behaved like present terms. "
            "Classification confidence may be reduced."
        )
