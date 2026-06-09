import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.audit import AuditSession
from app.models.dataset import Dataset
from app.schemas.dataset import DatasetPreview, DatasetRead
from app.services.dataset_service import (
    distribution,
    load_dataset_file,
    parse_dataset_upload,
    save_dataset_file,
)

router = APIRouter(prefix="/datasets", tags=["datasets"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[DatasetRead])
async def list_datasets(session: AsyncSession = Depends(get_session)) -> list[Dataset]:
    return (await session.execute(select(Dataset).order_by(Dataset.created_at.desc()))).scalars().all()


@router.post("/upload", response_model=DatasetRead)
async def upload_dataset(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)) -> Dataset:
    if not file.filename:
        raise HTTPException(status_code=422, detail="El archivo debe tener un nombre.")

    _, content, total_queries = await parse_dataset_upload(file)
    path = save_dataset_file(content, file.filename)
    dataset = Dataset(
        name=os.path.splitext(file.filename)[0],
        file_path=path,
        original_filename=file.filename,
        total_queries=total_queries,
    )
    session.add(dataset)
    await session.commit()
    await session.refresh(dataset)
    return dataset


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(dataset_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Dataset:
    dataset = await session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.get("/{dataset_id}/preview", response_model=DatasetPreview)
async def preview_dataset(dataset_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> DatasetPreview:
    dataset = await session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    queries = load_dataset_file(dataset.file_path)
    return DatasetPreview(dataset=DatasetRead.model_validate(dataset), preview=queries[:20], distribution=distribution(queries))


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict[str, bool]:
    dataset = await session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    count = (await session.execute(select(func.count()).select_from(AuditSession).where(AuditSession.dataset_id == dataset_id))).scalar_one()
    if count:
        raise HTTPException(status_code=409, detail="Dataset has associated audits")
    try:
        os.remove(dataset.file_path)
    except FileNotFoundError:
        pass
    await session.delete(dataset)
    await session.commit()
    return {"ok": True}
