import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.audit import AuditSession
from app.models.target import Target
from app.schemas.target import TargetCreate, TargetRead, TargetTestRequest, TargetTestResponse, TargetUpdate
from app.services.http_measurement import create_http_client, measure_target
from app.services.target_service import validate_target_payload

router = APIRouter(prefix="/targets", tags=["targets"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[TargetRead])
async def list_targets(session: AsyncSession = Depends(get_session)) -> list[Target]:
    return (await session.execute(select(Target).order_by(Target.created_at.desc()))).scalars().all()


@router.post("", response_model=TargetRead)
async def create_target(payload: TargetCreate, session: AsyncSession = Depends(get_session)) -> TargetRead:
    validate_target_payload(payload)
    target = Target(
        name=payload.name,
        endpoint_url=payload.endpoint_url,
        headers=payload.headers,
        payload_template=payload.payload_template,
        timeout_seconds=payload.timeout_seconds,
        verify_tls=payload.verify_tls,
    )
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return target


@router.get("/{target_id}", response_model=TargetRead)
async def get_target(target_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Target:
    target = await session.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return target


@router.put("/{target_id}", response_model=TargetRead)
async def update_target(target_id: uuid.UUID, payload: TargetUpdate, session: AsyncSession = Depends(get_session)) -> TargetRead:
    validate_target_payload(payload)
    target = await session.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    target.name = payload.name
    target.endpoint_url = payload.endpoint_url
    target.headers = payload.headers
    target.payload_template = payload.payload_template
    target.timeout_seconds = payload.timeout_seconds
    target.verify_tls = payload.verify_tls
    await session.commit()
    await session.refresh(target)
    return target


@router.delete("/{target_id}")
async def delete_target(target_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict[str, bool]:
    target = await session.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    count = (await session.execute(select(AuditSession).where(AuditSession.target_id == target_id).limit(1))).scalars().first()
    if count:
        raise HTTPException(status_code=409, detail="Target has associated audits")
    await session.delete(target)
    await session.commit()
    return {"ok": True}


@router.post("/{target_id}/test", response_model=TargetTestResponse)
async def test_target(target_id: uuid.UUID, payload: TargetTestRequest, session: AsyncSession = Depends(get_session)) -> TargetTestResponse:
    target = await session.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    async with create_http_client(target) as client:
        result = await measure_target(client, target, payload.query)
    return TargetTestResponse(ok=not result.is_error, **result.__dict__)
