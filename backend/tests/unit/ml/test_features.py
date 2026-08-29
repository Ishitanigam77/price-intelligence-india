"""Feature engineering: cutoff availability and missing-feature handling."""

from datetime import timedelta

from app.domain.enums import ConfidenceLevel
from tests.unit.ml.helpers import ANCHOR, engineer, event_record, observation, seed_ids


def test_current_price_uses_latest_observation_strictly_before_as_of() -> None:
    listing_id, variant_id = seed_ids()
    points = [
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="500.00",
            effective_price="500.00",
            observed_at=ANCHOR,
        ),
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="400.00",
            effective_price="400.00",
            observed_at=ANCHOR + timedelta(days=10),
        ),
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="300.00",
            effective_price="300.00",
            observed_at=ANCHOR + timedelta(days=20),
        ),
    ]
    as_of = ANCHOR + timedelta(days=20)
    vector = engineer().build(points, [], as_of=as_of)
    assert vector is not None
    assert vector.numeric["current_price"] == 400.0
    assert vector.numeric["historical_low"] == 400.0
    assert vector.numeric["historical_high"] == 500.0
    assert vector.available["current_price"] is True


def test_observation_at_as_of_is_not_available() -> None:
    listing_id, variant_id = seed_ids()
    points = [
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="100.00",
            effective_price="100.00",
            observed_at=ANCHOR,
        ),
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="1.00",
            effective_price="1.00",
            observed_at=ANCHOR + timedelta(days=5),
        ),
    ]
    vector = engineer().build(points, [], as_of=ANCHOR + timedelta(days=5))
    assert vector is not None
    assert vector.numeric["current_price"] == 100.0
    assert vector.numeric["historical_low"] != 1.0


def test_missing_window_average_is_none_not_zero_filled() -> None:
    point = observation(
        displayed_price="999.00",
        effective_price="999.00",
        observed_at=ANCHOR,
    )
    vector = engineer().build([point], [], as_of=ANCHOR + timedelta(hours=1))
    assert vector is not None
    assert vector.numeric["current_price"] == 999.0
    # A 90-day average still exists because the single point is inside the window.
    assert vector.numeric["avg_90d"] == 999.0
    assert vector.numeric["previous_sale_price"] is None
    assert vector.available["previous_sale_price"] is False
    assert vector.numeric["days_until_sale"] is None
    assert vector.available["days_until_sale"] is False
    assert vector.numeric["previous_sale_count"] == 0.0
    assert vector.available["previous_sale_count"] is True


def test_known_curated_sale_populates_days_until_sale() -> None:
    point = observation(
        displayed_price="900.00",
        effective_price="900.00",
        observed_at=ANCHOR,
    )
    sale = event_record(
        start_date=ANCHOR + timedelta(days=10), end_date=ANCHOR + timedelta(days=17)
    )
    vector = engineer().build([point], [sale], as_of=ANCHOR + timedelta(days=3))
    assert vector is not None
    assert vector.numeric["days_until_sale"] == 7.0
    assert vector.categorical["sale_event_id"] == str(sale.id)
    assert vector.categorical["sale_event_type"] == sale.event_type.value


def test_seasonal_time_features_come_from_as_of() -> None:
    point = observation(displayed_price="10.00", effective_price="10.00", observed_at=ANCHOR)
    as_of = ANCHOR + timedelta(days=1)  # 2024-01-16 is a Tuesday
    vector = engineer().build([point], [], as_of=as_of)
    assert vector is not None
    assert vector.numeric["month"] == 1.0
    assert vector.numeric["day_of_week"] == float(as_of.weekday())
    assert vector.numeric["is_weekend"] in {0.0, 1.0}


def test_no_history_returns_none_vector() -> None:
    point = observation(displayed_price="10.00", effective_price="10.00", observed_at=ANCHOR)
    assert engineer().build([point], [], as_of=ANCHOR) is None
    assert engineer().build([], [], as_of=ANCHOR + timedelta(days=1)) is None


def test_previous_sale_uses_completed_window_only() -> None:
    listing_id, variant_id = seed_ids()
    first_sale = event_record(
        start_date=ANCHOR + timedelta(days=10),
        end_date=ANCHOR + timedelta(days=16),
    )
    second_sale = event_record(
        start_date=ANCHOR + timedelta(days=40),
        end_date=ANCHOR + timedelta(days=46),
    )
    points = [
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="1000.00",
            effective_price="1000.00",
            observed_at=ANCHOR + timedelta(days=1),
        ),
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="800.00",
            effective_price="800.00",
            observed_at=ANCHOR + timedelta(days=12),
        ),
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="1000.00",
            effective_price="1000.00",
            observed_at=ANCHOR + timedelta(days=20),
        ),
    ]
    vector = engineer().build(points, [first_sale, second_sale], as_of=second_sale.start_date)
    assert vector is not None
    assert vector.numeric["previous_sale_price"] == 800.0
    assert vector.numeric["previous_sale_low"] == 800.0
    assert vector.numeric["previous_sale_count"] == 1.0
    assert vector.numeric["current_price"] == 1000.0


def test_low_confidence_observation_is_excluded() -> None:
    listing_id, variant_id = seed_ids()
    points = [
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="50.00",
            effective_price="50.00",
            observed_at=ANCHOR,
            confidence=ConfidenceLevel.LOW,
        ),
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="200.00",
            effective_price="200.00",
            observed_at=ANCHOR + timedelta(days=1),
        ),
    ]
    vector = engineer().build(points, [], as_of=ANCHOR + timedelta(days=2))
    assert vector is not None
    assert vector.numeric["current_price"] == 200.0
    assert vector.numeric["historical_low"] == 200.0
