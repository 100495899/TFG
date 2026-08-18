import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.api.v1 import audits as audits_api
from app.api.v1 import targets as targets_api
from app.api.v1 import term_inference as term_inference_api
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.audit import AuditResult, AuditSession
from app.models.dataset import Dataset
from app.models.target import Target
from app.models.term_inference import TermInferenceMeasurement, TermInferenceResult, TermInferenceSession
from app.models.user import User
from app.services import dataset_service
from app.services.http_measurement import MeasurementResult


DATASET_CONTENT = {
    "alta_frecuencia": {
        "corta": ["What is man?"],
        "media": ["Explain the history of man."],
        "larga": ["Explain the historical role of man in literature and culture."],
    },
    "media_frecuencia": {
        "corta": ["What is paper?"],
        "media": ["Explain the use of paper in books."],
        "larga": ["Explain the use of paper across historical book collections."],
    },
    "baja_frecuencia": {
        "corta": ["What is zenthorium?"],
        "media": ["Explain the fictional zenthorium concept."],
        "larga": ["Explain the fictional zenthorium concept in an invented archive."],
    },
}


class FakeRedis:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, str]] = []
        self.closed = False

    async def enqueue_job(self, name: str, identifier: str) -> None:
        self.jobs.append((name, identifier))

    async def aclose(self) -> None:
        self.closed = True


class DummyHttpClient:
    async def __aenter__(self) -> "DummyHttpClient":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


@pytest.fixture(autouse=True)
async def clean_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dataset_service.settings, "datasets_dir", str(tmp_path))
    await engine.dispose()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        session.add(
            User(
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                role="admin",
            )
        )
        await session.commit()
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    redis = FakeRedis()

    async def create_fake_pool(settings_object: Any) -> FakeRedis:
        return redis

    monkeypatch.setattr(audits_api, "create_pool", create_fake_pool)
    monkeypatch.setattr(term_inference_api, "create_pool", create_fake_pool)
    return redis


@pytest.fixture
def fake_target_measurement(monkeypatch: pytest.MonkeyPatch) -> None:
    async def measure(client: DummyHttpClient, target: Target, query: str) -> MeasurementResult:
        return MeasurementResult(
            status_code=200,
            ttfb_ms=123.4,
            full_response_ms=210.5,
            latency_ms=123.4,
            response_size_bytes=len(query.encode("utf-8")),
            is_error=False,
            error_type=None,
            error_message=None,
        )

    monkeypatch.setattr(targets_api, "create_http_client", lambda target: DummyHttpClient())
    monkeypatch.setattr(targets_api, "measure_target", measure)


