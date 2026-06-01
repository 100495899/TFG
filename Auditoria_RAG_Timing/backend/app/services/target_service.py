from typing import Any

from fastapi import HTTPException

from app.schemas.target import TargetCreate

MARCADOR_CONSULTA = "{{QUERY}}"


def contains_query_marker(value: Any) -> bool:
    if isinstance(value, str):
        return MARCADOR_CONSULTA in value
    if isinstance(value, dict):
        return any(contains_query_marker(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_query_marker(item) for item in value)
    return False


def validate_target_payload(payload: TargetCreate) -> None:
    if payload.http_method == "POST":
        if not payload.payload_template or not contains_query_marker(payload.payload_template):
            raise HTTPException(
                status_code=422,
                detail="POST targets require payload_template containing {{QUERY}}",
            )
    if payload.http_method == "GET" and MARCADOR_CONSULTA not in payload.endpoint_url:
        raise HTTPException(
            status_code=422,
            detail="GET targets require endpoint_url containing {{QUERY}}",
        )


def inject_query_template(value: Any, query: str) -> Any:
    if isinstance(value, str):
        return value.replace(MARCADOR_CONSULTA, query)
    if isinstance(value, dict):
        return {key: inject_query_template(item, query) for key, item in value.items()}
    if isinstance(value, list):
        return [inject_query_template(item, query) for item in value]
    return value
