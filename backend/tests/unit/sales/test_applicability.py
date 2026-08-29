"""Unit tests for sale-event applicability to products and observations."""

from datetime import timedelta

from app.domain.enums import SaleEventType
from app.sales.applicability import (
    applicable_events,
    event_applies_to_product,
    observation_belongs_to_event,
    observations_during_event,
)
from tests.unit.sales.helpers import (
    BRAND_A,
    CATEGORY_A,
    NOW,
    RETAILER_A,
    RETAILER_B,
    event_record,
    observation,
)


def test_unscoped_seasonal_event_applies_to_any_product() -> None:
    event = event_record(event_type=SaleEventType.SEASONAL)
    assert event_applies_to_product(event, brand_id=BRAND_A, category_id=CATEGORY_A) is True
    assert event_applies_to_product(event, brand_id=None, category_id=None) is True


def test_brand_event_does_not_apply_to_other_brand() -> None:
    event = event_record(event_type=SaleEventType.BRAND, brand_id=BRAND_A)
    assert event_applies_to_product(event, brand_id=BRAND_A, category_id=CATEGORY_A) is True
    other_brand = event_record(event_type=SaleEventType.BRAND).brand_id
    assert other_brand is not None
    assert (
        event_applies_to_product(event, brand_id=other_brand, category_id=CATEGORY_A) is False
        or event.brand_id == other_brand
    )
    from uuid import uuid4

    assert event_applies_to_product(event, brand_id=uuid4(), category_id=CATEGORY_A) is False


def test_retailer_specific_event_excludes_other_retailer_when_scoped() -> None:
    event = event_record(event_type=SaleEventType.RETAILER_SPECIFIC, retailer_id=RETAILER_A)
    assert (
        event_applies_to_product(
            event, brand_id=BRAND_A, category_id=CATEGORY_A, retailer_id=RETAILER_A
        )
        is True
    )
    assert (
        event_applies_to_product(
            event, brand_id=BRAND_A, category_id=CATEGORY_A, retailer_id=RETAILER_B
        )
        is False
    )


def test_observation_must_fall_inside_window() -> None:
    event = event_record(
        event_type=SaleEventType.SEASONAL,
        start_date=NOW,
        end_date=NOW + timedelta(days=2),
    )
    inside = observation(observed_at=NOW + timedelta(days=1))
    outside = observation(observed_at=NOW + timedelta(days=5))
    assert (
        observation_belongs_to_event(
            event, inside.observation, brand_id=BRAND_A, category_id=CATEGORY_A
        )
        is True
    )
    assert (
        observation_belongs_to_event(
            event, outside.observation, brand_id=BRAND_A, category_id=CATEGORY_A
        )
        is False
    )


def test_observations_during_event_filters_and_orders() -> None:
    event = event_record(
        event_type=SaleEventType.RETAILER_SPECIFIC,
        retailer_id=RETAILER_A,
        start_date=NOW,
        end_date=NOW + timedelta(days=3),
    )
    later = observation(observed_at=NOW + timedelta(days=2), retailer_id=RETAILER_A)
    earlier = observation(observed_at=NOW + timedelta(hours=1), retailer_id=RETAILER_A)
    other_retailer = observation(observed_at=NOW + timedelta(days=1), retailer_id=RETAILER_B)
    matching = observations_during_event(event, [later, earlier, other_retailer])
    assert [point.snapshot_id for point in matching] == [
        earlier.observation.snapshot_id,
        later.observation.snapshot_id,
    ]


def test_applicable_events_filters_brand_mismatch() -> None:
    from uuid import uuid4

    matching = event_record(event_type=SaleEventType.BRAND, brand_id=BRAND_A)
    other = event_record(event_type=SaleEventType.BRAND, brand_id=uuid4())
    result = applicable_events([matching, other], brand_id=BRAND_A, category_id=CATEGORY_A)
    assert [event.id for event in result] == [matching.id]
