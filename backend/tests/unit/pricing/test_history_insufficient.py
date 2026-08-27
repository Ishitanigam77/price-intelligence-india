"""Insufficient-history, missing observations, and stale freshness for Phase 7."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from app.pricing.enums import FreshnessStatus, InsufficientReasonCode, MetricStatus, TrendDirection
from tests.unit.pricing.helpers import NOW, VARIANT_A, history_engine, history_point

PRODUCT_ID = uuid4()


def _empty():
    return history_engine().compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        observations=[],
        as_of=NOW,
    )


def test_empty_history_does_not_fabricate_averages_or_extrema() -> None:
    result = _empty()
    for metric in (
        result.average_7d,
        result.average_30d,
        result.average_90d,
        result.average_180d,
        result.historical_low,
        result.historical_high,
        result.volatility,
        result.current_price_percentile,
        result.percentage_change,
    ):
        assert metric.status is MetricStatus.INSUFFICIENT_HISTORY
        assert metric.value is None
        assert metric.insufficient is not None
    assert result.price_drop.drop_occurred is None
    assert result.price_drop.status is MetricStatus.INSUFFICIENT_HISTORY
    assert result.trend.direction is TrendDirection.INSUFFICIENT_HISTORY
    assert result.current_observation is None
    assert result.data_freshness.status is FreshnessStatus.MISSING
    assert result.data_freshness.observed_at is None
    assert result.data_freshness.newest_observation is None


def test_single_observation_fills_averages_but_not_percentile_volatility_or_change() -> None:
    point = history_point(
        product_id=PRODUCT_ID,
        displayed_price="250.00",
        observed_at=NOW - timedelta(hours=1),
    )
    result = history_engine().compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        observations=[point],
        as_of=NOW,
    )
    assert result.average_7d.status is MetricStatus.AVAILABLE
    assert result.average_7d.value == Decimal("250.00")
    assert result.average_30d.value == Decimal("250.00")
    assert result.historical_low.value == Decimal("250.00")
    assert result.historical_high.value == Decimal("250.00")
    assert result.volatility.status is MetricStatus.INSUFFICIENT_HISTORY
    assert result.volatility.insufficient is not None
    assert (
        result.volatility.insufficient.code
        is InsufficientReasonCode.BELOW_MINIMUM_OBSERVATION_COUNT
    )
    assert result.current_price_percentile.status is MetricStatus.INSUFFICIENT_HISTORY
    assert result.percentage_change.status is MetricStatus.INSUFFICIENT_HISTORY
    assert result.percentage_change.insufficient is not None
    assert (
        result.percentage_change.insufficient.code is InsufficientReasonCode.NO_COMPARISON_BASELINE
    )
    assert result.trend.status is MetricStatus.INSUFFICIENT_HISTORY


def test_observation_outside_7_day_window_does_not_invent_a_7_day_average() -> None:
    point = history_point(
        product_id=PRODUCT_ID,
        displayed_price="250.00",
        observed_at=NOW - timedelta(days=20),
    )
    result = history_engine().compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        observations=[point],
        as_of=NOW,
    )
    assert result.average_7d.status is MetricStatus.INSUFFICIENT_HISTORY
    assert result.average_7d.value is None
    assert result.average_7d.insufficient is not None
    assert result.average_7d.insufficient.code is InsufficientReasonCode.NO_OBSERVATIONS_IN_WINDOW
    assert result.average_30d.status is MetricStatus.AVAILABLE
    assert result.average_30d.value == Decimal("250.00")
    assert result.average_90d.status is MetricStatus.AVAILABLE
    assert result.average_180d.status is MetricStatus.AVAILABLE


def test_stale_observation_keeps_its_real_timestamp() -> None:
    observed_at = NOW - timedelta(days=4)
    point = history_point(
        product_id=PRODUCT_ID,
        displayed_price="250.00",
        observed_at=observed_at,
    )
    result = history_engine().compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        observations=[point],
        as_of=NOW,
    )
    assert result.data_freshness.status is FreshnessStatus.STALE
    assert result.data_freshness.observed_at == observed_at
    assert result.data_freshness.newest_observation == observed_at
    assert result.data_freshness.as_of == NOW
    assert result.calculated_at == NOW


def test_fresh_observation_is_classified_from_actual_timestamp() -> None:
    observed_at = NOW - timedelta(hours=1)
    point = history_point(
        product_id=PRODUCT_ID,
        displayed_price="250.00",
        observed_at=observed_at,
    )
    result = history_engine().compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        observations=[point],
        as_of=NOW,
    )
    assert result.data_freshness.status is FreshnessStatus.FRESH
    assert result.data_freshness.observed_at == observed_at


def test_same_timestamp_observations_cannot_form_a_trend() -> None:
    listing = uuid4()
    points = [
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing,
            displayed_price="100.00",
            observed_at=NOW,
            created_at=NOW,
        ),
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing,
            seller_id=uuid4(),
            displayed_price="120.00",
            observed_at=NOW,
            created_at=NOW,
        ),
    ]
    result = history_engine().compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        observations=points,
        as_of=NOW,
    )
    assert result.trend.status is MetricStatus.INSUFFICIENT_HISTORY
    assert result.trend.insufficient is not None
    assert result.trend.insufficient.code is InsufficientReasonCode.ZERO_TIME_SPAN
    assert result.trend.implied_percent_change is None
