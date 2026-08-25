"""Application settings, sourced from environment variables.

Per `DEVELOPMENT_RULES.md` §4, configuration is never hardcoded. Locally this is populated from
a `.env` file (see `.env.example` at the repo root); in deployed environments the same variable
names are expected to be injected via Azure Key Vault / managed identity, not from a committed
file.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application configuration.

    Settings needed by Phase 1 (database + minimal API skeleton) and Phase 2 (FastAPI backend
    foundation: API app config, Redis, CORS, DB pool sizing, logging) are defined here. Later
    phases add their own settings (Celery, Clerk, retailer credentials, ...) alongside the
    functionality that consumes them, per `.env.example`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- General -----------------------------------------------------------------------------
    environment: str = "development"
    log_level: str = "INFO"
    log_format: str = "json"

    # -- API -----------------------------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_v1_prefix: str = "/api/v1"

    # -- CORS ----------------------------------------------------------------------------------
    # Comma-separated list of allowed origins, e.g. "http://localhost:3000,https://app.example.com"
    cors_allowed_origins: str = "http://localhost:3000"
    cors_allow_credentials: bool = True

    # -- Database (PostgreSQL) ------------------------------------------------------------------
    database_url: str = "postgresql+psycopg://priceradar_app:changeme@localhost:5432/priceradar"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    # -- Redis (cache/session infrastructure only in Phase 2; Celery broker use is Phase 2+) ----
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 20
    redis_socket_timeout: float = 5.0
    redis_socket_connect_timeout: float = 5.0

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}, got {value!r}.")
        return normalized

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_test(self) -> bool:
        return self.environment.lower() == "test"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        """Parse the comma-separated `cors_allowed_origins` env var into a clean list.

        Never defaults to a wildcard: an empty/unset value simply allows no cross-origin
        requests rather than silently allowing all of them.
        """
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance.

    Cached so environment variables are only read once per process; tests that need different
    settings should call `get_settings.cache_clear()` after monkeypatching the environment.
    """
    return Settings()
