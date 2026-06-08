import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.dataset import DatasetContent, DatasetQuery

FREQUENCY_GROUPS = {
    "alta_frecuencia": "high",
    "media_frecuencia": "medium",
    "baja_frecuencia": "low",
}

LENGTH_GROUPS = {
    "corta": "short",
    "media": "medium",
    "larga": "long",
}

SUPPORTED_DATASET_SCHEMA = "grouped-es-v1"

DATASET_FORMAT_EXAMPLE = {
    "alta_frecuencia": {
        "corta": ["Consulta corta de frecuencia alta"],
        "media": ["Consulta de longitud media y frecuencia alta"],
        "larga": ["Consulta larga de frecuencia alta"],
    },
    "media_frecuencia": {
        "corta": ["Consulta corta de frecuencia media"],
        "media": ["Consulta de longitud media y frecuencia media"],
        "larga": ["Consulta larga de frecuencia media"],
    },
    "baja_frecuencia": {
        "corta": ["Consulta corta de frecuencia baja"],
        "media": ["Consulta de longitud media y frecuencia baja"],
        "larga": ["Consulta larga de frecuencia baja"],
    },
}


def ensure_supported_schema(schema_version: str) -> None:
    if schema_version != SUPPORTED_DATASET_SCHEMA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El dataset usa un formato antiguo. Vuelve a subirlo con el formato agrupado actual.",
        )


def invalid_dataset_format(errors: list[dict[str, Any]] | None = None) -> HTTPException:
    detail: dict[str, Any] = {
        "message": "El dataset no sigue el formato obligatorio.",
        "expected_format": DATASET_FORMAT_EXAMPLE,
    }
    if errors:
        detail["errors"] = errors
    return HTTPException(status_code=422, detail=detail)


def flatten_dataset(dataset: DatasetContent) -> list[DatasetQuery]:
    queries: list[DatasetQuery] = []
    content = dataset.model_dump()
    for frequency_group, frequency in FREQUENCY_GROUPS.items():
        for length_group, length in LENGTH_GROUPS.items():
            for query_text in content[frequency_group][length_group]:
                queries.append(DatasetQuery(query=query_text, frequency=frequency, length=length))
    return queries


async def parse_dataset_upload(file: UploadFile) -> tuple[DatasetContent, bytes, int]:
    content = await file.read()
    max_bytes = settings.max_dataset_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Dataset file is too large")

    try:
        raw = json.loads(content)
        dataset = DatasetContent.model_validate(raw)
    except json.JSONDecodeError as exc:
        raise invalid_dataset_format([{"message": "El archivo no contiene JSON valido."}]) from exc
    except ValidationError as exc:
        raise invalid_dataset_format(exc.errors(include_url=False)) from exc

    total_queries = len(flatten_dataset(dataset))
    if total_queries == 0:
        raise HTTPException(status_code=422, detail="El dataset debe contener al menos una query.")
    if total_queries > settings.max_queries_per_audit:
        raise HTTPException(status_code=422, detail=f"Dataset exceeds {settings.max_queries_per_audit} queries")

    normalized_content = dataset.model_dump_json(indent=2).encode("utf-8")
    return dataset, normalized_content, total_queries


def save_dataset_file(content: bytes, original_filename: str) -> str:
    datasets_dir = Path(settings.datasets_dir)
    datasets_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{Path(original_filename).name}"
    path = datasets_dir / safe_name
    path.write_bytes(content)
    return str(path)


def load_dataset_file(path: str) -> list[DatasetQuery]:
    with open(path, "r", encoding="utf-8") as file:
        raw = json.load(file)

    queries: list[DatasetQuery] = []
    for frequency_group, frequency in FREQUENCY_GROUPS.items():
        for length_group, length in LENGTH_GROUPS.items():
            for query_text in raw[frequency_group][length_group]:
                queries.append(
                    DatasetQuery.model_construct(
                        query=query_text,
                        frequency=frequency,
                        length=length,
                    )
                )
    return queries


def distribution(queries: list[DatasetQuery]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {"frequency": {}, "length": {}}
    for query in queries:
        result["frequency"][query.frequency] = result["frequency"].get(query.frequency, 0) + 1
        result["length"][query.length] = result["length"].get(query.length, 0) + 1
    return result
