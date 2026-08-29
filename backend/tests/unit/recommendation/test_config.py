"""RecommendationConfig validation."""

import pytest
from pydantic import ValidationError

from app.recommendation.config import RecommendationConfig, get_recommendation_config


def test_defaults_are_sane() -> None:
    config = RecommendationConfig(_env_file=None)
    assert config.buy_percentile_max == 25.0
    assert config.buy_strong_percentile_max == 15.0
    assert config.near_historical_low_percent == 5.0
    assert config.near_historical_low_strong_percent == 2.0
    assert config.wait_percentile_min == 70.0
    assert config.min_predicted_savings_percent == 5.0
    assert config.min_prediction_confidence == 0.50
    assert config.upcoming_horizon_days == 30
    assert config.min_observations == 3


def test_buy_percentile_must_be_below_wait_percentile() -> None:
    with pytest.raises(ValidationError):
        RecommendationConfig(_env_file=None, buy_percentile_max=80, wait_percentile_min=70)


def test_strong_buy_percentile_cannot_exceed_buy_percentile() -> None:
    with pytest.raises(ValidationError):
        RecommendationConfig(_env_file=None, buy_percentile_max=20, buy_strong_percentile_max=25)


def test_get_recommendation_config_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    get_recommendation_config.cache_clear()
    try:
        monkeypatch.setenv("RECOMMENDATION_MIN_OBSERVATIONS", "4")
        first = get_recommendation_config()
        monkeypatch.setenv("RECOMMENDATION_MIN_OBSERVATIONS", "5")
        second = get_recommendation_config()
        assert first is second
        assert first.min_observations == 4
    finally:
        get_recommendation_config.cache_clear()
