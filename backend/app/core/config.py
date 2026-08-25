"""Application settings, sourced from environment variables.

Per `DEVELOPMENT_RULES.md` §4, configuration is never hardcoded. Locally this is populated from
a `.env` file (see `.env.example` at the repo root); in deployed environments the same variable
names are expected to be injected via Azure Key Vault / managed identity, not from a committed
file.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application configuration.

    Only settings actually needed by Phase 1 (database + minimal API skeleton) are defined
    here. Later phases add their own settings (Redis, Celery, Clerk, retailer credentials, ...)
    alongside the functionality that consumes them, per `.env.example`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+psycopg://priceradar_app:changeme@localhost:5432/priceradar"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance.

    Cached so environment variables are only read once per process; tests that need different
    settings should call `get_settings.cache_clear()` after monkeypatching the environment.
    """
    return Settings()
