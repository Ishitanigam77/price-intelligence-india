"""Configurable thresholds for the deterministic recommendation engine.

Sourced from `RECOMMENDATION_*` environment variables. No secrets are required.
"""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RECOMMENDATION_DISCLAIMER = (
    "This recommendation is a deterministic, rule-based suggestion from available "
    "observed, calculated, and (when used) predicted data. It is not a guarantee of "
    "any future price, saving, or sale outcome."
)


class RecommendationConfig(BaseSettings):
    """Environment-driven recommendation thresholds, independent of FastAPI settings."""

    model_config = SettingsConfigDict(
        env_prefix="RECOMMENDATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #: Inclusive historical percentile at or below which the current price is favorable.
    buy_percentile_max: float = Field(default=25.0, ge=0.0, le=100.0)
    #: Inclusive percentile at or below which historical position is strongly favorable.
    buy_strong_percentile_max: float = Field(default=15.0, ge=0.0, le=100.0)
    #: Current price is "near historical low" when it is within this percent of the low.
    near_historical_low_percent: float = Field(default=5.0, ge=0.0, le=100.0)
    #: Tighter band used as a standalone strong-buy historical signal.
    near_historical_low_strong_percent: float = Field(default=2.0, ge=0.0, le=100.0)
    #: Inclusive percentile at or above which the current price is unfavorably high.
    wait_percentile_min: float = Field(default=70.0, ge=0.0, le=100.0)
    #: Minimum percent (current − predicted) / current for predicted savings to be material.
    min_predicted_savings_percent: float = Field(default=5.0, ge=0.0, le=100.0)
    #: Minimum percent current is above a window average to count as materially expensive.
    min_above_average_percent: float = Field(default=5.0, ge=0.0, le=100.0)
    #: Phase 10 prediction confidence below this is unused; no predicted price is invented.
    min_prediction_confidence: float = Field(default=0.50, ge=0.0, le=1.0)
    #: Upcoming sale events further than this many days are not WAIT evidence.
    upcoming_horizon_days: int = Field(default=30, ge=1, le=365)
    #: Minimum qualifying stored observations before a recommendation is attempted.
    min_observations: int = Field(default=3, ge=1, le=1000)

    @model_validator(mode="after")
    def _thresholds_are_ordered(self) -> "RecommendationConfig":
        if self.buy_strong_percentile_max > self.buy_percentile_max:
            raise ValueError(
                "buy_strong_percentile_max must be less than or equal to buy_percentile_max."
            )
        if self.buy_percentile_max >= self.wait_percentile_min:
            raise ValueError("buy_percentile_max must be strictly less than wait_percentile_min.")
        if self.near_historical_low_strong_percent > self.near_historical_low_percent:
            raise ValueError(
                "near_historical_low_strong_percent must be less than or equal to "
                "near_historical_low_percent."
            )
        return self


@lru_cache
def get_recommendation_config() -> RecommendationConfig:
    """Cached recommendation config. Tests that mutate env should call `cache_clear()`."""
    return RecommendationConfig()
