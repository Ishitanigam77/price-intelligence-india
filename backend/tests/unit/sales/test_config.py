"""SalesConfig validation."""

import pytest
from pydantic import ValidationError

from app.sales.config import SalesConfig, get_sales_config


def test_defaults_are_sane() -> None:
    config = SalesConfig(_env_file=None)
    assert config.drop_percent_threshold == 10.0
    assert config.min_listings_for_detection == 2
    assert config.max_gap_days == 2.0
    assert config.min_observations_for_sale_stats == 1
    assert config.high_confidence_listing_count == 5
    assert config.medium_confidence_listing_count == 2


def test_invalid_threshold_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SalesConfig(_env_file=None, drop_percent_threshold=0)


def test_get_sales_config_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    get_sales_config.cache_clear()
    try:
        monkeypatch.setenv("SALES_DROP_PERCENT_THRESHOLD", "15")
        first = get_sales_config()
        monkeypatch.setenv("SALES_DROP_PERCENT_THRESHOLD", "20")
        second = get_sales_config()
        assert first is second
        assert first.drop_percent_threshold == 15.0
    finally:
        get_sales_config.cache_clear()
