"""Integration tests for sale-event persistence and repository filters."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.domain.enums import SaleEventSource, SaleEventStatus, SaleEventType
from app.domain.exceptions import InvalidSaleEventError
from app.repositories.sale_event_repository import SaleEventRepository
from tests.factories import make_brand, make_category, make_retailer, make_sale_event


def test_sale_event_round_trips_and_filters_by_status(db_session: Session) -> None:
    now = datetime.now(UTC)
    retailer = make_retailer()
    brand = make_brand()
    category = make_category()
    db_session.add_all([retailer, brand, category])
    db_session.flush()

    past = make_sale_event(
        name="FIXTURE: Past Seasonal Sale",
        start_date=now - timedelta(days=20),
        end_date=now - timedelta(days=10),
    )
    current = make_sale_event(
        name="FIXTURE: Current Retailer Sale",
        event_type=SaleEventType.RETAILER_SPECIFIC,
        retailer=retailer,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=1),
    )
    upcoming = make_sale_event(
        name="FIXTURE: Upcoming Brand Sale",
        event_type=SaleEventType.BRAND,
        brand=brand,
        start_date=now + timedelta(days=5),
        end_date=now + timedelta(days=8),
    )
    db_session.add_all([past, current, upcoming])
    db_session.flush()

    repo = SaleEventRepository(db_session)
    before = repo.list_filtered(status=SaleEventStatus.BEFORE_EVENT, at=now)
    during = repo.list_filtered(status=SaleEventStatus.DURING_EVENT, at=now)
    after = repo.list_filtered(status=SaleEventStatus.AFTER_EVENT, at=now)
    assert [event.name for event in before] == ["FIXTURE: Upcoming Brand Sale"]
    assert [event.name for event in during] == ["FIXTURE: Current Retailer Sale"]
    assert [event.name for event in after] == ["FIXTURE: Past Seasonal Sale"]

    upcoming_page = repo.list_upcoming(at=now)
    assert [event.name for event in upcoming_page] == ["FIXTURE: Upcoming Brand Sale"]

    by_type = repo.list_filtered(event_type=SaleEventType.RETAILER_SPECIFIC)
    assert [event.id for event in by_type] == [current.id]


def test_invalid_scope_is_rejected_on_insert(db_session: Session) -> None:
    now = datetime.now(UTC)
    event = make_sale_event(
        name="FIXTURE: Invalid Retailer Sale",
        event_type=SaleEventType.RETAILER_SPECIFIC,
        start_date=now,
        end_date=now + timedelta(days=1),
    )
    db_session.add(event)
    with pytest.raises(InvalidSaleEventError):
        db_session.flush()


def test_externally_sourced_fixture_requires_source_ref(db_session: Session) -> None:
    now = datetime.now(UTC)
    event = make_sale_event(
        name="FIXTURE: Partner Calendar Event",
        event_type=SaleEventType.EXTERNALLY_SOURCED,
        source=SaleEventSource.PRODUCT_FEED,
        source_ref="test.fixture.partner-calendar",
        start_date=now + timedelta(days=30),
        end_date=now + timedelta(days=33),
    )
    db_session.add(event)
    db_session.flush()
    loaded = SaleEventRepository(db_session).get_by_id(event.id)
    assert loaded is not None
    assert loaded.source is SaleEventSource.PRODUCT_FEED
    assert loaded.source_ref == "test.fixture.partner-calendar"
