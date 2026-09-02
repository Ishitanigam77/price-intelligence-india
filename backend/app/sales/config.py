"""Configurable thresholds for sale-event detection and sale-history statistics.

Sourced from `SALES_*` environment variables. No secrets are required.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SalesConfig(BaseSettings):
    """Environment-driven sale-event configuration, independent of FastAPI settings."""

    model_config = SettingsConfigDict(
        env_prefix="SALES_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #: An observation is treated as discounted when its analysis price is at least this
    #: percent below the listing's prior median.
    drop_percent_threshold: float = Field(default=10.0, gt=0.0, le=100.0)
    #: Minimum distinct listings showing a concurrent drop before a window is emitted.
    min_listings_for_detection: int = Field(default=2, ge=1, le=10000)
    #: Maximum gap (days) between discounted observations that still belong to one window.
    max_gap_days: float = Field(default=2.0, gt=0.0, le=90.0)
    #: Minimum qualifying in-window observations before sale min/max/avg is returned.
    min_observations_for_sale_stats: int = Field(default=1, ge=1, le=1000)
    #: Listing-count threshold at or above which inferred events are `high` confidence.
    high_confidence_listing_count: int = Field(default=5, ge=1, le=10000)
    #: Listing-count threshold at or above which inferred events are `medium` confidence.
    medium_confidence_listing_count: int = Field(default=2, ge=1, le=10000)
    #: Distinct calendar years of a sale family required before current-year mapping runs.
    min_years_for_calendar_mapping: int = Field(default=2, ge=2, le=20)
    #: Max day deviation from the median start for a fixed-calendar mapping.
    fixed_calendar_max_day_deviation: int = Field(default=3, ge=1, le=14)
    #: Max stdev (days) of festival offsets to accept a festival-relative mapping.
    festival_offset_max_stdev_days: float = Field(default=3.0, gt=0.0, le=14.0)
    #: Median |offset| from a festival must be within this many days.
    festival_offset_max_abs_days: int = Field(default=21, ge=0, le=60)
    #: Days of pre-sale observations used as the non-sale baseline for a window.
    pre_sale_lookback_days: int = Field(default=14, ge=1, le=90)
    #: Median in-window drop (%) at or above which a recurring family may be MAJOR.
    major_drop_percent: float = Field(default=15.0, gt=0.0, le=100.0)
    #: Median duration (days) at or above which a recurring family may be MAJOR.
    major_min_duration_days: float = Field(default=4.0, gt=0.0, le=90.0)


@lru_cache
def get_sales_config() -> SalesConfig:
    """Cached sales config. Tests that mutate env should call `cache_clear()`."""
    return SalesConfig()
