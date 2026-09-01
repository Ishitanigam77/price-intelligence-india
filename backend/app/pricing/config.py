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

    #: Implied percent-change band inside which historical trend is classified `stable`.
    trend_stable_percent: float = Field(default=2.0, ge=0.0, le=100.0)
    #: Minimum qualifying observations required before a window average is returned.
    min_observations_for_average: int = Field(default=1, ge=1, le=1000)
    #: Minimum qualifying observations required for historical min/max.
    min_observations_for_extrema: int = Field(default=1, ge=1, le=1000)
    #: Minimum qualifying observations required for sample volatility.
    min_observations_for_volatility: int = Field(default=2, ge=2, le=1000)
    #: Minimum qualifying observations required for a current-price percentile.
    min_observations_for_percentile: int = Field(default=2, ge=2, le=1000)
    #: Minimum qualifying observations required for a historical trend.
    min_observations_for_trend: int = Field(default=2, ge=2, le=1000)
    #: Minimum qualifying observations in a calendar month before monthly stats are returned.
    min_observations_for_monthly: int = Field(default=3, ge=1, le=1000)
    #: Minimum distinct months with usable stats before a best-buying-month is named.
    min_months_for_best_buying_month: int = Field(default=2, ge=1, le=12)

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
