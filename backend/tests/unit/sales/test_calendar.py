"""Previous-year → current-year sale mapping. Dates are never copied from last year."""

from datetime import UTC, datetime, timedelta

from app.domain.enums import (
    SaleEventSource,
    SaleEventType,
    SaleEvidenceStatus,
    SaleMappingMethod,
    SaleSeverity,
)
from app.sales.calendar import map_family, map_sale_calendar
from tests.unit.sales.helpers import NOW, RETAILER_A, event_record, sales_config

AS_OF = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def test_fixed_calendar_maps_stable_month_day_across_years() -> None:
    events = [
        event_record(
            name="FIXTURE: Mid-March Sale 2024",
            start_date=datetime(2024, 3, 15, tzinfo=UTC),
            end_date=datetime(2024, 3, 18, tzinfo=UTC),
        ),
        event_record(
            name="FIXTURE: Mid-March Sale 2025",
            start_date=datetime(2025, 3, 15, tzinfo=UTC),
            end_date=datetime(2025, 3, 18, tzinfo=UTC),
        ),
    ]
    window = map_family(events, (), as_of=AS_OF, config=sales_config())
    assert window.evidence_status is SaleEvidenceStatus.EXPECTED
    assert window.mapping_method is SaleMappingMethod.FIXED_CALENDAR
    assert window.expected_start_date is not None
    assert window.expected_start_date.date() == datetime(2026, 3, 15).date()
    assert window.historical_years_used == (2024, 2025)
    assert window.evidence_count >= 2


def test_festival_relative_uses_current_year_festival_not_last_year_date() -> None:
    # Diwali 2024-10-31 and 2025-10-20; sale starts 10 days before each year.
    events = [
        event_record(
            name="FIXTURE: Festival-adjacent Sale 2024",
            event_type=SaleEventType.SEASONAL,
            start_date=datetime(2024, 10, 21, tzinfo=UTC),
            end_date=datetime(2024, 10, 26, tzinfo=UTC),
        ),
        event_record(
            name="FIXTURE: Festival-adjacent Sale 2025",
            event_type=SaleEventType.SEASONAL,
            start_date=datetime(2025, 10, 10, tzinfo=UTC),
            end_date=datetime(2025, 10, 15, tzinfo=UTC),
        ),
    ]
    window = map_family(events, (), as_of=AS_OF, config=sales_config())
    assert window.mapping_method is SaleMappingMethod.FESTIVAL_RELATIVE
    assert window.occasion_id == "diwali"
    assert window.expected_start_date is not None
    # Diwali 2026-11-08 minus 10 days → 2026-10-29. Not a copy of 2025-10-10.
    assert window.expected_start_date.date() == datetime(2026, 10, 29).date()
    assert window.expected_start_date.date() != datetime(2025, 10, 10).date()
    assert window.evidence_status is SaleEvidenceStatus.EXPECTED


def test_recurring_weekday_pattern() -> None:
    events = [
        event_record(
            name="FIXTURE: July Weekend Sale 2024",
            start_date=datetime(2024, 7, 13, tzinfo=UTC),  # 2nd Saturday
            end_date=datetime(2024, 7, 15, tzinfo=UTC),
        ),
        event_record(
            name="FIXTURE: July Weekend Sale 2025",
            start_date=datetime(2025, 7, 12, tzinfo=UTC),  # 2nd Saturday
            end_date=datetime(2025, 7, 14, tzinfo=UTC),
        ),
    ]
    window = map_family(events, (), as_of=AS_OF, config=sales_config())
    assert window.mapping_method in {
        SaleMappingMethod.RECURRING,
        SaleMappingMethod.FIXED_CALENDAR,
    }
    assert window.expected_start_date is not None
    assert window.expected_start_date.year == 2026
    assert window.expected_start_date.month == 7


