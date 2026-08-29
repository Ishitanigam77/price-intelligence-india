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

    Settings needed by Phase 1 (database + minimal API skeleton), the FastAPI backend
    foundation (API app config, Redis, CORS, DB pool sizing, logging), and the retailer
    adapter framework defaults are defined here. Later phases add their own settings (Celery,
    Clerk, per-retailer credentials, ...) alongside the functionality that consumes them, per
    `.env.example`.
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

    # -- Redis (connection/client infrastructure only; caching logic, Celery broker/result-
    # backend usage, queues, and distributed locks are introduced in later phases) -----------
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 20
    redis_socket_timeout: float = 5.0
    redis_socket_connect_timeout: float = 5.0

    # Framework-wide retailer adapter defaults. Individual adapters override these per retailer
    # (see `app/retailer_adapters/base/config.py`); these are only the starting values, chosen
    # to be conservative rather than aggressive.
    retailer_adapter_default_timeout_seconds: float = 10.0
    retailer_adapter_default_max_attempts: int = 3
    retailer_adapter_default_requests_per_minute: int = 60
    retailer_adapter_default_max_concurrent_requests: int = 1
    #: Comma-separated retailer IDs to switch off globally, regardless of per-adapter config.
    retailer_adapters_disabled: str = ""
    #: Comma-separated adapter kinds to instantiate at startup (`mock`, `integration`).
    #: Phase 4 product discovery uses the existing fixture-backed mock adapters only; real
    #: integrations are a later phase. Production should switch this to `integration` once
    #: legitimate retailer adapters exist.
    retailer_adapter_kinds: str = "mock"

    # -- Authentication (Clerk) ----------------------------------------------------------------
    # Secret key is backend-only. Never expose it to the frontend or log it.
    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    clerk_audience: str = ""

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}, got {value!r}.")
        return normalized

    @field_validator("retailer_adapter_kinds")
    @classmethod
    def _validate_retailer_adapter_kinds(cls, value: str) -> str:
        allowed = {"mock", "integration"}
        for entry in value.split(","):
            token = entry.strip().lower()
            if token and token not in allowed:
                raise ValueError(
                    f"retailer_adapter_kinds entries must be one of {sorted(allowed)}, "
                    f"got {token!r}."
                )
        return value

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

    @property
    def disabled_retailer_ids(self) -> frozenset[str]:
        """Retailer IDs disabled via `RETAILER_ADAPTERS_DISABLED`."""
        return frozenset(
            entry.strip() for entry in self.retailer_adapters_disabled.split(",") if entry.strip()
        )

    @property
    def retailer_adapter_kind_values(self) -> tuple[str, ...]:
        """Adapter kinds to register at startup (`mock` and/or `integration`)."""
        kinds = tuple(
            entry.strip().lower()
            for entry in self.retailer_adapter_kinds.split(",")
            if entry.strip()
        )
        return kinds if kinds else ("mock",)

    @property
    def clerk_is_configured(self) -> bool:
        """True when backend token verification can run (JWKS URL present).

        A missing JWKS URL means protected routes fail closed (401). The secret key is never
        treated as sufficient by itself for JWT verification, and is never returned to clients.
        """
        return bool(self.clerk_jwks_url.strip())


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance.

    Cached so environment variables are only read once per process; tests that need different
    settings should call `get_settings.cache_clear()` after monkeypatching the environment.
    """
    return Settings()
