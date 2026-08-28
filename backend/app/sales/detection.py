"""Infer sale windows from concurrent observed price drops.

Output is always CALCULATED (`observed_price_inference`). Windows are unnamed generic
detections (date-stamped); real-world campaign names are never invented. Independent of
FastAPI and of specific retailer adapters.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from statistics import median

from app.domain.enums import ConfidenceLevel, SaleEventType
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.freshness import utc_now
from app.pricing.history import qualifying_observations
from app.pricing.history_models import HistoricalObservationPoint
from app.pricing.money import quantize_ratio
from app.sales.config import SalesConfig, get_sales_config
from app.sales.models import DetectedSaleWindow, SalePricePoint

logger = get_logger(__name__)

SALE_DETECTION_WINDOWS = "sales.detection.windows"


def _listing_key(point: HistoricalObservationPoint) -> tuple[uuid.UUID, uuid.UUID | None]:
    return (point.retailer_product_id, point.seller_id)


def _drop_percent(baseline: Decimal, price: Decimal) -> Decimal | None:
    if baseline <= 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 28
        return (baseline - price) / baseline * Decimal("100")


def _confidence(listing_count: int, config: SalesConfig) -> ConfidenceLevel:
    if listing_count >= config.high_confidence_listing_count:
        return ConfidenceLevel.HIGH
    if listing_count >= config.medium_confidence_listing_count:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


class SaleEventDetector:
    """Clusters concurrent verified price drops into calculated sale-window candidates."""

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

    def detect(self, points: Sequence[SalePricePoint]) -> tuple[DetectedSaleWindow, ...]:
        qualifying = qualifying_observations(tuple(item.observation for item in points))
        by_id = {item.observation.snapshot_id: item for item in points}
        discounted = self._discounted_observations(qualifying)
        retailer_windows = self._cluster(
            discounted,
            by_id=by_id,
            scope="retailer",
        )
        category_windows = self._cluster(
            discounted,
            by_id=by_id,
            scope="category",
        )
        brand_windows = self._cluster(
            discounted,
            by_id=by_id,
            scope="brand",
        )
        combined = tuple(
            sorted(
                (*retailer_windows, *category_windows, *brand_windows),
                key=lambda item: (item.start_date, item.event_type, item.name),
            )
        )
        self._metrics.increment(SALE_DETECTION_WINDOWS, value=len(combined))
        logger.info(
            "sales.detection.completed",
            extra={
                "qualifying_observation_count": len(qualifying),
                "discounted_observation_count": len(discounted),
                "window_count": len(combined),
            },
        )
        return combined

    def _discounted_observations(
        self, points: Sequence[HistoricalObservationPoint]
    ) -> tuple[tuple[HistoricalObservationPoint, Decimal], ...]:
        grouped: dict[tuple[uuid.UUID, uuid.UUID | None], list[HistoricalObservationPoint]] = (
            defaultdict(list)
        )
        for point in points:
            grouped[_listing_key(point)].append(point)

        threshold = Decimal(str(self._config.drop_percent_threshold))
        discounted: list[tuple[HistoricalObservationPoint, Decimal]] = []
        for series in grouped.values():
            series.sort(key=lambda item: (item.observed_at, item.created_at, item.snapshot_id))
            prior: list[Decimal] = []
            for point in series:
                if prior:
                    baseline = Decimal(str(median(prior)))
                    drop = _drop_percent(baseline, point.analysis_price)
                    if drop is not None and drop >= threshold:
                        discounted.append((point, quantize_ratio(drop)))
                prior.append(point.analysis_price)
        discounted.sort(key=lambda item: (item[0].observed_at, item[0].snapshot_id))
        return tuple(discounted)

    def _cluster(
        self,
        discounted: Sequence[tuple[HistoricalObservationPoint, Decimal]],
        *,
        by_id: dict[uuid.UUID, SalePricePoint],
        scope: str,
    ) -> tuple[DetectedSaleWindow, ...]:
        buckets: dict[uuid.UUID, list[tuple[HistoricalObservationPoint, Decimal]]] = defaultdict(
            list
        )
        for point, drop in discounted:
            sale_point = by_id[point.snapshot_id]
            scope_id = self._scope_id(point, sale_point, scope)
            if scope_id is None:
                continue
            buckets[scope_id].append((point, drop))

        max_gap = timedelta(days=self._config.max_gap_days)
        min_listings = self._config.min_listings_for_detection
        windows: list[DetectedSaleWindow] = []
        for scope_id, items in buckets.items():
            items.sort(key=lambda pair: (pair[0].observed_at, pair[0].snapshot_id))
            cluster: list[tuple[HistoricalObservationPoint, Decimal]] = []
            for point, drop in items:
                if cluster and (point.observed_at - cluster[-1][0].observed_at) > max_gap:
                    window = self._window_from_cluster(cluster, scope=scope, scope_id=scope_id)
                    if window is not None and window.listing_count >= min_listings:
                        windows.append(window)
                    cluster = []
                cluster.append((point, drop))
            window = self._window_from_cluster(cluster, scope=scope, scope_id=scope_id)
            if window is not None and window.listing_count >= min_listings:
                windows.append(window)
        return tuple(windows)

    @staticmethod
    def _scope_id(
        point: HistoricalObservationPoint, sale_point: SalePricePoint, scope: str
    ) -> uuid.UUID | None:
        if scope == "retailer":
            return point.retailer_id
        if scope == "category":
            return sale_point.category_id
        if scope == "brand":
            return sale_point.brand_id
        return None

    def _window_from_cluster(
        self,
        cluster: Sequence[tuple[HistoricalObservationPoint, Decimal]],
        *,
        scope: str,
        scope_id: uuid.UUID,
    ) -> DetectedSaleWindow | None:
        if not cluster:
            return None
        points = [item[0] for item in cluster]
        drops = [item[1] for item in cluster]
        listings = {_listing_key(point) for point in points}
        start = points[0].observed_at
        end = points[-1].observed_at
        listing_count = len(listings)
        median_drop = quantize_ratio(Decimal(str(median(drops)))) if drops else None
        event_type, retailer_id, category_id, brand_id, label = self._scope_fields(scope, scope_id)
        date_stamp = start.date().isoformat()
        return DetectedSaleWindow(
            name=f"Detected {label} sale {date_stamp}",
            retailer_id=retailer_id,
            category_id=category_id,
            brand_id=brand_id,
            start_date=start,
            end_date=end,
            event_type=event_type,
            confidence=_confidence(listing_count, self._config),
            listing_count=listing_count,
            median_drop_percent=median_drop,
            observation_count=len(points),
        )

    @staticmethod
    def _scope_fields(
        scope: str, scope_id: uuid.UUID
    ) -> tuple[SaleEventType, uuid.UUID | None, uuid.UUID | None, uuid.UUID | None, str]:
        if scope == "retailer":
            return SaleEventType.RETAILER_SPECIFIC, scope_id, None, None, "retailer"
        if scope == "category":
            return SaleEventType.CATEGORY, None, scope_id, None, "category"
        return SaleEventType.BRAND, None, None, scope_id, "brand"
