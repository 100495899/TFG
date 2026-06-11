from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    redis_url: str
    jwt_secret_key: str
    jwt_expire_minutes: int
    session_cookie_secure: bool
    admin_email: str
    admin_password: str
    datasets_dir: str
    max_dataset_size_mb: int
    max_queries_per_audit: int
    max_concurrent_audits: int
    backend_cors_origin: str
    api_v1_prefix: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
