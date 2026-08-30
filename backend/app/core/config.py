"""Application settings, sourced from environment variables.

Per `DEVELOPMENT_RULES.md` §4, configuration is never hardcoded. Locally this is populated from
a `.env` file (see `.env.example` at the repo root); in deployed environments the same variable
names are expected to be injected via Azure Key Vault / managed identity, not from a committed
file.
"""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REDIS_SCHEMES = {"redis", "rediss"}


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
    #: Process identity written on every structured log / metric. Override per container.
    service_name: str = "backend"

    # -- Observability (Phase 16). Connection string from env / Key Vault — never log it. ----
    applicationinsights_connection_string: str = ""
    worker_health_host: str = "0.0.0.0"
    worker_health_port: int = 8081
    worker_health_http: bool = False

    # -- API -----------------------------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_v1_prefix: str = "/api/v1"

    # -- CORS ----------------------------------------------------------------------------------
    # Comma-separated list of allowed origins, e.g. "http://localhost:3000,https://app.example.com"
    cors_allowed_origins: str = "http://localhost:3000"
    cors_allow_credentials: bool = True

    # -- API abuse protection (Phase 17). In-process; no extra infrastructure. -----------------
    # auto = on for deployed environments (prod/staging/dev), off for local development/test.
    api_rate_limit_enabled: str = "auto"
    api_rate_limit_per_minute: int = Field(default=120, ge=1, le=10000)
    api_rate_limit_expensive_per_minute: int = Field(default=20, ge=1, le=10000)

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
    #: Defaults to mock adapters so local discovery stays fixture-backed. Set to
    #: `integration` to wire Amazon.in / Flipkart when their env credentials exist.
    retailer_adapter_kinds: str = "mock"

    # -- Authentication (Clerk) ----------------------------------------------------------------
    # Secret key is backend-only. Never expose it to the frontend or log it.
    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    clerk_audience: str = ""

    # -- Celery (Phase 13 background collection) ----------------------------------------------
    #: Redis URL used as the Celery broker. Never log this value — it may contain a password.
    celery_broker_url: str = "redis://localhost:6379/1"
    #: Redis URL used as the Celery result backend. Never log this value.
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_always_eager: bool = False
    celery_task_eager_propagates: bool = True
    celery_task_acks_late: bool = True
    celery_worker_concurrency: int = 2
    celery_worker_prefetch_multiplier: int = 1
    celery_task_time_limit: int = 300
    celery_task_soft_time_limit: int = 270
    celery_result_expires_seconds: int = 86400
    celery_broker_connection_retry_on_startup: bool = True

    # -- Collection jobs (Phase 13) ------------------------------------------------------------
    #: Additional attempts after the first try. Total attempts = this value + 1. Never infinite.
    collection_max_retries: int = Field(default=2, ge=0, le=10)
    collection_initial_backoff_seconds: float = 0.5
    collection_max_backoff_seconds: float = 30.0
    collection_backoff_multiplier: float = 2.0
    #: Outer bound for a single retailer operation (search, one SKU refresh, ...).
    collection_operation_timeout_seconds: float = 15.0
    #: Outer bound for one retailer's slice of a job, including retries.
    collection_retailer_timeout_seconds: float = 120.0
    collection_default_search_query: str = "fictional"
    collection_default_search_limit: int = 20
    collection_default_search_category: str = ""
    #: Collection-layer per-retailer pacing. Independent per retailer; never a global lock.
    collection_rate_limit_requests_per_minute: int = 60
    collection_rate_limit_burst_size: int = 1
    collection_rate_limit_max_concurrent: int = 1
    collection_beat_enabled: bool = False
    collection_search_interval_seconds: int = 3600
    collection_product_refresh_interval_seconds: int = 3600
    collection_price_refresh_interval_seconds: int = 1800
    collection_availability_refresh_interval_seconds: int = 1800
    collection_sale_event_refresh_interval_seconds: int = 3600

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

    @field_validator("celery_broker_url", "celery_result_backend")
    @classmethod
    def _validate_celery_redis_url(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(
                "Celery broker and result backend URLs are required. Set CELERY_BROKER_URL "
                "and CELERY_RESULT_BACKEND to redis:// or rediss:// URLs (credentials from "
                "the environment / Key Vault, never committed)."
            )
        scheme = stripped.split("://", 1)[0].lower()
        if scheme not in _REDIS_SCHEMES:
            raise ValueError(
                "Celery broker and result backend URLs must use the redis:// or rediss:// "
                "scheme. The URL value is not echoed here because it may contain a password."
            )
        return stripped

    @field_validator("redis_url")
    @classmethod
    def _validate_redis_url(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(
                "REDIS_URL is required. Set it to a redis:// or rediss:// URL (credentials "
                "from the environment / Key Vault, never committed)."
            )
        scheme = stripped.split("://", 1)[0].lower()
        if scheme not in _REDIS_SCHEMES:
            raise ValueError(
                "REDIS_URL must use the redis:// or rediss:// scheme. The URL value is not "
                "echoed here because it may contain a password."
            )
        return stripped

    @field_validator(
        "collection_max_retries",
        "celery_worker_concurrency",
        "celery_worker_prefetch_multiplier",
        "celery_task_time_limit",
        "celery_task_soft_time_limit",
        "collection_default_search_limit",
        "collection_rate_limit_requests_per_minute",
        "collection_rate_limit_burst_size",
        "collection_rate_limit_max_concurrent",
    )
    @classmethod
    def _validate_positive_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Numeric collection/Celery settings must be >= 0.")
        return value

    @field_validator(
        "collection_max_backoff_seconds",
        "collection_backoff_multiplier",
        "collection_operation_timeout_seconds",
        "collection_retailer_timeout_seconds",
    )
    @classmethod
    def _validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Collection timeout and backoff multiplier settings must be > 0.")
        return value

    @field_validator("collection_initial_backoff_seconds")
    @classmethod
    def _validate_non_negative_backoff(cls, value: float) -> float:
        if value < 0:
            raise ValueError("collection_initial_backoff_seconds must be >= 0.")
        return value

    @model_validator(mode="after")
    def _reject_wildcard_cors_with_credentials(self) -> "Settings":
        if self.cors_allow_credentials and "*" in self.cors_allowed_origins_list:
            raise ValueError(
                "CORS origin '*' cannot be used when CORS_ALLOW_CREDENTIALS is true."
            )
        return self

    @property
    def is_production(self) -> bool:
        """True for Azure prod (`prod`) and the explicit `production` name."""
        return self.environment.lower() in {"production", "prod"}

    @property
    def is_test(self) -> bool:
        return self.environment.lower() == "test"

    @property
    def is_local_or_test(self) -> bool:
        """Local Compose / pytest — not an Azure environment (`dev`/`staging`/`prod`)."""
        return self.environment.lower() in {"development", "test"}

    @property
    def is_deployed(self) -> bool:
        """Azure Container Apps environments (`dev`, `staging`, `prod` / `production`)."""
        return not self.is_local_or_test

    @property
    def rate_limiting_enabled(self) -> bool:
        """In-process API rate limiting. Auto-on in deployed environments."""
        normalized = self.api_rate_limit_enabled.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return self.is_deployed

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

    @property
    def collection_search_category_value(self) -> str | None:
        """Optional default search category; empty env value means unrestricted."""
        stripped = self.collection_default_search_category.strip()
        return stripped or None

    @property
    def collection_max_attempts(self) -> int:
        """Total attempts for a retryable collection failure (first try + configured retries)."""
        return self.collection_max_retries + 1


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance.

    Cached so environment variables are only read once per process; tests that need different
    settings should call `get_settings.cache_clear()` after monkeypatching the environment.
    """
    return Settings()
