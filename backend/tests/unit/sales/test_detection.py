"""Unit tests for calculated sale-window detection from observed price drops."""

from datetime import timedelta
from uuid import uuid4

from app.domain.enums import SaleEventSource, SaleEventType
from app.pricing.enums import ValueKind
from tests.unit.sales.helpers import NOW, RETAILER_A, detector, observation, sales_config


def test_concurrent_drops_across_listings_emit_calculated_window() -> None:
    listing_a = uuid4()
    listing_b = uuid4()
    points = [
        observation(
            listing_id=listing_a,
            displayed_price="1000.00",
            observed_at=NOW - timedelta(days=10),
        ),
        observation(
            listing_id=listing_b,
            displayed_price="1000.00",
            observed_at=NOW - timedelta(days=10),
        ),
        observation(
            listing_id=listing_a,
            displayed_price="700.00",
            observed_at=NOW - timedelta(days=2),
        ),
        observation(
            listing_id=listing_b,
            displayed_price="650.00",
            observed_at=NOW - timedelta(days=2, hours=6),
        ),
    ]
    windows = detector().detect(points)
    retailer_windows = [
        item for item in windows if item.event_type is SaleEventType.RETAILER_SPECIFIC
    ]
    assert len(retailer_windows) == 1
    window = retailer_windows[0]
    assert window.value_kind is ValueKind.CALCULATED
    assert window.source is SaleEventSource.OBSERVED_PRICE_INFERENCE
    assert window.retailer_id == RETAILER_A
    assert window.listing_count == 2
    assert window.name.startswith("Detected retailer sale ")
    assert "Billion" not in window.name
    assert "festival" not in window.name.lower()


def test_single_listing_drop_is_not_enough_by_default() -> None:
    listing = uuid4()
    points = [
        observation(
            listing_id=listing,
            displayed_price="1000.00",
            observed_at=NOW - timedelta(days=8),
        ),
        observation(
            listing_id=listing,
            displayed_price="500.00",
            observed_at=NOW - timedelta(days=1),
        ),
    ]
    windows = detector().detect(points)
    assert [item for item in windows if item.event_type is SaleEventType.RETAILER_SPECIFIC] == []


def test_small_change_below_threshold_is_not_a_sale_window() -> None:
    listing_a = uuid4()
    listing_b = uuid4()
    points = [
        observation(
            listing_id=listing_a,
            displayed_price="1000.00",
            observed_at=NOW - timedelta(days=8),
        ),
        observation(
            listing_id=listing_b,
            displayed_price="1000.00",
            observed_at=NOW - timedelta(days=8),
        ),
        observation(
            listing_id=listing_a,
            displayed_price="980.00",
            observed_at=NOW - timedelta(days=1),
        ),
        observation(
            listing_id=listing_b,
            displayed_price="990.00",
            observed_at=NOW - timedelta(days=1),
        ),
    ]
    windows = detector(sales_config(drop_percent_threshold=10.0)).detect(points)
    assert windows == ()


def test_empty_history_yields_no_detected_events() -> None:
    assert detector().detect([]) == ()
