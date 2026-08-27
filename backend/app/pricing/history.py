"""Historical price intelligence over stored, verified price observations.

Computes window averages, extrema, percentile, volatility, percentage change, price-drop
detection, and a deterministic trend. Inputs are stored observations only. Missing history
is reported as `insufficient_history` — never replaced with zeros, guesses, or predictions.

Independent of FastAPI and of specific retailer adapter packages.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal, localcontext

from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.config import PricingConfig, get_pricing_config
from app.pricing.enums import InsufficientReasonCode, MetricStatus, TrendDirection, ValueKind
from app.pricing.freshness import aggregate_freshness, offer_freshness, utc_now
from app.pricing.history_models import (
    AVERAGE_WINDOW_DAYS,
    PRICE_DROP_BASELINE_DESCRIPTION,
    TREND_METHOD_DESCRIPTION,
    CalculatedMetric,
    ExtremaMetric,
    HistoricalObservationPoint,
    HistoryProvenance,
    InsufficientHistory,
    PriceDropResult,
    ProductHistory,
    TrendResult,
    VariantHistory,
)
from app.pricing.money import quantize_money, quantize_ratio

logger = get_logger(__name__)

HISTORY_VARIANTS = "pricing.history.variants"
HISTORY_OBSERVATIONS = "pricing.history.observations"

_SECONDS_PER_DAY = Decimal("86400")


def _sort_key(point: HistoricalObservationPoint) -> tuple[datetime, datetime, uuid.UUID]:
    return (point.observed_at, point.created_at, point.snapshot_id)


def qualifying_observations(
    points: Sequence[HistoricalObservationPoint],
) -> tuple[HistoricalObservationPoint, ...]:
    """Verified observations only, oldest first. LOW-confidence rows are excluded."""
    qualifying = [point for point in points if point.qualifies_for_calculations]
    qualifying.sort(key=_sort_key)
    return tuple(qualifying)


def _reason(code: InsufficientReasonCode, detail: str) -> InsufficientHistory:
    return InsufficientHistory(code=code, reason=detail)


def _unavailable_metric(
    *,
    unit: str,
    calculated_at: datetime,
    observation_count: int,
    code: InsufficientReasonCode,
    detail: str,
    window_days: int | None = None,
    extra: dict[str, Decimal | int | str | None] | None = None,
) -> CalculatedMetric:
    return CalculatedMetric(
        value_kind=ValueKind.CALCULATED,
        status=MetricStatus.INSUFFICIENT_HISTORY,
        value=None,
        unit=unit,
        window_days=window_days,
        observation_count=observation_count,
        calculated_at=calculated_at,
        insufficient=_reason(code, detail),
        extra=extra or {},
    )


def _available_metric(
    *,
    value: Decimal,
    unit: str,
    calculated_at: datetime,
    observation_count: int,
    window_days: int | None = None,
    extra: dict[str, Decimal | int | str | None] | None = None,
) -> CalculatedMetric:
    return CalculatedMetric(
        value_kind=ValueKind.CALCULATED,
        status=MetricStatus.AVAILABLE,
        value=value,
        unit=unit,
        window_days=window_days,
        observation_count=observation_count,
        calculated_at=calculated_at,
        insufficient=None,
        extra=extra or {},
    )


def _window_points(
    points: Sequence[HistoricalObservationPoint],
    *,
    as_of: datetime,
    days: int,
) -> tuple[HistoricalObservationPoint, ...]:
    start = as_of - timedelta(days=days)
    return tuple(point for point in points if start <= point.observed_at <= as_of)


def window_average(
    points: Sequence[HistoricalObservationPoint],
    *,
    window_days: int,
    as_of: datetime,
    min_count: int,
    unit: str,
) -> CalculatedMetric:
    """Mean analysis price of qualifying observations inside `[as_of - N days, as_of]`."""
    in_window = _window_points(points, as_of=as_of, days=window_days)
    if not in_window:
        return _unavailable_metric(
            unit=unit,
            calculated_at=as_of,
            observation_count=0,
            code=InsufficientReasonCode.NO_OBSERVATIONS_IN_WINDOW,
            detail=(
                f"No qualifying verified observations exist in the {window_days}-day window "
                f"ending at calculation time."
            ),
            window_days=window_days,
        )
    if len(in_window) < min_count:
        return _unavailable_metric(
            unit=unit,
            calculated_at=as_of,
            observation_count=len(in_window),
            code=InsufficientReasonCode.BELOW_MINIMUM_OBSERVATION_COUNT,
            detail=(
                f"The {window_days}-day average requires at least {min_count} qualifying "
                f"observation(s); {len(in_window)} were found."
            ),
            window_days=window_days,
        )
    total = sum((point.analysis_price for point in in_window), Decimal("0.00"))
    mean = quantize_money(total / Decimal(len(in_window)))
    return _available_metric(
        value=mean,
        unit=unit,
        calculated_at=as_of,
        observation_count=len(in_window),
        window_days=window_days,
    )


def _extrema(
    points: Sequence[HistoricalObservationPoint],
    *,
    as_of: datetime,
    min_count: int,
    unit: str,
    pick_high: bool,
) -> ExtremaMetric:
    label = "maximum" if pick_high else "minimum"
    if not points:
        base = _unavailable_metric(
            unit=unit,
            calculated_at=as_of,
            observation_count=0,
            code=InsufficientReasonCode.NO_QUALIFYING_OBSERVATIONS,
            detail=(
                f"Historical {label} is unavailable because no qualifying "
                "verified observations exist."
            ),
        )
        return ExtremaMetric(**base.model_dump())
    if len(points) < min_count:
        base = _unavailable_metric(
            unit=unit,
            calculated_at=as_of,
            observation_count=len(points),
            code=InsufficientReasonCode.BELOW_MINIMUM_OBSERVATION_COUNT,
            detail=(
                f"Historical {label} requires at least {min_count} qualifying observation(s); "
                f"{len(points)} were found."
            ),
        )
        return ExtremaMetric(**base.model_dump())

    target_price = (
        max(point.analysis_price for point in points)
        if pick_high
        else min(point.analysis_price for point in points)
    )
    candidates = [point for point in points if point.analysis_price == target_price]
    winner = min(candidates, key=_sort_key)

    base = _available_metric(
        value=winner.analysis_price,
        unit=unit,
        calculated_at=as_of,
        observation_count=len(points),
    )
    return ExtremaMetric(
        **base.model_dump(),
        snapshot_id=winner.snapshot_id,
        observed_at=winner.observed_at,
        retailer_id=winner.retailer_id,
        seller_id=winner.seller_id,
        source_url=winner.source_url,
    )


def historical_low(
    points: Sequence[HistoricalObservationPoint],
    *,
    as_of: datetime,
    min_count: int,
    unit: str,
) -> ExtremaMetric:
    return _extrema(points, as_of=as_of, min_count=min_count, unit=unit, pick_high=False)


def historical_high(
    points: Sequence[HistoricalObservationPoint],
    *,
    as_of: datetime,
    min_count: int,
    unit: str,
) -> ExtremaMetric:
    return _extrema(points, as_of=as_of, min_count=min_count, unit=unit, pick_high=True)


def current_price_percentile(
    points: Sequence[HistoricalObservationPoint],
    *,
    current: HistoricalObservationPoint | None,
    as_of: datetime,
    min_count: int,
) -> CalculatedMetric:
    """Inclusive percentile of the current analysis price among qualifying observations.

    `percentile = 100 * count(price <= current) / n`. Requires a current price and at least
    `min_count` qualifying observations so there is comparison history.
    """
    if current is None:
        return _unavailable_metric(
            unit="percentile",
            calculated_at=as_of,
            observation_count=len(points),
            code=InsufficientReasonCode.NO_CURRENT_PRICE,
            detail=(
                "Current price percentile is unavailable because there is no qualifying "
                "current observation."
            ),
        )
    if len(points) < min_count:
        return _unavailable_metric(
            unit="percentile",
            calculated_at=as_of,
            observation_count=len(points),
            code=InsufficientReasonCode.BELOW_MINIMUM_OBSERVATION_COUNT,
            detail=(
                "Current price percentile is unavailable because comparison history is "
                f"insufficient ({len(points)} qualifying observation(s); {min_count} required)."
            ),
        )
    current_price = current.analysis_price
    at_or_below = sum(1 for point in points if point.analysis_price <= current_price)
    percentile = quantize_ratio(Decimal(at_or_below) / Decimal(len(points)) * Decimal("100"))
    return _available_metric(
        value=percentile,
        unit="percentile",
        calculated_at=as_of,
        observation_count=len(points),
        extra={"current_price": current_price},
    )


def price_volatility(
    points: Sequence[HistoricalObservationPoint],
    *,
    as_of: datetime,
    min_count: int,
    unit: str,
) -> CalculatedMetric:
    """Sample standard deviation of analysis prices across qualifying observations."""
    if len(points) < min_count:
        code = (
            InsufficientReasonCode.NO_QUALIFYING_OBSERVATIONS
            if not points
            else InsufficientReasonCode.BELOW_MINIMUM_OBSERVATION_COUNT
        )
        detail = (
            "Price volatility is unavailable because no qualifying verified observations exist."
            if not points
            else (
                f"Price volatility requires at least {min_count} qualifying observations; "
                f"{len(points)} were found."
            )
        )
        return _unavailable_metric(
            unit=unit,
            calculated_at=as_of,
            observation_count=len(points),
            code=code,
            detail=detail,
        )
    n = Decimal(len(points))
    mean = sum((point.analysis_price for point in points), Decimal("0.00")) / n
    squared = sum(((point.analysis_price - mean) ** 2 for point in points), Decimal("0"))
    variance = squared / (n - 1)
    with localcontext() as ctx:
        ctx.prec = 28
        stdev = variance.sqrt()
    stdev = quantize_money(stdev)
    extra: dict[str, Decimal | int | str | None] = {"mean": quantize_money(mean)}
    if mean > 0:
        extra["coefficient_of_variation"] = quantize_ratio(stdev / mean)
    return _available_metric(
        value=stdev,
        unit=unit,
        calculated_at=as_of,
        observation_count=len(points),
        extra=extra,
    )


def _baseline_for(
    current: HistoricalObservationPoint,
    points: Sequence[HistoricalObservationPoint],
) -> HistoricalObservationPoint | None:
    earlier = [
        point
        for point in points
        if point.listing_key == current.listing_key and _sort_key(point) < _sort_key(current)
    ]
    if not earlier:
        return None
    return earlier[-1]


def percentage_change(
    points: Sequence[HistoricalObservationPoint],
    *,
    current: HistoricalObservationPoint | None,
    as_of: datetime,
) -> tuple[CalculatedMetric, HistoricalObservationPoint | None]:
    """Percent change from the documented listing+seller baseline to the current price."""
    if current is None:
        metric = _unavailable_metric(
            unit="percent",
            calculated_at=as_of,
            observation_count=len(points),
            code=InsufficientReasonCode.NO_CURRENT_PRICE,
            detail=(
                "Percentage change is unavailable because there is no qualifying current "
                "observation."
            ),
        )
        return metric, None
    baseline = _baseline_for(current, points)
    if baseline is None:
        metric = _unavailable_metric(
            unit="percent",
            calculated_at=as_of,
            observation_count=len(points),
            code=InsufficientReasonCode.NO_COMPARISON_BASELINE,
            detail=(
                "Percentage change is unavailable because there is no previous qualifying "
                "verified observation for the same retailer listing and seller."
            ),
        )
        return metric, None
    if baseline.analysis_price == 0:
        metric = _unavailable_metric(
            unit="percent",
            calculated_at=as_of,
            observation_count=len(points),
            code=InsufficientReasonCode.ZERO_BASELINE_PRICE,
            detail="Percentage change is unavailable because the baseline observed price is zero.",
        )
        return metric, baseline
    change = (current.analysis_price - baseline.analysis_price) / baseline.analysis_price
    percent = quantize_ratio(change * Decimal("100"))
    metric = _available_metric(
        value=percent,
        unit="percent",
        calculated_at=as_of,
        observation_count=len(points),
        extra={
            "current_price": current.analysis_price,
            "baseline_price": baseline.analysis_price,
            "baseline_snapshot_id": str(baseline.snapshot_id),
        },
    )
    return metric, baseline


def detect_price_drop(
    *,
    current: HistoricalObservationPoint | None,
    baseline: HistoricalObservationPoint | None,
    change_metric: CalculatedMetric,
    as_of: datetime,
    observation_count: int,
) -> PriceDropResult:
    """True drop only when current verified price is strictly below the documented baseline."""
    if (
        change_metric.status is MetricStatus.INSUFFICIENT_HISTORY
        or current is None
        or baseline is None
    ):
        return PriceDropResult(
            status=MetricStatus.INSUFFICIENT_HISTORY,
            drop_occurred=None,
            observation_count=observation_count,
            calculated_at=as_of,
            insufficient=change_metric.insufficient,
            current_snapshot_id=None if current is None else current.snapshot_id,
            current_observed_at=None if current is None else current.observed_at,
            current_price=None if current is None else current.analysis_price,
            baseline_snapshot_id=None if baseline is None else baseline.snapshot_id,
            baseline_observed_at=None if baseline is None else baseline.observed_at,
            baseline_price=None if baseline is None else baseline.analysis_price,
            baseline_retailer_id=None if baseline is None else baseline.retailer_id,
            baseline_seller_id=None if baseline is None else baseline.seller_id,
            baseline_description=PRICE_DROP_BASELINE_DESCRIPTION,
        )
    drop_occurred = current.analysis_price < baseline.analysis_price
    return PriceDropResult(
        status=MetricStatus.AVAILABLE,
        drop_occurred=drop_occurred,
        percentage_change=change_metric.value,
        current_price=current.analysis_price,
        baseline_price=baseline.analysis_price,
        current_observed_at=current.observed_at,
        baseline_observed_at=baseline.observed_at,
        current_snapshot_id=current.snapshot_id,
        baseline_snapshot_id=baseline.snapshot_id,
        baseline_retailer_id=baseline.retailer_id,
        baseline_seller_id=baseline.seller_id,
        baseline_description=PRICE_DROP_BASELINE_DESCRIPTION,
        observation_count=observation_count,
        calculated_at=as_of,
        insufficient=None,
    )


def _days_since(origin: datetime, instant: datetime) -> Decimal:
    return Decimal(str((instant - origin).total_seconds())) / _SECONDS_PER_DAY


def historical_trend(
    points: Sequence[HistoricalObservationPoint],
    *,
    as_of: datetime,
    min_count: int,
    stable_percent: Decimal,
) -> TrendResult:
    """OLS slope of analysis price vs time. Not a prediction of future prices."""
    if len(points) < min_count:
        code = (
            InsufficientReasonCode.NO_QUALIFYING_OBSERVATIONS
            if not points
            else InsufficientReasonCode.BELOW_MINIMUM_OBSERVATION_COUNT
        )
        detail = (
            "Trend is unavailable because no qualifying verified observations exist."
            if not points
            else (
                f"Trend requires at least {min_count} qualifying observations; "
                f"{len(points)} were found."
            )
        )
        return TrendResult(
            status=MetricStatus.INSUFFICIENT_HISTORY,
            direction=TrendDirection.INSUFFICIENT_HISTORY,
            observation_count=len(points),
            calculated_at=as_of,
            insufficient=_reason(code, detail),
        )
    first = points[0]
    last = points[-1]
    xs = [_days_since(first.observed_at, point.observed_at) for point in points]
    ys = [point.analysis_price for point in points]
    n = Decimal(len(points))
    sum_x = sum(xs, Decimal("0"))
    sum_y = sum(ys, Decimal("0"))
    sum_xy = sum((x * y for x, y in zip(xs, ys, strict=True)), Decimal("0"))
    sum_x2 = sum((x * x for x in xs), Decimal("0"))
    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return TrendResult(
            status=MetricStatus.INSUFFICIENT_HISTORY,
            direction=TrendDirection.INSUFFICIENT_HISTORY,
            observation_count=len(points),
            first_observed_at=first.observed_at,
            last_observed_at=last.observed_at,
            calculated_at=as_of,
            insufficient=_reason(
                InsufficientReasonCode.ZERO_TIME_SPAN,
                "Trend is unavailable because qualifying observations share the same timestamp.",
            ),
        )
    slope = (n * sum_xy - sum_x * sum_y) / denom
    span_days = xs[-1]
    if first.analysis_price == 0:
        return TrendResult(
            status=MetricStatus.INSUFFICIENT_HISTORY,
            direction=TrendDirection.INSUFFICIENT_HISTORY,
            slope_per_day=quantize_ratio(slope),
            observation_count=len(points),
            first_observed_at=first.observed_at,
            last_observed_at=last.observed_at,
            calculated_at=as_of,
            insufficient=_reason(
                InsufficientReasonCode.ZERO_BASELINE_PRICE,
                "Trend percent change is unavailable because the first observed analysis "
                "price is zero.",
            ),
        )
    implied = quantize_ratio(slope * span_days / first.analysis_price * Decimal("100"))
    if abs(implied) <= stable_percent:
        direction = TrendDirection.STABLE
    elif implied > 0:
        direction = TrendDirection.RISING
    else:
        direction = TrendDirection.FALLING
    return TrendResult(
        status=MetricStatus.AVAILABLE,
        direction=direction,
        implied_percent_change=implied,
        slope_per_day=quantize_ratio(slope),
        method=TREND_METHOD_DESCRIPTION,
        observation_count=len(points),
        first_observed_at=first.observed_at,
        last_observed_at=last.observed_at,
        calculated_at=as_of,
        insufficient=None,
    )


def variant_freshness(
    points: Sequence[HistoricalObservationPoint],
    *,
    as_of: datetime,
    config: PricingConfig,
):
    """Freshness from actual observation timestamps, including unverified rows."""
    if not points:
        return offer_freshness(None, as_of=as_of, config=config)
    items = tuple(
        offer_freshness(point.observed_at, as_of=as_of, config=config) for point in points
    )
    return aggregate_freshness(items, as_of=as_of)


class PriceHistoryEngine:
    """Compute historical intelligence per matched product variant from stored observations."""

    def __init__(
        self,
        config: PricingConfig | None = None,
        *,
        metrics_sink: MetricsSink | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config if config is not None else get_pricing_config()
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._clock = clock if clock is not None else utc_now

    @property
    def config(self) -> PricingConfig:
        return self._config

    def compute_variant(
        self,
        *,
        product_id: uuid.UUID,
        product_variant_id: uuid.UUID,
        observations: Sequence[HistoricalObservationPoint],
        variant_key: str | None = None,
        as_of: datetime | None = None,
    ) -> VariantHistory:
        now = as_of if as_of is not None else self._clock()
        ordered = tuple(sorted(observations, key=_sort_key))
        qualifying = qualifying_observations(ordered)
        unverified_count = len(ordered) - len(qualifying)
        current = qualifying[-1] if qualifying else None
        currency = current.currency if current is not None else "INR"
        averages = {
            days: window_average(
                qualifying,
                window_days=days,
                as_of=now,
                min_count=self._config.min_observations_for_average,
                unit=currency,
            )
            for days in AVERAGE_WINDOW_DAYS
        }
        change_metric, baseline = percentage_change(qualifying, current=current, as_of=now)
        drop = detect_price_drop(
            current=current,
            baseline=baseline,
            change_metric=change_metric,
            as_of=now,
            observation_count=len(qualifying),
        )
        provenance = HistoryProvenance()
        result = VariantHistory(
            product_id=product_id,
            product_variant_id=product_variant_id,
            variant_key=variant_key,
            observations=ordered,
            qualifying_observation_count=len(qualifying),
            excluded_unverified_observation_count=unverified_count,
            current_observation=current,
            average_7d=averages[7],
            average_30d=averages[30],
            average_90d=averages[90],
            average_180d=averages[180],
            historical_low=historical_low(
                qualifying,
                as_of=now,
                min_count=self._config.min_observations_for_extrema,
                unit=currency,
            ),
            historical_high=historical_high(
                qualifying,
                as_of=now,
                min_count=self._config.min_observations_for_extrema,
                unit=currency,
            ),
            current_price_percentile=current_price_percentile(
                qualifying,
                current=current,
                as_of=now,
                min_count=self._config.min_observations_for_percentile,
            ),
            volatility=price_volatility(
                qualifying,
                as_of=now,
                min_count=self._config.min_observations_for_volatility,
                unit=currency,
            ),
            percentage_change=change_metric,
            price_drop=drop,
            trend=historical_trend(
                qualifying,
                as_of=now,
                min_count=self._config.min_observations_for_trend,
                stable_percent=Decimal(str(self._config.trend_stable_percent)),
            ),
            data_freshness=variant_freshness(ordered, as_of=now, config=self._config),
            provenance=provenance,
            calculated_at=now,
        )
        self._metrics.increment(HISTORY_VARIANTS)
        self._metrics.increment(HISTORY_OBSERVATIONS, value=len(ordered))
        logger.info(
            "pricing.variant_history_computed",
            extra={
                "product_id": str(product_id),
                "product_variant_id": str(product_variant_id),
                "observation_count": len(ordered),
                "qualifying_observation_count": len(qualifying),
                "excluded_unverified_observation_count": unverified_count,
                "freshness": result.data_freshness.status.value,
            },
        )
        return result

    def compute_product(
        self,
        product_id: uuid.UUID,
        variants: Mapping[uuid.UUID, Sequence[HistoricalObservationPoint]],
        *,
        variant_keys: Mapping[uuid.UUID, str] | None = None,
        as_of: datetime | None = None,
    ) -> ProductHistory:
        now = as_of if as_of is not None else self._clock()
        keys = variant_keys or {}
        computed = tuple(
            self.compute_variant(
                product_id=product_id,
                product_variant_id=variant_id,
                observations=observations,
                variant_key=keys.get(variant_id),
                as_of=now,
            )
            for variant_id, observations in variants.items()
        )
        freshness = aggregate_freshness(tuple(item.data_freshness for item in computed), as_of=now)
        logger.info(
            "pricing.product_history_computed",
            extra={
                "product_id": str(product_id),
                "variant_count": len(computed),
                "observation_count": sum(len(item.observations) for item in computed),
                "freshness": freshness.status.value,
            },
        )
        return ProductHistory(
            product_id=product_id,
            variants=computed,
            data_freshness=freshness,
            provenance=HistoryProvenance(),
            calculated_at=now,
            predicted=None,
        )
