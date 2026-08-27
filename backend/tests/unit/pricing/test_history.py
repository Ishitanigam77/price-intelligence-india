"""Phase 7 historical price intelligence: averages, extrema, percentile, drop, trend."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from app.domain.enums import ConfidenceLevel
from app.pricing.enums import MetricStatus, TrendDirection, ValueKind
from app.pricing.history_models import PRICE_DROP_BASELINE_DESCRIPTION
from tests.unit.pricing.helpers import (
    NOW,
    RETAILER_A,
    RETAILER_B,
    VARIANT_A,
    VARIANT_B,
    history_engine,
    history_point,
)

PRODUCT_ID = uuid4()
LISTING_A = uuid4()
LISTING_B = uuid4()
SELLER_A = uuid4()
SELLER_B = uuid4()


def _series():
    """Six verified observations on listing A, plus one unverified and one other-variant row."""
    return [
        history_point(
            product_id=PRODUCT_ID,
            variant_id=VARIANT_A,
            listing_id=LISTING_A,
            seller_id=SELLER_A,
            displayed_price="600.00",
            observed_at=NOW - timedelta(days=200),
            source_url="https://fictional-mart-a.example.test/old",
        ),
        history_point(
            product_id=PRODUCT_ID,
            variant_id=VARIANT_A,
            listing_id=LISTING_A,
            seller_id=SELLER_A,
            displayed_price="500.00",
            observed_at=NOW - timedelta(days=100),
        ),
        history_point(
            product_id=PRODUCT_ID,
            variant_id=VARIANT_A,
            listing_id=LISTING_A,
            seller_id=SELLER_A,
            displayed_price="400.00",
            observed_at=NOW - timedelta(days=40),
        ),
        history_point(
            product_id=PRODUCT_ID,
            variant_id=VARIANT_A,
            listing_id=LISTING_A,
            seller_id=SELLER_A,
            displayed_price="300.00",
            observed_at=NOW - timedelta(days=10),
        ),
        history_point(
            product_id=PRODUCT_ID,
            variant_id=VARIANT_A,
            listing_id=LISTING_A,
            seller_id=SELLER_A,
            displayed_price="200.00",
            observed_at=NOW - timedelta(days=3),
        ),
        history_point(
            product_id=PRODUCT_ID,
            variant_id=VARIANT_A,
            listing_id=LISTING_A,
            seller_id=SELLER_A,
            displayed_price="100.00",
            observed_at=NOW,
            source_url="https://fictional-mart-a.example.test/current",
        ),
        history_point(
            product_id=PRODUCT_ID,
            variant_id=VARIANT_A,
            listing_id=LISTING_A,
            seller_id=SELLER_A,
            displayed_price="1.00",
            observed_at=NOW - timedelta(days=1),
            confidence=ConfidenceLevel.LOW,
        ),
        history_point(
            product_id=PRODUCT_ID,
            variant_id=VARIANT_B,
            listing_id=uuid4(),
            displayed_price="50.00",
            observed_at=NOW,
        ),
    ]


def _variant_history(points=None):
    engine = history_engine()
    return engine.compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        observations=points if points is not None else _series()[:7],
        variant_key="128gb-black",
        as_of=NOW,
    )


def test_window_averages_use_only_qualifying_observations_in_each_window() -> None:
    result = _variant_history()
    assert result.average_7d.status is MetricStatus.AVAILABLE
    assert result.average_7d.value == Decimal("150.00")
    assert result.average_7d.window_days == 7
    assert result.average_7d.value_kind is ValueKind.CALCULATED
    assert result.average_7d.observation_count == 2

    assert result.average_30d.value == Decimal("200.00")
    assert result.average_30d.window_days == 30
    assert result.average_30d.observation_count == 3

    assert result.average_90d.value == Decimal("250.00")
    assert result.average_90d.observation_count == 4

    assert result.average_180d.value == Decimal("300.00")
    assert result.average_180d.observation_count == 5


def test_low_confidence_observation_is_stored_but_excluded_from_calculations() -> None:
    result = _variant_history()
    assert result.qualifying_observation_count == 6
    assert result.excluded_unverified_observation_count == 1
    assert any(point.displayed_price == Decimal("1.00") for point in result.observations)
    assert all(
        point.displayed_price != Decimal("1.00") or not point.qualifies_for_calculations
        for point in result.observations
    )
    # A 1.00 unverified price must not pull the 7-day average down.
    assert result.average_7d.value == Decimal("150.00")


def test_historical_min_and_max_keep_observation_provenance() -> None:
    result = _variant_history()
    assert result.historical_low.status is MetricStatus.AVAILABLE
    assert result.historical_low.value == Decimal("100.00")
    assert result.historical_low.observed_at == NOW
    assert result.historical_low.retailer_id == RETAILER_A
    assert result.historical_low.seller_id == SELLER_A
    assert result.historical_low.source_url == "https://fictional-mart-a.example.test/current"
    assert result.historical_low.value_kind is ValueKind.CALCULATED

    assert result.historical_high.value == Decimal("600.00")
    assert result.historical_high.observed_at == NOW - timedelta(days=200)


def test_percentile_ranks_current_price_among_qualifying_history() -> None:
    result = _variant_history()
    assert result.current_price_percentile.status is MetricStatus.AVAILABLE
    # Current 100 is the lowest of 6 qualifying prices → 1/6 * 100
    assert result.current_price_percentile.value == Decimal("16.6667")
    assert result.current_price_percentile.unit == "percentile"


def test_volatility_is_sample_standard_deviation() -> None:
    result = _variant_history()
    assert result.volatility.status is MetricStatus.AVAILABLE
    assert result.volatility.value is not None
    assert result.volatility.value > Decimal("0.00")
    assert result.volatility.observation_count == 6
    assert "mean" in result.volatility.extra
    assert "coefficient_of_variation" in result.volatility.extra


def test_percentage_change_and_price_drop_use_same_listing_seller_baseline() -> None:
    result = _variant_history()
    assert result.percentage_change.status is MetricStatus.AVAILABLE
    assert result.percentage_change.value == Decimal("-50.0000")
    assert result.price_drop.status is MetricStatus.AVAILABLE
    assert result.price_drop.drop_occurred is True
    assert result.price_drop.percentage_change == Decimal("-50.0000")
    assert result.price_drop.current_price == Decimal("100.00")
    assert result.price_drop.baseline_price == Decimal("200.00")
    assert result.price_drop.baseline_description == PRICE_DROP_BASELINE_DESCRIPTION
    assert result.price_drop.value_kind is ValueKind.CALCULATED


def test_price_increase_is_not_classified_as_a_drop() -> None:
    listing = uuid4()
    points = [
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing,
            displayed_price="80.00",
            observed_at=NOW - timedelta(days=2),
        ),
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing,
            displayed_price="100.00",
            observed_at=NOW,
        ),
    ]
    result = _variant_history(points)
    assert result.price_drop.drop_occurred is False
    assert result.percentage_change.value == Decimal("25.0000")


def test_trend_is_calculated_falling_not_predicted() -> None:
    result = _variant_history()
    assert result.trend.status is MetricStatus.AVAILABLE
    assert result.trend.direction is TrendDirection.FALLING
    assert result.trend.value_kind is ValueKind.CALCULATED
    assert result.trend.implied_percent_change is not None
    assert result.trend.implied_percent_change < 0
    assert "forecast" not in result.trend.method.lower() or "not a forecast" in result.trend.method


def test_stable_trend_when_implied_change_is_inside_configured_band() -> None:
    listing = uuid4()
    points = [
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing,
            displayed_price="100.00",
            observed_at=NOW - timedelta(days=10),
        ),
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing,
            displayed_price="101.00",
            observed_at=NOW,
        ),
    ]
    result = _variant_history(points)
    assert result.trend.direction is TrendDirection.STABLE


def test_effective_price_is_used_for_analysis_when_recorded() -> None:
    listing = uuid4()
    points = [
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing,
            displayed_price="200.00",
            effective_price="150.00",
            observed_at=NOW - timedelta(days=1),
        ),
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing,
            displayed_price="180.00",
            effective_price="120.00",
            observed_at=NOW,
        ),
    ]
    result = _variant_history(points)
    assert result.average_7d.value == Decimal("135.00")
    assert result.current_observation is not None
    assert result.current_observation.analysis_price_field == "effective_price"
    assert result.current_observation.value_kind is ValueKind.OBSERVED


def test_multiple_retailers_are_kept_as_distinct_observations() -> None:
    listing_a = uuid4()
    listing_b = uuid4()
    points = [
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing_a,
            retailer_id=RETAILER_A,
            retailer_slug="fictional-mart-a",
            displayed_price="100.00",
            observed_at=NOW - timedelta(days=1),
        ),
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing_b,
            retailer_id=RETAILER_B,
            retailer_slug="fictional-mart-b",
            displayed_price="200.00",
            observed_at=NOW,
        ),
    ]
    result = _variant_history(points)
    slugs = {point.retailer_slug for point in result.observations}
    assert slugs == {"fictional-mart-a", "fictional-mart-b"}
    assert result.average_7d.value == Decimal("150.00")
    # Drop baseline is listing+seller of the current (B) observation — A is a different listing.
    assert result.price_drop.status is MetricStatus.INSUFFICIENT_HISTORY
    assert result.price_drop.insufficient is not None
    assert result.price_drop.insufficient.code.value == "no_comparison_baseline"


def test_multiple_sellers_are_not_merged_for_drop_detection() -> None:
    listing = uuid4()
    points = [
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing,
            seller_id=SELLER_A,
            displayed_price="300.00",
            observed_at=NOW - timedelta(days=2),
        ),
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing,
            seller_id=SELLER_B,
            displayed_price="100.00",
            observed_at=NOW - timedelta(days=1),
        ),
        history_point(
            product_id=PRODUCT_ID,
            listing_id=listing,
            seller_id=SELLER_A,
            displayed_price="280.00",
            observed_at=NOW,
        ),
    ]
    result = _variant_history(points)
    assert result.price_drop.drop_occurred is True
    assert result.price_drop.baseline_price == Decimal("300.00")
    assert result.price_drop.current_price == Decimal("280.00")
    assert result.price_drop.baseline_seller_id == SELLER_A


def test_variant_isolation_does_not_mix_storage_or_color() -> None:
    engine = history_engine()
    cheap_other = history_point(
        product_id=PRODUCT_ID,
        variant_id=VARIANT_B,
        displayed_price="10.00",
        observed_at=NOW,
    )
    target = history_point(
        product_id=PRODUCT_ID,
        variant_id=VARIANT_A,
        listing_id=LISTING_A,
        displayed_price="500.00",
        observed_at=NOW,
    )
    history = engine.compute_product(
        PRODUCT_ID,
        {VARIANT_A: [target], VARIANT_B: [cheap_other]},
        as_of=NOW,
    )
    by_id = {item.product_variant_id: item for item in history.variants}
    assert by_id[VARIANT_A].historical_low.value == Decimal("500.00")
    assert by_id[VARIANT_B].historical_low.value == Decimal("10.00")
    assert by_id[VARIANT_A].average_7d.value == Decimal("500.00")


def test_provenance_separates_observed_calculated_and_absent_predicted() -> None:
    result = _variant_history()
    assert result.provenance.observations_value_kind is ValueKind.OBSERVED
    assert result.provenance.calculations_value_kind is ValueKind.CALCULATED
    assert result.provenance.predicted is None
    assert result.provenance.predicted_value_kind is None
    dumped = result.model_dump()
    assert dumped["provenance"]["predicted"] is None
    for point in result.observations:
        assert point.value_kind is ValueKind.OBSERVED
    for metric in (
        result.average_7d,
        result.average_30d,
        result.average_90d,
        result.average_180d,
        result.historical_low,
        result.historical_high,
        result.current_price_percentile,
        result.volatility,
        result.percentage_change,
    ):
        assert metric.value_kind is ValueKind.CALCULATED
    assert result.price_drop.value_kind is ValueKind.CALCULATED
    assert result.trend.value_kind is ValueKind.CALCULATED


def test_product_history_never_includes_a_predicted_payload() -> None:
    history = history_engine().compute_product(PRODUCT_ID, {VARIANT_A: _series()[:6]}, as_of=NOW)
    assert history.predicted is None
    payload = history.model_dump()
    assert payload["predicted"] is None
    serialized = str(payload)
    assert "PREDICTED" not in serialized.replace("predicted", "")
