"""Evidence-based MAJOR / ORDINARY / UNKNOWN classification.

Does not hardcode real-world campaign names (Diwali, Republic Day, Black Friday, …).
Uses duration, year recurrence, in-window discount vs a pre-sale baseline, and the
generic `SaleEventType` as a weak prior only.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal
from statistics import median

from app.domain.enums import SaleEventType, SaleSeverity
from app.pricing.history import qualifying_observations
from app.sales.config import SalesConfig, get_sales_config
from app.sales.models import SaleEventRecord, SalePricePoint

_MAJOR_TYPES = frozenset({SaleEventType.SEASONAL, SaleEventType.NATIONAL_SHOPPING})


def _duration_days(event: SaleEventRecord) -> float:
    return max(0.0, (event.end_date - event.start_date).total_seconds() / 86400.0)


def _years(events: Sequence[SaleEventRecord]) -> set[int]:
    return {event.start_date.year for event in events}


def _drop_percent(
    event: SaleEventRecord,
    points: Sequence[SalePricePoint],
    *,
    lookback_days: int,
) -> Decimal | None:
    qualifying = qualifying_observations(tuple(item.observation for item in points))
    scoped_retailer = event.retailer_id
    in_window = [
        point.analysis_price
        for point in qualifying
        if event.start_date <= point.observed_at <= event.end_date
        and (scoped_retailer is None or point.retailer_id == scoped_retailer)
    ]
    pre_start = event.start_date - timedelta(days=lookback_days)
    pre = [
        point.analysis_price
        for point in qualifying
        if pre_start <= point.observed_at < event.start_date
        and (scoped_retailer is None or point.retailer_id == scoped_retailer)
    ]
    if not in_window or not pre:
        return None
    baseline = Decimal(str(median(pre)))
    sale = Decimal(str(median(in_window)))
    if baseline <= 0:
        return None
    return (baseline - sale) / baseline * Decimal("100")


def classify_family(
    events: Sequence[SaleEventRecord],
    points: Sequence[SalePricePoint] = (),
    *,
    config: SalesConfig | None = None,
) -> SaleSeverity:
    """Classify one sale family. UNKNOWN when evidence is too thin to choose."""
    if not events:
        return SaleSeverity.UNKNOWN
    resolved = config if config is not None else get_sales_config()
    years = _years(events)
    durations = [_duration_days(event) for event in events]
    median_duration = float(median(durations)) if durations else 0.0
    drops = [
        drop
        for event in events
        if (drop := _drop_percent(event, points, lookback_days=resolved.pre_sale_lookback_days))
        is not None
    ]
    median_drop = Decimal(str(median(drops))) if drops else None
    types = {event.event_type for event in events}
    recurring = len(years) >= 2
    major_type = bool(types & _MAJOR_TYPES)
    long_enough = median_duration >= resolved.major_min_duration_days
    big_drop = median_drop is not None and median_drop >= Decimal(str(resolved.major_drop_percent))
    moderate_drop = median_drop is not None and median_drop >= Decimal("8")

    if recurring and (big_drop or (major_type and (long_enough or moderate_drop))):
        return SaleSeverity.MAJOR
    if big_drop and long_enough and (recurring or major_type):
        return SaleSeverity.MAJOR
    if types == {SaleEventType.RETAILER_SPECIFIC} and median_duration <= 2 and not big_drop:
        return SaleSeverity.ORDINARY
    if median_drop is None and not recurring and not major_type and median_duration < 2:
        return SaleSeverity.UNKNOWN
    if recurring or moderate_drop or major_type or median_duration >= 1:
        return SaleSeverity.ORDINARY
    return SaleSeverity.UNKNOWN
