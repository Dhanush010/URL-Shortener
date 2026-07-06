from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: str = "development"
    app_version: str = "1.0.0"
    base_url: str = "http://localhost:8000"
    secret_key: str = "change-me-in-production"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/urlshortener"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # Cache
    cache_ttl_seconds: int = 3600
    negative_cache_ttl_seconds: int = 300

    # Short code
    short_code_length: int = 6
    short_code_max_retries: int = 5

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
