"""Unit tests for historical sale-price analysis."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from app.domain.enums import ConfidenceLevel, SaleEventType
from app.pricing.enums import MetricStatus, ValueKind
from app.sales.enums import SaleInsufficientReasonCode
from tests.unit.sales.helpers import (
    BRAND_A,
    CATEGORY_A,
    NOW,
    PRODUCT_ID,
    RETAILER_A,
    VARIANT_A,
    VARIANT_B,
    event_record,
    history_engine,
    observation,
)


def test_no_events_reports_insufficient_and_never_predicts() -> None:
    engine = history_engine()
    points = [
        observation(displayed_price="500.00", observed_at=NOW - timedelta(days=3)),
        observation(displayed_price="400.00", observed_at=NOW - timedelta(days=1)),
    ]
    history = engine.compute_product(
        PRODUCT_ID,
        {VARIANT_A: points},
        events=(),
        brand_id=BRAND_A,
        category_id=CATEGORY_A,
        variant_keys={VARIANT_A: "color=black|storage=128gb"},
    )
    assert history.predicted is None
    assert history.provenance.predicted is None
    assert history.events == ()
    variant = history.variants[0]
    assert variant.overall_sale_average.status is MetricStatus.INSUFFICIENT_HISTORY
    assert variant.overall_sale_average.value_kind is ValueKind.CALCULATED
    assert variant.overall_sale_average.value is None
    assert (
        variant.overall_sale_average.insufficient.code
        is SaleInsufficientReasonCode.NO_APPLICABLE_EVENTS
    )
    assert variant.non_sale_baseline.status is MetricStatus.AVAILABLE
    assert variant.non_sale_baseline.value == Decimal("450.00")


def test_in_window_observations_are_observed_and_stats_are_calculated() -> None:
    engine = history_engine()
    event = event_record(
        event_type=SaleEventType.SEASONAL,
        start_date=NOW - timedelta(days=4),
        end_date=NOW - timedelta(days=1),
    )
    listing = uuid4()
    before = observation(
        displayed_price="1000.00",
        observed_at=NOW - timedelta(days=10),
        listing_id=listing,
    )
    during_high = observation(
        displayed_price="800.00",
        observed_at=NOW - timedelta(days=3),
        listing_id=listing,
    )
    during_low = observation(
        displayed_price="600.00",
        observed_at=NOW - timedelta(days=2),
        listing_id=listing,
    )
    after = observation(
        displayed_price="900.00",
        observed_at=NOW - timedelta(hours=1),
        listing_id=listing,
    )
    history = engine.compute_product(
        PRODUCT_ID,
        {VARIANT_A: [before, during_high, during_low, after]},
        events=[event],
        brand_id=BRAND_A,
        category_id=CATEGORY_A,
    )
    variant = history.variants[0]
    window = variant.event_windows[0]
    assert [point.value_kind for point in window.observations] == [
        ValueKind.OBSERVED,
        ValueKind.OBSERVED,
    ]
    assert window.sale_average.value_kind is ValueKind.CALCULATED
    assert window.sale_average.status is MetricStatus.AVAILABLE
    assert window.sale_average.value == Decimal("700.00")
    assert window.sale_low.value == Decimal("600.00")
    assert window.sale_high.value == Decimal("800.00")
    assert variant.non_sale_baseline.value == Decimal("950.00")
    assert variant.vs_non_sale_baseline_percent.status is MetricStatus.AVAILABLE
    assert history.predicted is None


def test_low_confidence_observations_are_excluded() -> None:
    engine = history_engine()
    event = event_record(
        event_type=SaleEventType.SEASONAL,
        start_date=NOW - timedelta(days=2),
        end_date=NOW + timedelta(days=1),
    )
    unverified = observation(
        displayed_price="100.00",
        observed_at=NOW - timedelta(days=1),
        confidence=ConfidenceLevel.LOW,
    )
    history = engine.compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        points=[unverified],
        events=[event],
    )
    assert history.qualifying_observation_count == 0
    assert history.excluded_unverified_observation_count == 1
    assert history.event_windows[0].observation_count == 0
    assert (
        history.event_windows[0].sale_average.insufficient.code
        is SaleInsufficientReasonCode.NO_OBSERVATIONS_DURING_EVENT
    )


def test_variants_are_never_merged() -> None:
    engine = history_engine()
    event = event_record(
        event_type=SaleEventType.SEASONAL,
        start_date=NOW - timedelta(days=2),
        end_date=NOW + timedelta(days=1),
    )
    a = observation(
        variant_id=VARIANT_A, displayed_price="100.00", observed_at=NOW - timedelta(days=1)
    )
    b = observation(
        variant_id=VARIANT_B, displayed_price="500.00", observed_at=NOW - timedelta(days=1)
    )
    history = engine.compute_product(
        PRODUCT_ID,
        {VARIANT_A: [a], VARIANT_B: [b]},
        events=[event],
        brand_id=BRAND_A,
        category_id=CATEGORY_A,
    )
    by_id = {variant.product_variant_id: variant for variant in history.variants}
    assert by_id[VARIANT_A].overall_sale_average.value == Decimal("100.00")
    assert by_id[VARIANT_B].overall_sale_average.value == Decimal("500.00")


def test_retailer_event_ignores_other_retailer_prices() -> None:
    from tests.unit.sales.helpers import RETAILER_B

    engine = history_engine()
    event = event_record(
        event_type=SaleEventType.RETAILER_SPECIFIC,
        retailer_id=RETAILER_A,
        start_date=NOW - timedelta(days=2),
        end_date=NOW + timedelta(days=1),
    )
    own = observation(
        retailer_id=RETAILER_A,
        displayed_price="200.00",
        observed_at=NOW - timedelta(days=1),
    )
    other = observation(
        retailer_id=RETAILER_B,
        displayed_price="50.00",
        observed_at=NOW - timedelta(days=1),
    )
    variant = engine.compute_variant(
        product_id=PRODUCT_ID,
        product_variant_id=VARIANT_A,
        points=[own, other],
        events=[event],
    )
    assert variant.event_windows[0].sale_average.value == Decimal("200.00")
    assert variant.event_windows[0].observation_count == 1
