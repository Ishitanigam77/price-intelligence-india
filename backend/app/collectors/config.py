"""Collection orchestration settings, sourced from application `Settings` / environment."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings, get_settings


class CollectionConfig(BaseModel):
    """Timeouts, retries, rate limits, and default search parameters for collection jobs."""

    model_config = ConfigDict(frozen=True)

    max_retries: int = Field(default=2, ge=0, le=10)
    initial_backoff_seconds: float = Field(default=0.5, ge=0.0)
    max_backoff_seconds: float = Field(default=30.0, gt=0.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    operation_timeout_seconds: float = Field(default=15.0, gt=0.0)
    retailer_timeout_seconds: float = Field(default=120.0, gt=0.0)
    default_search_query: str = "fictional"
    default_search_limit: int = Field(default=20, ge=1, le=100)
    default_search_category: str | None = None
    rate_limit_requests_per_minute: int = Field(default=60, ge=1)
    rate_limit_burst_size: int = Field(default=1, ge=1)
    rate_limit_max_concurrent: int = Field(default=1, ge=1)

    @property
    def max_attempts(self) -> int:
        """First try plus configured retries. Never unbounded."""
        return self.max_retries + 1


def collection_config_from_settings(settings: Settings | None = None) -> CollectionConfig:
    """Build collection config from environment-backed application settings."""
    resolved = settings if settings is not None else get_settings()
    return CollectionConfig(
        max_retries=resolved.collection_max_retries,
        initial_backoff_seconds=resolved.collection_initial_backoff_seconds,
        max_backoff_seconds=resolved.collection_max_backoff_seconds,
        backoff_multiplier=resolved.collection_backoff_multiplier,
        operation_timeout_seconds=resolved.collection_operation_timeout_seconds,
        retailer_timeout_seconds=resolved.collection_retailer_timeout_seconds,
        default_search_query=resolved.collection_default_search_query,
        default_search_limit=resolved.collection_default_search_limit,
        default_search_category=resolved.collection_search_category_value,
        rate_limit_requests_per_minute=resolved.collection_rate_limit_requests_per_minute,
        rate_limit_burst_size=resolved.collection_rate_limit_burst_size,
        rate_limit_max_concurrent=resolved.collection_rate_limit_max_concurrent,
    )