async def login(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()


async def create_target(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/targets",
        json={
            "name": "Functional Target",
            "endpoint_url": "https://rag.example.test/chat",
            "headers": {"X-Test": "true"},
            "payload_template": {"query": "{{QUERY}}"},
            "timeout_seconds": 15,
            "verify_tls": True,
        },
    )
    assert response.status_code == 200
    return response.json()


async def upload_dataset(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/datasets/upload",
        files={
            "file": (
                "functional_dataset.json",
                json.dumps(DATASET_CONTENT).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert response.status_code == 200
    return response.json()


async def add_audit_results(audit_id: str) -> None:
    async with AsyncSessionLocal() as session:
        audit = await session.get(AuditSession, uuid.UUID(audit_id))
        assert audit is not None
        audit.status = "COMPLETED"
        audit.started_at = datetime.now(timezone.utc)
        audit.completed_at = datetime.now(timezone.utc)
        audit.progress_current = audit.progress_total
        rows = [
            ("high", "short", "What is man?", 100.0),
            ("high", "short", "Explain man.", 102.0),
            ("medium", "short", "What is paper?", 140.0),
            ("medium", "short", "Explain paper.", 142.0),
            ("low", "short", "What is zenthorium?", 180.0),
            ("low", "short", "Explain zenthorium.", 182.0),
        ]
        for index, (frequency, length, query, ttfb) in enumerate(rows, start=1):
            session.add(
                AuditResult(
                    session_id=audit.id,
                    request_index=index,
                    query_text=query,
                    frequency_tag=frequency,
                    length_tag=length,
                    latency_ms=ttfb,
                    ttfb_ms=ttfb,
                    full_response_ms=ttfb + 50,
                    status_code=200,
                    response_size_bytes=512,
                    is_error=False,
                )
            )
        await session.commit()


async def add_completed_term_inference(inference_id: str) -> None:
    async with AsyncSessionLocal() as session:
        inference = await session.get(TermInferenceSession, uuid.UUID(inference_id))
        assert inference is not None
        inference.status = "COMPLETED"
        inference.started_at = datetime.now(timezone.utc)
        inference.completed_at = datetime.now(timezone.utc)
        result = TermInferenceResult(
            session_id=inference.id,
            term="man",
            is_control=False,
            classification="likely_present",
            observed_mean_ttfb_ms=101.0,
            observed_std_ttfb_ms=1.0,
            valid_measurements=2,
            total_measurements=2,
            distance_to_threshold_ms=-39.0,
            closest_reference="high",
            error_count=0,
        )
        session.add(result)
        await session.flush()
        for index, ttfb in enumerate([100.5, 101.5], start=1):
            session.add(
                TermInferenceMeasurement(
                    result_id=result.id,
                    request_index=index,
                    round_number=1,
                    query_text=f"Probe {index} for man",
                    latency_ms=ttfb,
                    ttfb_ms=ttfb,
                    full_response_ms=ttfb + 40,
                    status_code=200,
                    response_size_bytes=256,
                    is_error=False,
                )
            )
        inference.progress_current = 2
        inference.progress_total = 2
        await session.commit()


@pytest.mark.asyncio
async def test_authenticated_audit_flow(
    client: httpx.AsyncClient,
    fake_redis: FakeRedis,
    fake_target_measurement: None,
):
    unauthenticated = await client.get("/api/v1/targets")
    assert unauthenticated.status_code == 401

    await login(client)
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == settings.admin_email

    target = await create_target(client)
    test_response = await client.post(f"/api/v1/targets/{target['id']}/test", json={"query": "health probe"})
    assert test_response.status_code == 200
    assert test_response.json()["ok"] is True

    update_response = await client.put(
        f"/api/v1/targets/{target['id']}",
        json={
            "name": "Updated Functional Target",
            "endpoint_url": "https://rag.example.test/chat",
            "headers": {},
            "payload_template": {"messages": [{"content": "{{QUERY}}"}]},
            "timeout_seconds": 20,
            "verify_tls": False,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Functional Target"

    dataset = await upload_dataset(client)
    preview = await client.get(f"/api/v1/datasets/{dataset['id']}/preview")
    assert preview.status_code == 200
    assert preview.json()["distribution"]["frequency"] == {"high": 3, "medium": 3, "low": 3}

    start = await client.post(
        "/api/v1/audits/start",
        json={
            "target_id": target["id"],
            "dataset_id": dataset["id"],
            "calibration_requests": 2,
            "random_seed": 123,
        },
    )
    assert start.status_code == 200
    audit_id = start.json()["session_id"]
    assert fake_redis.jobs == [("run_audit_job", audit_id)]
    assert fake_redis.closed is True

    status_response = await client.get(f"/api/v1/audits/{audit_id}/status")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "PENDING"
    assert status_response.json()["progress_total"] == dataset["total_queries"]

    abort_response = await client.post(f"/api/v1/audits/{audit_id}/abort")
    assert abort_response.status_code == 200
    blocked_delete = await client.delete(f"/api/v1/audits/{audit_id}")
    assert blocked_delete.status_code == 409

    await add_audit_results(audit_id)

    dashboard = await client.get("/api/v1/audits/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()[0]["target_name"] == "Updated Functional Target"

    results = await client.get(f"/api/v1/audits/{audit_id}/results", params={"frequency": "high", "page_size": 2})
    assert results.status_code == 200
    assert results.json()["total"] == 2

    summary = await client.get(f"/api/v1/audits/{audit_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["metadata"]["successful_requests"] == 6

    raw_csv = await client.get(f"/api/v1/audits/{audit_id}/export.csv")
    assert raw_csv.status_code == 200
    assert "query_text" in raw_csv.text
    assert "What is man?" in raw_csv.text

    summary_csv = await client.get(f"/api/v1/audits/{audit_id}/export-summary.csv")
    assert summary_csv.status_code == 200
    assert "mean_ttfb_ms" in summary_csv.text

    delete_audit = await client.delete(f"/api/v1/audits/{audit_id}")
    assert delete_audit.status_code == 200
    delete_dataset = await client.delete(f"/api/v1/datasets/{dataset['id']}")
    assert delete_dataset.status_code == 200
    delete_target = await client.delete(f"/api/v1/targets/{target['id']}")
    assert delete_target.status_code == 200

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_term_inference_flow_accepts_audit_or_summary_csv_and_exports_results(
    client: httpx.AsyncClient,
    fake_redis: FakeRedis,
):
    await login(client)
    target = await create_target(client)
    dataset = await upload_dataset(client)

    audit_start = await client.post(
        "/api/v1/audits/start",
        json={
                "target_id": target["id"],
                "dataset_id": dataset["id"],
                "calibration_requests": 1,
                "random_seed": 456,
            },
        )
    assert audit_start.status_code == 200
    audit_id = audit_start.json()["session_id"]
    await add_audit_results(audit_id)
    fake_redis.jobs.clear()

    inference_start = await client.post(
        "/api/v1/term-inference/start",
        json={
            "target_id": target["id"],
            "source_audit_id": audit_id,
            "terms_payload": {"terms": ["man", "Man", "tesla"], "negative_controls": ["zenthorium"]},
            "random_seed": 789,
            "probes_per_round": 4,
            "max_probes_per_term": 12,
        },
    )
    assert inference_start.status_code == 200
    inference_id = inference_start.json()["session_id"]
    assert fake_redis.jobs == [("run_term_inference_job", inference_id)]

    inference_status = await client.get(f"/api/v1/term-inference/{inference_id}/status")
    assert inference_status.status_code == 200
    assert inference_status.json()["status"] == "PENDING"

    abort = await client.post(f"/api/v1/term-inference/{inference_id}/abort")
    assert abort.status_code == 200
    blocked_delete = await client.delete(f"/api/v1/term-inference/{inference_id}")
    assert blocked_delete.status_code == 409

    await add_completed_term_inference(inference_id)

    listing = await client.get("/api/v1/term-inference")
    assert listing.status_code == 200
    assert listing.json()[0]["result_count"] == 1
    assert listing.json()[0]["progress_current"] == 2

    results = await client.get(f"/api/v1/term-inference/{inference_id}/results")
    assert results.status_code == 200
    body = results.json()
    assert body["results"][0]["classification"] == "likely_present"
    assert body["measurements"][0]["query_text"] == "Probe 1 for man"

    export = await client.get(f"/api/v1/term-inference/{inference_id}/export.csv")
    assert export.status_code == 200
    assert "likely_present" in export.text
    assert "observed_mean_ttfb_ms" in export.text

    raw_csv_rejection = await client.post(
        "/api/v1/term-inference/start",
        data={
            "target_id": target["id"],
            "terms_payload": json.dumps({"terms": ["man"]}),
            "random_seed": "123",
            "probes_per_round": "4",
            "max_probes_per_term": "12",
        },
        files={"summary_csv": ("raw.csv", b"request_index,query_text,ttfb_ms\n1,a,10\n", "text/csv")},
    )
    assert raw_csv_rejection.status_code == 422
    assert "Raw CSV is not supported" in raw_csv_rejection.text

    valid_summary_csv = (
        "frequency,length,mean_ttfb_ms,std_ttfb_ms\n"
        "high,short,100,5\n"
        "medium,short,140,6\n"
        "low,short,180,7\n"
    ).encode("utf-8")
    csv_start = await client.post(
        "/api/v1/term-inference/start",
        data={
            "target_id": target["id"],
            "terms_payload": json.dumps({"custom_queries": {"time": ["time in books", "history of time"]}}),
            "random_seed": "321",
            "probes_per_round": "3",
            "max_probes_per_term": "9",
        },
        files={"summary_csv": ("summary.csv", valid_summary_csv, "text/csv")},
    )
    assert csv_start.status_code == 200
    csv_inference = await client.get(f"/api/v1/term-inference/{csv_start.json()['session_id']}")
    assert csv_inference.status_code == 200
    assert csv_inference.json()["source_type"] == "summary_csv"
    assert csv_inference.json()["source_audit_id"] is None

    delete_inference = await client.delete(f"/api/v1/term-inference/{inference_id}")
    assert delete_inference.status_code == 200
