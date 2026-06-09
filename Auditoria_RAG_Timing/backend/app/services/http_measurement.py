import time
from dataclasses import dataclass

import httpx

from app.models.target import Target
from app.services.target_service import inject_query_template


@dataclass(frozen=True)
class MeasurementResult:
    status_code: int | None
    ttfb_ms: float | None
    full_response_ms: float | None
    latency_ms: float | None
    response_size_bytes: int | None
    is_error: bool
    error_type: str | None
    error_message: str | None


def create_http_client(target: Target) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=target.headers,
        timeout=httpx.Timeout(target.timeout_seconds),
        verify=target.verify_tls,
        follow_redirects=True,
        limits=httpx.Limits(
            max_connections=1,
            max_keepalive_connections=1,
            keepalive_expiry=None,
        ),
    )


def error_result(error_type: str, error_message: str) -> MeasurementResult:
    return MeasurementResult(
        status_code=None,
        ttfb_ms=None,
        full_response_ms=None,
        latency_ms=None,
        response_size_bytes=None,
        is_error=True,
        error_type=error_type,
        error_message=error_message,
    )


async def measure_target(client: httpx.AsyncClient, target: Target, query: str) -> MeasurementResult:
    json_payload = inject_query_template(target.payload_template, query)
    try:
        started_at = time.perf_counter()
        async with client.stream("POST", target.endpoint_url, json=json_payload) as response:
            chunks = response.aiter_bytes()
            first_chunk = await anext(chunks, b"")
            first_body_byte_at = time.perf_counter()
            response_size = len(first_chunk)
            async for chunk in chunks:
                response_size += len(chunk)
        completed_at = time.perf_counter()
        ttfb_ms = (first_body_byte_at - started_at) * 1000
        return MeasurementResult(
            status_code=response.status_code,
            ttfb_ms=ttfb_ms,
            full_response_ms=(completed_at - started_at) * 1000,
            latency_ms=ttfb_ms,
            response_size_bytes=response_size,
            is_error=False,
            error_type=None,
            error_message=None,
        )
    except httpx.TimeoutException as exc:
        return error_result("timeout", str(exc))
    except httpx.ConnectError as exc:
        return error_result("connection_error", str(exc))
    except httpx.HTTPError as exc:
        return error_result("http_error", str(exc))
    except Exception as exc:
        return error_result(type(exc).__name__, str(exc))
