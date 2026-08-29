"""Engine facade: upcoming events and status views."""

from datetime import timedelta

from app.domain.enums import SaleEventStatus
from tests.unit.sales.helpers import NOW, engine, event_record


def test_upcoming_returns_only_before_event_in_start_order() -> None:
    past = event_record(
        name="FIXTURE: Past Sale",
        start_date=NOW - timedelta(days=10),
        end_date=NOW - timedelta(days=5),
    )
    current = event_record(
        name="FIXTURE: Current Sale",
        start_date=NOW - timedelta(days=1),
        end_date=NOW + timedelta(days=1),
    )
    later = event_record(
        name="FIXTURE: Later Sale",
        start_date=NOW + timedelta(days=10),
        end_date=NOW + timedelta(days=12),
    )
    sooner = event_record(
        name="FIXTURE: Soon Sale",
        start_date=NOW + timedelta(days=3),
        end_date=NOW + timedelta(days=4),
    )
    views = engine().upcoming([past, current, later, sooner], at=NOW)
    assert [item.event.name for item in views] == ["FIXTURE: Soon Sale", "FIXTURE: Later Sale"]
    assert all(item.status is SaleEventStatus.BEFORE_EVENT for item in views)


def test_views_cover_all_three_statuses() -> None:
    records = [
        event_record(start_date=NOW - timedelta(days=5), end_date=NOW - timedelta(days=1)),
        event_record(start_date=NOW - timedelta(hours=1), end_date=NOW + timedelta(hours=1)),
        event_record(start_date=NOW + timedelta(days=1), end_date=NOW + timedelta(days=2)),
    ]
    statuses = [view.status for view in engine().views(records, at=NOW)]
    assert statuses == [
        SaleEventStatus.AFTER_EVENT,
        SaleEventStatus.DURING_EVENT,
        SaleEventStatus.BEFORE_EVENT,
    ]
