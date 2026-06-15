from urllib.parse import urlparse

from arq.connections import RedisSettings
from arq.worker import func

from app.core.config import settings
from app.services.audit_runner import run_audit_job


def redis_settings_from_url(url: str) -> RedisSettings:
    parsed = urlparse(url)
    if parsed.hostname is None or parsed.port is None or not parsed.path.lstrip("/"):
        raise ValueError("REDIS_URL must include host, port and database")
    return RedisSettings(
        host=parsed.hostname,
        port=parsed.port,
        database=int(parsed.path.lstrip("/")),
        username=parsed.username,
        password=parsed.password,
    )


class WorkerSettings:
    functions = [
        func(
            run_audit_job,
            timeout=settings.audit_job_timeout_seconds,
            max_tries=1,
        )
    ]
    redis_settings = redis_settings_from_url(settings.redis_url)
    max_jobs = settings.max_concurrent_audits
