"""Historical sale-price analysis over stored observations overlapping sale events.

Inputs are stored observations and persisted (or otherwise supplied) sale events. Missing
history is reported as insufficient — never replaced with zeros, guesses, or predictions.
Variants are never mixed. Independent of FastAPI and of specific retailer adapters.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal, localcontext
from statistics import median

from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.enums import MetricStatus, ValueKind
from app.pricing.freshness import utc_now
from app.pricing.history import qualifying_observations
from app.pricing.history_models import HistoricalObservationPoint
from app.pricing.money import quantize_money, quantize_ratio
from app.sales.applicability import (
    applicable_events,
    observations_during_event,
)
from app.sales.config import SalesConfig, get_sales_config
from app.sales.enums import SaleInsufficientReasonCode
from app.sales.lifecycle import view_at
from app.sales.models import (
    EventWindowHistory,
    ProductSaleHistory,
    SaleCalculatedMetric,
    SaleEventRecord,
    SaleHistoryProvenance,
    SaleInsufficient,
    SalePricePoint,
    VariantSaleHistory,
)

logger = get_logger(__name__)

SALE_HISTORY_VARIANTS = "sales.history.variants"
SALE_HISTORY_EVENTS = "sales.history.events"

ANALYSIS_PRICE_RULE = (
    "Each qualifying observation contributes its stored effective_price when that field was "
    "recorded, otherwise its observed displayed_price. Missing prices are never invented. "
    "An observation belongs to a sale event only when its observed_at falls inside the event "
    "window and the event's optional retailer/category/brand scope matches."
)

DETECTION_RULE = (
    "Sale events supplied to this engine are treated as given records. This engine does not "
    "invent named real-world campaigns. Calculated statistics describe observed prices during "
    "those windows; they are not forecasts."
)


def _reason(code: SaleInsufficientReasonCode, detail: str) -> SaleInsufficient:
    return SaleInsufficient(code=code, reason=detail)


def _unavailable(
    *,
    unit: str,
    calculated_at: datetime,
    observation_count: int,
    code: SaleInsufficientReasonCode,
    detail: str,
    extra: dict[str, Decimal | int | str | None] | None = None,
) -> SaleCalculatedMetric:
    return SaleCalculatedMetric(
        value_kind=ValueKind.CALCULATED,
        status=MetricStatus.INSUFFICIENT_HISTORY,
        value=None,
        unit=unit,
        observation_count=observation_count,
        calculated_at=calculated_at,
        insufficient=_reason(code, detail),
        extra=extra or {},
    )


def _available(
    *,
    value: Decimal,
    unit: str,
    calculated_at: datetime,
    observation_count: int,
    extra: dict[str, Decimal | int | str | None] | None = None,
) -> SaleCalculatedMetric:
    return SaleCalculatedMetric(
        value_kind=ValueKind.CALCULATED,
        status=MetricStatus.AVAILABLE,
        value=value,
        unit=unit,
        observation_count=observation_count,
        calculated_at=calculated_at,
        insufficient=None,
        extra=extra or {},
    )


def _mean(prices: Sequence[Decimal]) -> Decimal:
    total = sum(prices, start=Decimal("0"))
    with localcontext() as ctx:
        ctx.prec = 28
        return quantize_money(total / Decimal(len(prices)))


def _extrema_sort_key(item: HistoricalObservationPoint) -> tuple[Decimal, datetime, uuid.UUID]:
    return (item.analysis_price, item.observed_at, item.snapshot_id)


def _stats_from_points(
    points: Sequence[HistoricalObservationPoint],
    *,
    calculated_at: datetime,
    min_count: int,
    unit: str,
) -> tuple[SaleCalculatedMetric, SaleCalculatedMetric, SaleCalculatedMetric]:
    count = len(points)
    if count < min_count:
        detail = (
            f"Need at least {min_count} qualifying observation(s) during the sale window; "
            f"got {count}."
        )
        code = (
            SaleInsufficientReasonCode.NO_OBSERVATIONS_DURING_EVENT
            if count == 0
            else SaleInsufficientReasonCode.BELOW_MINIMUM_OBSERVATION_COUNT
        )
        unavailable = _unavailable(
            unit=unit,
            calculated_at=calculated_at,
            observation_count=count,
            code=code,
            detail=detail,
        )
        return unavailable, unavailable, unavailable

    prices = [point.analysis_price for point in points]
    average = _available(
        value=_mean(prices),
        unit=unit,
        calculated_at=calculated_at,
        observation_count=count,
    )
    low_point = min(points, key=_extrema_sort_key)
    high_point = max(points, key=_extrema_sort_key)
    low = _available(
        value=quantize_money(low_point.analysis_price),
        unit=unit,
        calculated_at=calculated_at,
        observation_count=count,
        extra={
            "snapshot_id": str(low_point.snapshot_id),
            "observed_at": low_point.observed_at.isoformat(),
            "retailer_id": str(low_point.retailer_id),
        },
    )
    high = _available(
        value=quantize_money(high_point.analysis_price),
        unit=unit,
        calculated_at=calculated_at,
        observation_count=count,
        extra={
            "snapshot_id": str(high_point.snapshot_id),
            "observed_at": high_point.observed_at.isoformat(),
            "retailer_id": str(high_point.retailer_id),
        },
    )
    return average, low, high


def _percent_below_baseline(
    *,
    sale_average: SaleCalculatedMetric,
    baseline: SaleCalculatedMetric,
    calculated_at: datetime,
) -> SaleCalculatedMetric:
    if sale_average.status is not MetricStatus.AVAILABLE or sale_average.value is None:
        return _unavailable(
            unit="percent",
            calculated_at=calculated_at,
            observation_count=sale_average.observation_count,
            code=(
                sale_average.insufficient.code
                if sale_average.insufficient is not None
                else SaleInsufficientReasonCode.NO_OBSERVATIONS_DURING_EVENT
            ),
            detail=(
                sale_average.insufficient.reason
                if sale_average.insufficient is not None
                else "Sale-window average is unavailable."
            ),
        )
    if baseline.status is not MetricStatus.AVAILABLE or baseline.value is None:
        return _unavailable(
            unit="percent",
            calculated_at=calculated_at,
            observation_count=baseline.observation_count,
            code=(
                baseline.insufficient.code
                if baseline.insufficient is not None
                else SaleInsufficientReasonCode.NO_QUALIFYING_OBSERVATIONS
            ),
            detail=(
                baseline.insufficient.reason
                if baseline.insufficient is not None
                else "Non-sale baseline is unavailable."
            ),
        )
    if baseline.value == 0:
        return _unavailable(
            unit="percent",
            calculated_at=calculated_at,
            observation_count=sale_average.observation_count,
            code=SaleInsufficientReasonCode.ZERO_BASELINE_PRICE,
            detail="Non-sale baseline price is zero; percent change is undefined.",
        )
    with localcontext() as ctx:
        ctx.prec = 28
        percent = quantize_ratio(
            (baseline.value - sale_average.value) / baseline.value * Decimal("100")
        )
    return _available(
        value=percent,
        unit="percent",
        calculated_at=calculated_at,
        observation_count=sale_average.observation_count,
        extra={"baseline_observation_count": baseline.observation_count},
    )


class SaleHistoryEngine:
    """Computes per-variant sale-price history from stored observations and sale events."""

    def __init__(
        self,
        config: SalesConfig | None = None,
        *,
        metrics_sink: MetricsSink | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config if config is not None else get_sales_config()
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._clock = clock if clock is not None else utc_now

    @property
    def config(self) -> SalesConfig:
        return self._config

    def compute_product(
        self,
        product_id: uuid.UUID,
        points_by_variant: dict[uuid.UUID, Sequence[SalePricePoint]],
        events: Sequence[SaleEventRecord],
        *,
        brand_id: uuid.UUID | None,
        category_id: uuid.UUID | None,
        variant_keys: dict[uuid.UUID, str | None] | None = None,
    ) -> ProductSaleHistory:
        calculated_at = self._clock()
        matching_events = applicable_events(events, brand_id=brand_id, category_id=category_id)
        event_views = tuple(
            sorted(
                (view_at(event, at=calculated_at) for event in matching_events),
                key=lambda item: (item.event.start_date, item.event.id),
            )
        )
        variants = tuple(
            self.compute_variant(
                product_id=product_id,
                product_variant_id=variant_id,
                points=points,
                events=matching_events,
                variant_key=(variant_keys or {}).get(variant_id),
                calculated_at=calculated_at,
            )
            for variant_id, points in points_by_variant.items()
        )
        self._metrics.increment(SALE_HISTORY_VARIANTS, value=len(variants))
        self._metrics.increment(SALE_HISTORY_EVENTS, value=len(event_views))
        logger.info(
            "sales.history.product_completed",
            extra={
                "product_id": str(product_id),
                "variant_count": len(variants),
                "event_count": len(event_views),
            },
        )
        return ProductSaleHistory(
            product_id=product_id,
            events=event_views,
            variants=variants,
            provenance=SaleHistoryProvenance(
                analysis_price_rule=ANALYSIS_PRICE_RULE,
                detection_rule=DETECTION_RULE,
            ),
            calculated_at=calculated_at,
            predicted=None,
        )

    def compute_variant(
        self,
        *,
        product_id: uuid.UUID,
        product_variant_id: uuid.UUID,
        points: Sequence[SalePricePoint],
        events: Sequence[SaleEventRecord],
        variant_key: str | None = None,
        calculated_at: datetime | None = None,
    ) -> VariantSaleHistory:
        as_of = calculated_at if calculated_at is not None else self._clock()
        observations = tuple(point.observation for point in points)
        qualifying = qualifying_observations(observations)
        excluded = len(observations) - len(qualifying)
        qualifying_ids = {point.snapshot_id for point in qualifying}
        qualifying_sale_points = [
            point for point in points if point.observation.snapshot_id in qualifying_ids
        ]
        min_count = self._config.min_observations_for_sale_stats
        unit = qualifying[0].currency if qualifying else "INR"

        if not events:
            unavailable_events = _unavailable(
                unit=unit,
                calculated_at=as_of,
                observation_count=0,
                code=SaleInsufficientReasonCode.NO_APPLICABLE_EVENTS,
                detail="No sale events apply to this product; sale-window statistics are withheld.",
            )
            baseline = self._baseline(
                qualifying, calculated_at=as_of, min_count=min_count, unit=unit
            )
            vs_baseline = _percent_below_baseline(
                sale_average=unavailable_events, baseline=baseline, calculated_at=as_of
            )
            return VariantSaleHistory(
                product_id=product_id,
                product_variant_id=product_variant_id,
                variant_key=variant_key,
                event_windows=(),
                qualifying_observation_count=len(qualifying),
                excluded_unverified_observation_count=excluded,
                overall_sale_average=unavailable_events,
                overall_sale_low=unavailable_events,
                overall_sale_high=unavailable_events,
                non_sale_baseline=baseline,
                vs_non_sale_baseline_percent=vs_baseline,
                calculated_at=as_of,
            )

        in_any_event: list[HistoricalObservationPoint] = []
        seen: set[uuid.UUID] = set()
        windows: list[EventWindowHistory] = []
        for event in sorted(events, key=lambda item: (item.start_date, item.id)):
            during = observations_during_event(event, qualifying_sale_points)
            for point in during:
                if point.snapshot_id not in seen:
                    seen.add(point.snapshot_id)
                    in_any_event.append(point)
            average, low, high = _stats_from_points(
                during, calculated_at=as_of, min_count=min_count, unit=unit
            )
            non_sale_for_event = [
                point
                for point in qualifying
                if point.snapshot_id not in {item.snapshot_id for item in during}
            ]
            event_baseline = self._baseline(
                non_sale_for_event, calculated_at=as_of, min_count=min_count, unit=unit
            )
            windows.append(
                EventWindowHistory(
                    event=view_at(event, at=as_of),
                    observations=during,
                    observation_count=len(during),
                    sale_average=average,
                    sale_low=low,
                    sale_high=high,
                    vs_non_sale_baseline_percent=_percent_below_baseline(
                        sale_average=average, baseline=event_baseline, calculated_at=as_of
                    ),
                )
            )

        overall_avg, overall_low, overall_high = _stats_from_points(
            in_any_event, calculated_at=as_of, min_count=min_count, unit=unit
        )
        non_sale = [point for point in qualifying if point.snapshot_id not in seen]
        baseline = self._baseline(non_sale, calculated_at=as_of, min_count=min_count, unit=unit)
        return VariantSaleHistory(
            product_id=product_id,
            product_variant_id=product_variant_id,
            variant_key=variant_key,
            event_windows=tuple(windows),
            qualifying_observation_count=len(qualifying),
            excluded_unverified_observation_count=excluded,
            overall_sale_average=overall_avg,
            overall_sale_low=overall_low,
            overall_sale_high=overall_high,
            non_sale_baseline=baseline,
            vs_non_sale_baseline_percent=_percent_below_baseline(
                sale_average=overall_avg, baseline=baseline, calculated_at=as_of
            ),
            calculated_at=as_of,
        )

    def _baseline(
        self,
        points: Sequence[HistoricalObservationPoint],
        *,
        calculated_at: datetime,
        min_count: int,
        unit: str,
    ) -> SaleCalculatedMetric:
        if not points:
            return _unavailable(
                unit=unit,
                calculated_at=calculated_at,
                observation_count=0,
                code=SaleInsufficientReasonCode.NO_QUALIFYING_OBSERVATIONS,
                detail="No qualifying non-sale observations are available for a baseline.",
            )
        if len(points) < min_count:
            return _unavailable(
                unit=unit,
                calculated_at=calculated_at,
                observation_count=len(points),
                code=SaleInsufficientReasonCode.BELOW_MINIMUM_OBSERVATION_COUNT,
                detail=(
                    f"Need at least {min_count} qualifying non-sale observation(s); "
                    f"got {len(points)}."
                ),
            )
        prices = [point.analysis_price for point in points]
        extra: dict[str, Decimal | int | str | None] = {
            "median": quantize_money(Decimal(str(median(prices))))
        }
        return _available(
            value=_mean(prices),
            unit=unit,
            calculated_at=calculated_at,
            observation_count=len(points),
            extra=extra,
        )
