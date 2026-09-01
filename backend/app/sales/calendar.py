"""Previous-year → current-year sale timing mapper.

Never copies last year's date. Uses multi-year patterns:

- fixed calendar (stable month-day)
- festival-relative (stable offset from a public festival/civil date)
- recurring (month / week-of-month / weekday)
- retailer-specific (same methods, scoped to one retailer)

Insufficient evidence yields UNKNOWN rather than an invented date.
Projected windows are EXPECTED or INFERRED — never CONFIRMED unless a persisted
non-inferred event already has future dates.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from statistics import median, pstdev

from app.domain.enums import (
    ConfidenceLevel,
    SaleEventSource,
    SaleEvidenceStatus,
    SaleMappingMethod,
    SaleSeverity,
)
from app.sales.classification import classify_family
from app.sales.config import SalesConfig, get_sales_config
from app.sales.families import (
    family_key,
    family_retailer_id,
    group_by_family,
    normalize_family_name,
)
from app.sales.festivals import all_occasion_ids, apply_offset, occasion_date, offset_days
from app.sales.models import SaleEventRecord, SalePricePoint
from app.sales.timing_models import ExpectedSaleWindow

_PERMITTED_FUTURE_SOURCES = frozenset(
    {
        SaleEventSource.MANUAL_CURATION,
        SaleEventSource.OFFICIAL_API,
        SaleEventSource.AFFILIATE_FEED,
        SaleEventSource.PRODUCT_FEED,
        SaleEventSource.OTHER_PERMITTED,
    }
)


def _median_int(values: Sequence[int]) -> int:
    return int(round(float(median(values))))


def _week_of_month(moment: datetime) -> int:
    return (moment.day - 1) // 7 + 1


def _duration_days(event: SaleEventRecord) -> int:
    seconds = (event.end_date - event.start_date).total_seconds()
    return max(0, int(round(seconds / 86400.0)))


def _confidence(
    *,
    years: int,
    deviation_days: float,
    evidence_status: SaleEvidenceStatus,
) -> ConfidenceLevel:
    if evidence_status is SaleEvidenceStatus.UNKNOWN:
        return ConfidenceLevel.LOW
    if evidence_status is SaleEvidenceStatus.CONFIRMED and years >= 1:
        return ConfidenceLevel.HIGH if years >= 2 else ConfidenceLevel.MEDIUM
    if years >= 3 and deviation_days <= 2:
        return ConfidenceLevel.HIGH
    if years >= 2 and deviation_days <= 4:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _shift_to_future(
    start: datetime,
    end: datetime,
    *,
    as_of: datetime,
) -> tuple[datetime, datetime]:
    if end >= as_of:
        return start, end
    delta_years = as_of.year - start.year + 1
    try:
        shifted_start = start.replace(year=start.year + delta_years)
        shifted_end = end.replace(year=end.year + delta_years)
    except ValueError:
        shifted_start = start.replace(year=start.year + delta_years, day=28)
        shifted_end = end.replace(year=end.year + delta_years, day=28)
    if shifted_end < as_of:
        try:
            shifted_start = shifted_start.replace(year=shifted_start.year + 1)
            shifted_end = shifted_end.replace(year=shifted_end.year + 1)
        except ValueError:
            shifted_start = shifted_start.replace(year=shifted_start.year + 1, day=28)
            shifted_end = shifted_end.replace(year=shifted_end.year + 1, day=28)
    return shifted_start, shifted_end


def _nth_weekday(year: int, month: int, weekday: int, week: int) -> datetime | None:
    first = datetime(year, month, 1, tzinfo=UTC)
    offset = (weekday - first.weekday()) % 7
    day = 1 + offset + (week - 1) * 7
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None


def _fixed_calendar_candidate(
    events: Sequence[SaleEventRecord],
    *,
    max_deviation: int,
) -> tuple[datetime, datetime, float] | None:
    starts = [event.start_date for event in events]
    months = {item.month for item in starts}
    if len(months) != 1:
        return None
    days = [item.day for item in starts]
    med_day = _median_int(days)
    deviation = max(abs(value - med_day) for value in days)
    if deviation > max_deviation:
        return None
    durations = [_duration_days(event) for event in events]
    duration = _median_int(durations) if durations else 0
    month = next(iter(months))
    ref_year = starts[0].year
    try:
        start_date = datetime(ref_year, month, med_day, tzinfo=UTC)
    except ValueError:
        start_date = datetime(ref_year, month, min(days), tzinfo=UTC)
    end = start_date + timedelta(days=duration)
    return start_date, end, float(deviation)


def _festival_candidate(
    events: Sequence[SaleEventRecord],
    *,
    max_stdev: float,
    max_abs: int,
) -> tuple[str, int, float, int] | None:
    best: tuple[str, int, float, int] | None = None
    for occasion_id in all_occasion_ids():
        offsets: list[int] = []
        for event in events:
            occasion = occasion_date(occasion_id, event.start_date.year)
            if occasion is None:
                offsets = []
                break
            offsets.append(offset_days(event.start_date, occasion))
        if len(offsets) < 2:
            continue
        if max(abs(value) for value in offsets) > max_abs:
            continue
        spread = float(pstdev(offsets)) if len(offsets) > 1 else 0.0
        if spread > max_stdev:
            continue
        med = _median_int(offsets)
        duration = _median_int([_duration_days(event) for event in events])
        candidate = (occasion_id, med, spread, duration)
        if best is None or spread < best[2] or (spread == best[2] and abs(med) < abs(best[1])):
            best = candidate
    return best


def _recurring_candidate(
    events: Sequence[SaleEventRecord],
) -> tuple[int, int, int, int, float] | None:
    months = [event.start_date.month for event in events]
    if len(set(months)) != 1:
        return None
    weeks = [_week_of_month(event.start_date) for event in events]
    weekdays = [event.start_date.weekday() for event in events]
    week_spread = float(pstdev(weeks)) if len(weeks) > 1 else 0.0
    weekday_spread = float(pstdev(weekdays)) if len(weekdays) > 1 else 0.0
    if week_spread > 1.0 or weekday_spread > 1.5:
        return None
    duration = _median_int([_duration_days(event) for event in events])
    deviation = max(week_spread, weekday_spread) * 7.0
    return months[0], _median_int(weeks), _median_int(weekdays), duration, deviation


def _unknown_window(
    *,
    family: str,
    display_name: str,
    events: Sequence[SaleEventRecord],
    severity: SaleSeverity,
    as_of: datetime,
    retailer_id,
) -> ExpectedSaleWindow:
    years = tuple(sorted({event.start_date.year for event in events}))
    return ExpectedSaleWindow(
        sale_family=family,
        display_name=display_name,
        sale_type=severity,
        evidence_status=SaleEvidenceStatus.UNKNOWN,
        mapping_method=SaleMappingMethod.INSUFFICIENT,
        expected_start_date=None,
        expected_end_date=None,
        confidence=ConfidenceLevel.LOW,
        evidence_count=len(events),
        historical_years_used=years,
        retailer_id=retailer_id,
        occasion_id=None,
        duration_days=None,
        as_of=as_of,
        reason=(
            "Insufficient multi-year evidence to map this sale family onto the current "
            "calendar. A date is not invented by copying last year."
        ),
    )


def map_family(
    events: Sequence[SaleEventRecord],
    points: Sequence[SalePricePoint] = (),
    *,
    as_of: datetime,
    config: SalesConfig | None = None,
) -> ExpectedSaleWindow:
    """Map one family to a current-year (or next-year) expected window."""
    resolved = config if config is not None else get_sales_config()
    if not events:
        return _unknown_window(
            family="unknown",
            display_name="Unknown sale family",
            events=(),
            severity=SaleSeverity.UNKNOWN,
            as_of=as_of,
            retailer_id=None,
        )
    key = family_key(events[0])
    display = normalize_family_name(events[0].name).replace("-", " ").title()
    retailer_id = family_retailer_id(events)
    confirmed = [
        event
        for event in events
        if event.start_date >= as_of and event.source in _PERMITTED_FUTURE_SOURCES
    ]
    historical = tuple(event for event in events if event.end_date < as_of)
    years = tuple(sorted({event.start_date.year for event in (historical or events)}))
    severity = classify_family(historical or events, points, config=resolved)
    if confirmed:
        chosen = min(confirmed, key=lambda item: (item.start_date, item.id))
        return ExpectedSaleWindow(
            sale_family=key,
            display_name=chosen.name,
            sale_type=severity,
            evidence_status=SaleEvidenceStatus.CONFIRMED,
            mapping_method=SaleMappingMethod.CONFIRMED_SCHEDULE,
            expected_start_date=chosen.start_date,
            expected_end_date=chosen.end_date,
            confidence=_confidence(
                years=len(years),
                deviation_days=0.0,
                evidence_status=SaleEvidenceStatus.CONFIRMED,
            ),
            evidence_count=len(events),
            historical_years_used=years,
            retailer_id=retailer_id,
            occasion_id=None,
            duration_days=_duration_days(chosen),
            as_of=as_of,
            reason=(
                "Window taken from a persisted sale event with a permitted or curated "
                "source. This is not a model forecast."
            ),
        )

    inferred_only = bool(historical) and all(
        event.source is SaleEventSource.OBSERVED_PRICE_INFERENCE for event in historical
    )
    years = tuple(sorted({event.start_date.year for event in historical}))

    if len(years) < resolved.min_years_for_calendar_mapping:
        return _unknown_window(
            family=key,
            display_name=display,
            events=historical or events,
            severity=severity,
            as_of=as_of,
            retailer_id=retailer_id,
        )

    status = SaleEvidenceStatus.INFERRED if inferred_only else SaleEvidenceStatus.EXPECTED
    festival = _festival_candidate(
        historical,
        max_stdev=resolved.festival_offset_max_stdev_days,
        max_abs=resolved.festival_offset_max_abs_days,
    )
    fixed = _fixed_calendar_candidate(
        historical, max_deviation=resolved.fixed_calendar_max_day_deviation
    )
    recurring = _recurring_candidate(historical)
    method = SaleMappingMethod.INSUFFICIENT
    start: datetime | None = None
    end: datetime | None = None
    deviation = math.inf
    occasion_id: str | None = None
    duration: int | None = None
    reason = "Insufficient stable timing pattern across historical years."

    target_year = as_of.year
    if festival is not None:
        occasion_id, offset, spread, duration = festival
        occasion = occasion_date(occasion_id, target_year)
        if occasion is None:
            occasion = occasion_date(occasion_id, target_year + 1)
        if occasion is not None:
            start, end = apply_offset(occasion, offset, duration_days=duration)
            start, end = _shift_to_future(start, end, as_of=as_of)
            method = SaleMappingMethod.FESTIVAL_RELATIVE
            deviation = spread
            reason = (
                f"Historical starts clustered {offset} day(s) relative to {occasion_id} "
                f"across {len(years)} years (offset stdev {spread:.2f} days). "
                "This is an evidence-based estimate, not a retailer announcement."
            )
    if fixed is not None and (festival is None or fixed[2] <= deviation):
        proto_start, proto_end, fixed_dev = fixed
        try:
            start = proto_start.replace(year=target_year)
            end = proto_end.replace(year=target_year)
        except ValueError:
            start = proto_start.replace(year=target_year, day=28)
            end = proto_end.replace(year=target_year, day=28)
        assert start is not None and end is not None
        start, end = _shift_to_future(start, end, as_of=as_of)
        method = SaleMappingMethod.FIXED_CALENDAR
        deviation = fixed_dev
        occasion_id = None
        duration = _median_int([_duration_days(event) for event in historical])
        reason = (
            f"Historical starts fell within {fixed_dev:.1f} day(s) of a stable calendar "
            f"date across {len(years)} years. This is not a copy of last year's date."
        )
    elif method is SaleMappingMethod.INSUFFICIENT and recurring is not None:
        month, week, weekday, duration, rec_dev = recurring
        projected = _nth_weekday(target_year, month, weekday, week)
        if projected is None:
            projected = _nth_weekday(target_year + 1, month, weekday, week)
        if projected is not None:
            start = projected
            end = projected + timedelta(days=duration)
            start, end = _shift_to_future(start, end, as_of=as_of)
            method = (
                SaleMappingMethod.RETAILER_SPECIFIC
                if retailer_id is not None
                else SaleMappingMethod.RECURRING
            )
            deviation = rec_dev
            reason = (
                f"Historical starts recurred in month {month}, week {week}, weekday "
                f"{weekday} across {len(years)} years."
            )

    if start is None or end is None or method is SaleMappingMethod.INSUFFICIENT:
        return _unknown_window(
            family=key,
            display_name=display,
            events=events,
            severity=severity,
            as_of=as_of,
            retailer_id=retailer_id,
        )
    return ExpectedSaleWindow(
        sale_family=key,
        display_name=display,
        sale_type=severity,
        evidence_status=status,
        mapping_method=method,
        expected_start_date=start,
        expected_end_date=end,
        confidence=_confidence(years=len(years), deviation_days=deviation, evidence_status=status),
        evidence_count=len(events),
        historical_years_used=years,
        retailer_id=retailer_id,
        occasion_id=occasion_id,
        duration_days=duration,
        as_of=as_of,
        reason=reason,
    )


def map_sale_calendar(
    events: Sequence[SaleEventRecord],
    points: Sequence[SalePricePoint] = (),
    *,
    as_of: datetime,
    config: SalesConfig | None = None,
) -> tuple[ExpectedSaleWindow, ...]:
    """Map every sale family. Families with no usable pattern are UNKNOWN, not omitted."""
    resolved = config if config is not None else get_sales_config()
    windows = [
        map_family(family_events, points, as_of=as_of, config=resolved)
        for family_events in group_by_family(events).values()
    ]
    windows.sort(
        key=lambda item: (
            item.expected_start_date or datetime.max.replace(tzinfo=UTC),
            item.sale_family,
        )
    )
    return tuple(windows)
