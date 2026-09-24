from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    model_version: str = "3.2.0-dev"
    tax_version: str = "br-simplified-2026.09-draft"
    database_url: str | None = None
    redis_url: str | None = None
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    session_cookie_name: str = "startupvalue_session"
    session_lifetime_hours: int = 720
    session_cookie_secure: bool | None = None
    csrf_secret: str | None = None
    domain: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    public_app_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
