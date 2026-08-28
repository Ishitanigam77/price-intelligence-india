"""Facade for sale-event lifecycle views and historical sale-price analysis."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import datetime

from app.domain.enums import SaleEventStatus
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.freshness import utc_now
from app.sales.config import SalesConfig, get_sales_config
from app.sales.history import SaleHistoryEngine
from app.sales.lifecycle import event_status, view_at
from app.sales.models import (
    ProductSaleHistory,
    SaleEventRecord,
    SaleEventView,
    SalePricePoint,
)


class SaleEventEngine:
    """Retailer-agnostic sale-event intelligence. Does not predict prices."""

    def __init__(
        self,
        config: SalesConfig | None = None,
        *,
        metrics_sink: MetricsSink | None = None,
        clock: Callable[[], datetime] | None = None,
        history_engine: SaleHistoryEngine | None = None,
    ) -> None:
        self._config = config if config is not None else get_sales_config()
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._clock = clock if clock is not None else utc_now
        self._history = history_engine or SaleHistoryEngine(
            config=self._config,
            metrics_sink=self._metrics,
            clock=self._clock,
        )

    @property
    def config(self) -> SalesConfig:
        return self._config

    def status_at(
        self,
        record: SaleEventRecord,
        *,
        at: datetime | None = None,
    ) -> SaleEventView:
        moment = at if at is not None else self._clock()
        return view_at(record, at=moment)

    def views(
        self,
        records: Sequence[SaleEventRecord],
        *,
        at: datetime | None = None,
    ) -> tuple[SaleEventView, ...]:
        moment = at if at is not None else self._clock()
        return tuple(view_at(record, at=moment) for record in records)

    def upcoming(
        self,
        records: Sequence[SaleEventRecord],
        *,
        at: datetime | None = None,
    ) -> tuple[SaleEventView, ...]:
        moment = at if at is not None else self._clock()
        matching = [
            view_at(record, at=moment)
            for record in records
            if event_status(start_date=record.start_date, end_date=record.end_date, at=moment)
            is SaleEventStatus.BEFORE_EVENT
        ]
        matching.sort(key=lambda item: (item.event.start_date, item.event.id))
        return tuple(matching)

    def compute_product_history(
        self,
        product_id: uuid.UUID,
        points_by_variant: dict[uuid.UUID, Sequence[SalePricePoint]],
        events: Sequence[SaleEventRecord],
        *,
        brand_id: uuid.UUID | None,
        category_id: uuid.UUID | None,
        variant_keys: dict[uuid.UUID, str | None] | None = None,
    ) -> ProductSaleHistory:
        return self._history.compute_product(
            product_id,
            points_by_variant,
            events,
            brand_id=brand_id,
            category_id=category_id,
            variant_keys=variant_keys,
        )