def test_retailer_specific_recurring_pattern() -> None:
    events = [
        event_record(
            name="FIXTURE: Retailer July Sale 2024",
            event_type=SaleEventType.RETAILER_SPECIFIC,
            retailer_id=RETAILER_A,
            start_date=datetime(2024, 7, 13, tzinfo=UTC),
            end_date=datetime(2024, 7, 15, tzinfo=UTC),
        ),
        event_record(
            name="FIXTURE: Retailer July Sale 2025",
            event_type=SaleEventType.RETAILER_SPECIFIC,
            retailer_id=RETAILER_A,
            start_date=datetime(2025, 7, 12, tzinfo=UTC),
            end_date=datetime(2025, 7, 14, tzinfo=UTC),
        ),
    ]
    window = map_family(events, (), as_of=AS_OF, config=sales_config())
    assert window.retailer_id == RETAILER_A
    assert window.expected_start_date is not None
    if window.mapping_method is SaleMappingMethod.RECURRING:
        raise AssertionError("retailer-scoped families should use RETAILER_SPECIFIC when recurring")
    assert window.mapping_method in {
        SaleMappingMethod.RETAILER_SPECIFIC,
        SaleMappingMethod.FIXED_CALENDAR,
    }


def test_single_year_is_unknown_and_does_not_copy_last_year() -> None:
    events = [
        event_record(
            name="FIXTURE: Only last year",
            start_date=datetime(2025, 11, 1, tzinfo=UTC),
            end_date=datetime(2025, 11, 5, tzinfo=UTC),
        )
    ]
    window = map_family(events, (), as_of=AS_OF, config=sales_config())
    assert window.evidence_status is SaleEvidenceStatus.UNKNOWN
    assert window.mapping_method is SaleMappingMethod.INSUFFICIENT
    assert window.expected_start_date is None
    assert window.expected_end_date is None


def test_confirmed_future_permitted_event_is_not_inferred() -> None:
    events = [
        event_record(
            name="FIXTURE: Confirmed future sale",
            source=SaleEventSource.MANUAL_CURATION,
            start_date=datetime(2026, 9, 1, tzinfo=UTC),
            end_date=datetime(2026, 9, 7, tzinfo=UTC),
        ),
        event_record(
            name="FIXTURE: Confirmed future sale 2024",
            source=SaleEventSource.MANUAL_CURATION,
            start_date=datetime(2024, 9, 1, tzinfo=UTC),
            end_date=datetime(2024, 9, 7, tzinfo=UTC),
        ),
        event_record(
            name="FIXTURE: Confirmed future sale 2025",
            source=SaleEventSource.MANUAL_CURATION,
            start_date=datetime(2025, 9, 1, tzinfo=UTC),
            end_date=datetime(2025, 9, 7, tzinfo=UTC),
        ),
    ]
    window = map_family(events, (), as_of=AS_OF, config=sales_config())
    assert window.evidence_status is SaleEvidenceStatus.CONFIRMED
    assert window.mapping_method is SaleMappingMethod.CONFIRMED_SCHEDULE
    assert window.expected_start_date == datetime(2026, 9, 1, tzinfo=UTC)


def test_inferred_source_history_is_labeled_inferred() -> None:
    events = [
        event_record(
            name="Detected retailer sale",
            source=SaleEventSource.OBSERVED_PRICE_INFERENCE,
            event_type=SaleEventType.RETAILER_SPECIFIC,
            retailer_id=RETAILER_A,
            start_date=datetime(2024, 4, 10, tzinfo=UTC),
            end_date=datetime(2024, 4, 12, tzinfo=UTC),
        ),
        event_record(
            name="Detected retailer sale",
            source=SaleEventSource.OBSERVED_PRICE_INFERENCE,
            event_type=SaleEventType.RETAILER_SPECIFIC,
            retailer_id=RETAILER_A,
            start_date=datetime(2025, 4, 10, tzinfo=UTC),
            end_date=datetime(2025, 4, 12, tzinfo=UTC),
        ),
    ]
    window = map_family(events, (), as_of=AS_OF, config=sales_config())
    assert window.evidence_status is SaleEvidenceStatus.INFERRED
    assert window.expected_start_date is not None


def test_map_sale_calendar_keeps_unknown_families() -> None:
    events = [
        event_record(
            name="FIXTURE: Thin family",
            start_date=NOW - timedelta(days=40),
            end_date=NOW - timedelta(days=38),
        )
    ]
    windows = map_sale_calendar(events, (), as_of=NOW, config=sales_config())
    assert len(windows) == 1
    assert windows[0].sale_type in {SaleSeverity.UNKNOWN, SaleSeverity.ORDINARY}
    assert windows[0].expected_start_date is None or (
        windows[0].evidence_status is not SaleEvidenceStatus.CONFIRMED
    )
