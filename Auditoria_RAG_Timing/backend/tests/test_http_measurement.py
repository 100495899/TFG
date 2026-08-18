import asyncio
import json

import httpx

from app.models.target import Target
from app.services.http_measurement import measure_target


def test_measure_target_sends_post_and_injects_query():
    asyncio.run(run_measurement_test())


async def run_measurement_test():
    captured_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, content=b'{"answer":"ok"}')

    target = Target(
        name="test",
        endpoint_url="https://example.test/chat",
        headers={"Authorization": "Bearer token"},
        payload_template={"request": {"question": "{{QUERY}}"}},
        timeout_seconds=30,
        verify_tls=True,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await measure_target(client, target, "What is time?")

    assert captured_request is not None
    assert captured_request.method == "POST"
    assert json.loads(captured_request.content) == {"request": {"question": "What is time?"}}
    assert result.status_code == 200
    assert result.is_error is False
    assert result.ttfb_ms is not None
    assert result.full_response_ms is not None
    assert result.full_response_ms >= result.ttfb_ms
    assert result.response_size_bytes == len(b'{"answer":"ok"}')
