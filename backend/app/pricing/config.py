"""Configurable freshness windows for the price comparison engine.

Sourced from `PRICING_*` environment variables. No secrets are required.
"""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PricingConfig(BaseSettings):
    """Environment-driven comparison configuration, independent of FastAPI settings."""

    model_config = SettingsConfigDict(
        env_prefix="PRICING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #: Observations younger than this (hours) are `fresh`.
    fresh_within_hours: float = Field(default=6.0, gt=0.0, le=168.0)
    #: Observations older than this (hours) are `stale`. Between the two windows is `aging`.
    stale_after_hours: float = Field(default=24.0, gt=0.0, le=720.0)

    @model_validator(mode="after")
    def _windows_are_ordered(self) -> "PricingConfig":
        if self.stale_after_hours < self.fresh_within_hours:
            raise ValueError(
                "stale_after_hours must be greater than or equal to fresh_within_hours."
            )
        return self

    @property
    def fresh_within_seconds(self) -> float:
        return self.fresh_within_hours * 3600.0

    @property
    def stale_after_seconds(self) -> float:
        return self.stale_after_hours * 3600.0


@lru_cache
def get_pricing_config() -> PricingConfig:
    """Cached pricing config. Tests that mutate env should call `cache_clear()`."""
    return PricingConfig()
