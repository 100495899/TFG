import pytest
from fastapi import HTTPException

from app.schemas.target import TargetCreate
from app.services.target_service import inject_query_template, validate_target_payload


def test_inject_query_template_recursively_replaces_placeholder():
    template = {
        "question": "{{QUERY}}",
        "messages": [{"content": "Ask: {{QUERY}}"}],
        "temperature": 0,
    }

    assert inject_query_template(template, "What is time?") == {
        "question": "What is time?",
        "messages": [{"content": "Ask: What is time?"}],
        "temperature": 0,
    }


def test_target_requires_payload_placeholder():
    payload = TargetCreate(
        name="bad",
        endpoint_url="http://example.test/chat",
        headers={},
        payload_template={"question": "missing"},
    )

    with pytest.raises(HTTPException) as exc:
        validate_target_payload(payload)

    assert exc.value.status_code == 422
    assert "{{QUERY}}" in exc.value.detail


def test_target_accepts_nested_payload_placeholder():
    payload = TargetCreate(
        name="valid",
        endpoint_url="http://example.test/chat",
        headers={},
        payload_template={"request": {"question": "{{QUERY}}"}},
    )

    validate_target_payload(payload)
