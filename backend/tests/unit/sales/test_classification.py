"""MAJOR / ORDINARY / UNKNOWN classification from evidence, not hardcoded names."""

from datetime import timedelta

from app.domain.enums import SaleEventType, SaleSeverity
from app.sales.classification import classify_family
from tests.unit.sales.helpers import NOW, RETAILER_A, event_record, observation, sales_config


def test_recurring_seasonal_drop_is_major() -> None:
    events = [
        event_record(
            name="FIXTURE: Fictional Seasonal Sale 2024",
            event_type=SaleEventType.SEASONAL,
            start_date=NOW.replace(year=2024, month=10, day=1),
            end_date=NOW.replace(year=2024, month=10, day=8),
        ),
        event_record(
            name="FIXTURE: Fictional Seasonal Sale 2025",
            event_type=SaleEventType.SEASONAL,
            start_date=NOW.replace(year=2025, month=10, day=1),
            end_date=NOW.replace(year=2025, month=10, day=8),
        ),
    ]
    points = []
    for year in (2024, 2025):
        start = NOW.replace(year=year, month=10, day=1)
        points.append(
            observation(
                displayed_price="1000.00",
                effective_price="1000.00",
                observed_at=start - timedelta(days=5),
            )
        )
        points.append(
            observation(
                displayed_price="800.00",
                effective_price="800.00",
                observed_at=start + timedelta(days=1),
            )
        )
    assert classify_family(events, points, config=sales_config()) is SaleSeverity.MAJOR


def test_short_retailer_promo_is_ordinary() -> None:
    events = [
        event_record(
            name="FIXTURE: Fictional Weekend Promo",
            event_type=SaleEventType.RETAILER_SPECIFIC,
            retailer_id=RETAILER_A,
            start_date=NOW.replace(year=2025, month=6, day=6),
            end_date=NOW.replace(year=2025, month=6, day=7),
        )
    ]
    assert classify_family(events, (), config=sales_config()) is SaleSeverity.ORDINARY


def test_thin_one_off_event_is_unknown() -> None:
    events = [
        event_record(
            name="FIXTURE: One-off blip",
            event_type=SaleEventType.BRAND,
            start_date=NOW,
            end_date=NOW + timedelta(hours=6),
        )
    ]
    assert classify_family(events, (), config=sales_config()) is SaleSeverity.UNKNOWN


def test_classification_does_not_key_off_festival_names() -> None:
    events = [
        event_record(
            name="Diwali Dhamaka",
            event_type=SaleEventType.RETAILER_SPECIFIC,
            retailer_id=RETAILER_A,
            start_date=NOW.replace(year=2025, month=10, day=20),
            end_date=NOW.replace(year=2025, month=10, day=21),
        )
    ]
    assert classify_family(events, (), config=sales_config()) is SaleSeverity.ORDINARY


def test_empty_family_is_unknown() -> None:
    assert classify_family((), ()) is SaleSeverity.UNKNOWN
