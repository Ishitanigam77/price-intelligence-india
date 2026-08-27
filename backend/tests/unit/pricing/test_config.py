"""PricingConfig validation."""

import pytest
from pydantic import ValidationError

from app.pricing.config import PricingConfig, get_pricing_config


def test_defaults_are_sane() -> None:
    config = PricingConfig(_env_file=None)
    assert config.fresh_within_hours == 6.0
    assert config.stale_after_hours == 24.0
    assert config.fresh_within_seconds == 6.0 * 3600
    assert config.stale_after_seconds == 24.0 * 3600
    assert config.trend_stable_percent == 2.0
    assert config.min_observations_for_average == 1
    assert config.min_observations_for_extrema == 1
    assert config.min_observations_for_volatility == 2
    assert config.min_observations_for_percentile == 2
    assert config.min_observations_for_trend == 2


def test_stale_window_cannot_be_narrower_than_fresh_window() -> None:
    with pytest.raises(ValidationError):
        PricingConfig(_env_file=None, fresh_within_hours=48, stale_after_hours=6)


def test_get_pricing_config_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    get_pricing_config.cache_clear()
    try:
        monkeypatch.setenv("PRICING_FRESH_WITHIN_HOURS", "2")
        first = get_pricing_config()
        monkeypatch.setenv("PRICING_FRESH_WITHIN_HOURS", "3")
        second = get_pricing_config()
        assert first is second
        assert first.fresh_within_hours == 2.0
    finally:
        get_pricing_config.cache_clear()
