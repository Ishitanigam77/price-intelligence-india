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

    Only settings actually needed by the phases implemented so far (database + minimal API
    skeleton, retailer adapter framework defaults) are defined here. Later phases add their own
    settings (Redis, Celery, Clerk, per-retailer credentials, ...) alongside the functionality
    that consumes them, per `.env.example`.
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

    # Framework-wide retailer adapter defaults. Individual adapters override these per retailer
    # (see `app/retailer_adapters/base/config.py`); these are only the starting values, chosen
    # to be conservative rather than aggressive.
    retailer_adapter_default_timeout_seconds: float = 10.0
    retailer_adapter_default_max_attempts: int = 3
    retailer_adapter_default_requests_per_minute: int = 60
    retailer_adapter_default_max_concurrent_requests: int = 1
    #: Comma-separated retailer IDs to switch off globally, regardless of per-adapter config.
    retailer_adapters_disabled: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def disabled_retailer_ids(self) -> frozenset[str]:
        """Retailer IDs disabled via `RETAILER_ADAPTERS_DISABLED`."""
        return frozenset(
            entry.strip() for entry in self.retailer_adapters_disabled.split(",") if entry.strip()
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance.

    Cached so environment variables are only read once per process; tests that need different
    settings should call `get_settings.cache_clear()` after monkeypatching the environment.
    """
    return Settings()
