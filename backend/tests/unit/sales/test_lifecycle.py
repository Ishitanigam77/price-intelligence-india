"""Unit tests for sale-event lifecycle status."""

from datetime import timedelta

import pytest

from app.domain.enums import SaleEventStatus
from app.domain.exceptions import InvalidSaleEventError
from app.sales.lifecycle import event_status, view_at
from tests.unit.sales.helpers import NOW, event_record


def test_before_during_after_boundaries() -> None:
    start = NOW
    end = NOW + timedelta(days=3)
    assert (
        event_status(start_date=start, end_date=end, at=start - timedelta(seconds=1))
        is SaleEventStatus.BEFORE_EVENT
    )
    assert event_status(start_date=start, end_date=end, at=start) is SaleEventStatus.DURING_EVENT
    assert (
        event_status(start_date=start, end_date=end, at=start + timedelta(days=1))
        is SaleEventStatus.DURING_EVENT
    )
    assert event_status(start_date=start, end_date=end, at=end) is SaleEventStatus.DURING_EVENT
    assert (
        event_status(start_date=start, end_date=end, at=end + timedelta(seconds=1))
        is SaleEventStatus.AFTER_EVENT
    )


def test_naive_datetime_is_rejected() -> None:
    start = NOW
    end = NOW + timedelta(days=1)
    with pytest.raises(InvalidSaleEventError):
        event_status(start_date=start, end_date=end, at=NOW.replace(tzinfo=None))


def test_view_at_attaches_status() -> None:
    record = event_record(start_date=NOW + timedelta(days=2), end_date=NOW + timedelta(days=5))
    view = view_at(record, at=NOW)
    assert view.status is SaleEventStatus.BEFORE_EVENT
    assert view.event.id == record.id
    assert view.as_of == NOW
