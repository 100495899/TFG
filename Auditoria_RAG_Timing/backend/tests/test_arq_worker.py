import pytest

from app.core.config import settings
from app.workers.arq_worker import WorkerSettings, redis_settings_from_url


def test_redis_settings_are_read_from_complete_url():
    settings = redis_settings_from_url("redis://user:secret@redis:6379/2")

    assert settings.host == "redis"
    assert settings.port == 6379
    assert settings.database == 2
    assert settings.username == "user"
    assert settings.password == "secret"


@pytest.mark.parametrize(
    "url",
    [
        "redis://redis/0",
        "redis://:6379/0",
        "redis://redis:6379",
    ],
)
def test_redis_url_requires_host_port_and_database(url: str):
    with pytest.raises(ValueError):
        redis_settings_from_url(url)


def test_audit_job_uses_configured_timeout_without_automatic_retries():
    audit_job = WorkerSettings.functions[0]

    assert audit_job.timeout_s == settings.audit_job_timeout_seconds
    assert audit_job.max_tries == 1
