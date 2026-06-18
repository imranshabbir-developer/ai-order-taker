from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(raw: str) -> str:
    """Convert standard Postgres URLs to SQLAlchemy asyncpg form."""
    url = raw.strip()
    if not url:
        return ""

    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")

    # asyncpg uses ssl=require (Aiven uses sslmode=require)
    url = url.replace("sslmode=require", "ssl=require")
    url = url.replace("sslmode=verify-full", "ssl=require")
    url = url.replace("sslmode=verify-ca", "ssl=require")
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""
    redis_url: str = "redis://127.0.0.1:6379/0"

    @property
    def async_database_url(self) -> str:
        return normalize_database_url(self.database_url)

    @property
    def database_enabled(self) -> bool:
        return bool(self.async_database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
