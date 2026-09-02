"""Monthly price intelligence derived from stored qualifying observations.

Groups verified snapshots by calendar month-of-year (and optionally by retailer). Raw
observations and 7/30/90/180-day windows are not replaced. Missing months are
`insufficient_history` — never zero-filled or invented.

Independent of FastAPI and of specific retailer adapter packages.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, localcontext
from statistics import median

from app.pricing.config import PricingConfig, get_pricing_config
from app.pricing.enums import InsufficientReasonCode, MetricStatus, ValueKind
from app.pricing.history_models import (
    CalculatedMetric,
    HistoricalObservationPoint,
    InsufficientHistory,
    MonthlyBucket,
    MonthlyPriceIntelligence,
)
from app.pricing.money import quantize_money, quantize_ratio

MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

MONTHLY_METHOD_DESCRIPTION = (
    "CALCULATED from qualifying verified observations grouped by calendar month-of-year "
    "across available years. Median is the primary typical-price statistic. This is a "
    "historical description, not a forecast or a guaranteed future price."
)


def _reason(code: InsufficientReasonCode, detail: str) -> InsufficientHistory:
    return InsufficientHistory(code=code, reason=detail)


def _unavailable(
    *,
    unit: str,
    calculated_at: datetime,
    observation_count: int,
    code: InsufficientReasonCode,
    detail: str,
) -> CalculatedMetric:
    return CalculatedMetric(
        value_kind=ValueKind.CALCULATED,
        status=MetricStatus.INSUFFICIENT_HISTORY,
        value=None,
        unit=unit,
        observation_count=observation_count,
        calculated_at=calculated_at,
        insufficient=_reason(code, detail),
    )


def _available(
    *,
    value: Decimal,
    unit: str,
    calculated_at: datetime,
    observation_count: int,
    extra: dict[str, Decimal | int | str | None] | None = None,
) -> CalculatedMetric:
    return CalculatedMetric(
        value_kind=ValueKind.CALCULATED,
        status=MetricStatus.AVAILABLE,
        value=value,
        unit=unit,
        observation_count=observation_count,
        calculated_at=calculated_at,
        insufficient=None,
        extra=extra or {},
    )


def _stdev(prices: Sequence[Decimal]) -> Decimal | None:
    if len(prices) < 2:
        return None
    n = Decimal(len(prices))
    mean = sum(prices, Decimal("0")) / n
    squared = sum(((price - mean) ** 2 for price in prices), Decimal("0"))
    variance = squared / (n - 1)
    with localcontext() as ctx:
        ctx.prec = 28
        return quantize_money(variance.sqrt())


def _bucket_from_prices(
    prices: Sequence[Decimal],
    *,
    month: int,
    calculated_at: datetime,
    min_count: int,
    unit: str,
    retailer_id: uuid.UUID | None,
    retailer_slug: str | None,
    retailer_name: str | None,
    years: tuple[int, ...],
) -> MonthlyBucket:
    count = len(prices)
    name = MONTH_NAMES[month - 1]
    if count < min_count:
        unavailable = _unavailable(
            unit=unit,
            calculated_at=calculated_at,
            observation_count=count,
            code=(
                InsufficientReasonCode.NO_QUALIFYING_OBSERVATIONS
                if count == 0
                else InsufficientReasonCode.BELOW_MINIMUM_OBSERVATION_COUNT
            ),
            detail=(
                f"{name} monthly statistics require at least {min_count} qualifying "
                f"observation(s); {count} were found."
            ),
        )
        return MonthlyBucket(
            month=month,
            month_name=name,
            retailer_id=retailer_id,
            retailer_slug=retailer_slug,
            retailer_name=retailer_name,
            years_used=years,
            observation_count=count,
            minimum=unavailable,
            average=unavailable,
            median=unavailable,
            maximum=unavailable,
            historical_low=unavailable,
            historical_high=unavailable,
            volatility=unavailable,
        )
    ordered = tuple(sorted(prices))
    total = sum(ordered, Decimal("0"))
    mean = quantize_money(total / Decimal(count))
    med = quantize_money(Decimal(str(median(ordered))))
    low = quantize_money(ordered[0])
    high = quantize_money(ordered[-1])
    stdev = _stdev(ordered)
    extra = {"years_used": len(years)}
    minimum = _available(value=low, unit=unit, calculated_at=calculated_at, observation_count=count)
    maximum = _available(
        value=high, unit=unit, calculated_at=calculated_at, observation_count=count
    )
    volatility = (
        _available(
            value=stdev,
            unit=unit,
            calculated_at=calculated_at,
            observation_count=count,
            extra={"mean": mean, "coefficient_of_variation": quantize_ratio(stdev / mean)}
            if mean > 0 and stdev is not None
            else extra,
        )
        if stdev is not None
        else _unavailable(
            unit=unit,
            calculated_at=calculated_at,
            observation_count=count,
            code=InsufficientReasonCode.BELOW_MINIMUM_OBSERVATION_COUNT,
            detail=f"{name} volatility requires at least 2 qualifying observations.",
        )
    )
    return MonthlyBucket(
        month=month,
        month_name=name,
        retailer_id=retailer_id,
        retailer_slug=retailer_slug,
        retailer_name=retailer_name,
        years_used=years,
        observation_count=count,
        minimum=minimum,
        average=_available(
            value=mean, unit=unit, calculated_at=calculated_at, observation_count=count
        ),
        median=_available(
            value=med, unit=unit, calculated_at=calculated_at, observation_count=count
        ),
        maximum=maximum,
        historical_low=minimum,
        historical_high=maximum,
        volatility=volatility,
    )


def _typical_price(bucket: MonthlyBucket) -> Decimal | None:
    if bucket.median.status is MetricStatus.AVAILABLE and bucket.median.value is not None:
        return bucket.median.value
    if bucket.average.status is MetricStatus.AVAILABLE and bucket.average.value is not None:
        return bucket.average.value
    return None


def compute_monthly_intelligence(
    points: Sequence[HistoricalObservationPoint],
    *,
    as_of: datetime,
    config: PricingConfig | None = None,
) -> MonthlyPriceIntelligence:
    """Derive month-of-year stats from qualifying verified observations only."""
    resolved = config if config is not None else get_pricing_config()
    qualifying = tuple(point for point in points if point.qualifies_for_calculations)
    unit = qualifying[-1].currency if qualifying else "INR"
    min_count = resolved.min_observations_for_monthly
    by_month: dict[int, list[Decimal]] = defaultdict(list)
    years_by_month: dict[int, set[int]] = defaultdict(set)
    by_retailer_month: dict[tuple[uuid.UUID, int], list[Decimal]] = defaultdict(list)
    retailer_meta: dict[uuid.UUID, tuple[str, str]] = {}
    years_by_retailer_month: dict[tuple[uuid.UUID, int], set[int]] = defaultdict(set)
    for point in qualifying:
        month = point.observed_at.month
        year = point.observed_at.year
        by_month[month].append(point.analysis_price)
        years_by_month[month].add(year)
        key = (point.retailer_id, month)
        by_retailer_month[key].append(point.analysis_price)
        years_by_retailer_month[key].add(year)
        retailer_meta[point.retailer_id] = (point.retailer_slug, point.retailer_name)

    months = tuple(
        _bucket_from_prices(
            by_month.get(month, ()),
            month=month,
            calculated_at=as_of,
            min_count=min_count,
            unit=unit,
            retailer_id=None,
            retailer_slug=None,
            retailer_name=None,
            years=tuple(sorted(years_by_month.get(month, ()))),
        )
        for month in range(1, 13)
    )
    retailer_months = tuple(
        _bucket_from_prices(
            prices,
            month=month,
            calculated_at=as_of,
            min_count=min_count,
            unit=unit,
            retailer_id=retailer_id,
            retailer_slug=retailer_meta[retailer_id][0],
            retailer_name=retailer_meta[retailer_id][1],
            years=tuple(sorted(years_by_retailer_month[(retailer_id, month)])),
        )
        for (retailer_id, month), prices in sorted(
            by_retailer_month.items(), key=lambda item: (item[0][1], str(item[0][0]))
        )
    )
    usable = [bucket for bucket in months if _typical_price(bucket) is not None]
    best: MonthlyBucket | None = None
    best_metric: CalculatedMetric
    if len(usable) < resolved.min_months_for_best_buying_month:
        best_metric = _unavailable(
            unit=unit,
            calculated_at=as_of,
            observation_count=len(qualifying),
            code=InsufficientReasonCode.BELOW_MINIMUM_OBSERVATION_COUNT,
            detail=(
                "Best historical buying month requires usable statistics in at least "
                f"{resolved.min_months_for_best_buying_month} distinct months; "
                f"{len(usable)} qualified."
            ),
        )
    else:
        best = min(
            usable,
            key=lambda bucket: (
                _typical_price(bucket),
                bucket.month,
            ),
        )
        typical = _typical_price(best)
        assert typical is not None
        best_metric = _available(
            value=typical,
            unit=unit,
            calculated_at=as_of,
            observation_count=best.observation_count,
            extra={"month": best.month, "month_name": best.month_name},
        )
    return MonthlyPriceIntelligence(
        months=months,
        retailer_months=retailer_months,
        best_buying_month=best,
        best_buying_month_price=best_metric,
        qualifying_observation_count=len(qualifying),
        calculated_at=as_of,
        method=MONTHLY_METHOD_DESCRIPTION,
    )
