"""Sale-event lifecycle: BEFORE EVENT / DURING EVENT / AFTER EVENT.

Status is derived from the event window and a point in time. It is never stored, guessed, or
predicted.
"""

from datetime import datetime

from app.domain.enums import SaleEventStatus
from app.domain.exceptions import InvalidSaleEventError
from app.domain.validation import validate_sale_event_dates
from app.sales.models import SaleEventRecord, SaleEventView


def event_status(
    *,
    start_date: datetime,
    end_date: datetime,
    at: datetime,
) -> SaleEventStatus:
    """Classify an event window at `at`. Bounds are inclusive for `during_event`."""
    start, end = validate_sale_event_dates(start_date, end_date)
    if at.tzinfo is None or at.tzinfo.utcoffset(at) is None:
        raise InvalidSaleEventError("Lifecycle comparison time must be timezone-aware.")
    if at < start:
        return SaleEventStatus.BEFORE_EVENT
    if at > end:
        return SaleEventStatus.AFTER_EVENT
    return SaleEventStatus.DURING_EVENT


def view_at(record: SaleEventRecord, *, at: datetime) -> SaleEventView:
    """Attach lifecycle status to a sale-event record at `at`."""
    return SaleEventView(
        event=record,
        status=event_status(start_date=record.start_date, end_date=record.end_date, at=at),
        as_of=at,
    )
