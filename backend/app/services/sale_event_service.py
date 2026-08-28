"""Sale-event service: persist sale windows and compute product sale history.

Projects ORM rows into `app.sales` records, asks `SaleEventEngine` for lifecycle and
historical analysis, and maps the result onto the API schema. Does not predict prices and
does not invent real-world sale campaigns.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.api.errors import NotFoundError
from app.db.models import PriceSnapshot, Product, ProductVariant, SaleEvent
from app.domain.enums import SaleEventSource, SaleEventStatus, SaleEventType
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.freshness import utc_now
from app.pricing.history_models import HistoricalObservationPoint
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_variant_repository import ProductVariantRepository
from app.repositories.sale_event_repository import SaleEventRepository
from app.sales.config import SalesConfig, get_sales_config
from app.sales.engine import SaleEventEngine
from app.sales.lifecycle import view_at
from app.sales.models import SaleEventRecord, SaleEventView, SalePricePoint
from app.schemas.common import Page
from app.schemas.sale_event import (
    ProductSaleHistoryRead,
    SaleEventRead,
    product_sale_history_read,
    sale_event_read,
)

logger = get_logger(__name__)


class SaleEventService:
    """Orchestrates persistence → sale-event engine → API schema."""

    def __init__(
        self,
        session: Session,
        *,
        metrics_sink: MetricsSink | None = None,
        config: SalesConfig | None = None,
        engine: SaleEventEngine | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._events = SaleEventRepository(session)
        self._products = ProductRepository(session)
        self._variants = ProductVariantRepository(session)
        self._snapshots = PriceSnapshotRepository(session)
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._clock = clock if clock is not None else utc_now
        self._engine = engine or SaleEventEngine(
            config=config if config is not None else get_sales_config(),
            metrics_sink=self._metrics,
            clock=self._clock,
        )

    def list_events(
        self,
        *,
        event_type: SaleEventType | None = None,
        source: SaleEventSource | None = None,
        retailer_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        status: SaleEventStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[SaleEventRead]:
        at = self._clock()
        items = self._events.list_filtered(
            event_type=event_type,
            source=source,
            retailer_id=retailer_id,
            category_id=category_id,
            brand_id=brand_id,
            status=status,
            at=at,
            limit=limit,
            offset=offset,
        )
        total = self._events.count_filtered(
            event_type=event_type,
            source=source,
            retailer_id=retailer_id,
            category_id=category_id,
            brand_id=brand_id,
            status=status,
            at=at,
        )
        return Page[SaleEventRead](
            items=[self._read(row, at=at) for row in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def list_upcoming(
        self,
        *,
        retailer_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[SaleEventRead]:
        at = self._clock()
        items = self._events.list_upcoming(
            at=at,
            retailer_id=retailer_id,
            category_id=category_id,
            brand_id=brand_id,
            limit=limit,
            offset=offset,
        )
        total = self._events.count_upcoming(
            at=at,
            retailer_id=retailer_id,
            category_id=category_id,
            brand_id=brand_id,
        )
        return Page[SaleEventRead](
            items=[self._read(row, at=at) for row in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_event(self, event_id: uuid.UUID) -> SaleEventRead:
        event = self._events.get_by_id(event_id)
        if event is None:
            raise NotFoundError(f"Sale event {event_id} was not found.")
        return self._read(event, at=self._clock())

    def get_product_sale_history(
        self,
        product_id: uuid.UUID,
        *,
        variant_id: uuid.UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ProductSaleHistoryRead:
        product = self._products.get_by_id(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} was not found.")

        variants = self._variants.list_for_product(product_id)
        if variant_id is not None:
            variants = [variant for variant in variants if variant.id == variant_id]
            if not variants:
                raise NotFoundError(
                    f"Product variant {variant_id} was not found on product {product_id}."
                )

        events = [
            self._record(row)
            for row in self._events.list_applicable_to_product(
                brand_id=product.brand_id, category_id=product.category_id
            )
        ]
        snapshots = self._snapshots.history_for_product(product_id, variant_id=variant_id)
        points_by_variant: dict[uuid.UUID, list[SalePricePoint]] = {
            variant.id: [] for variant in variants
        }
        for snapshot in snapshots:
            listing = snapshot.retailer_product
            variant = listing.product_variant
            if variant.id not in points_by_variant:
                continue
            points_by_variant[variant.id].append(
                self._point_from_snapshot(snapshot, product=product, variant=variant)
            )

        variant_keys = {variant.id: variant.variant_key for variant in variants}
        history = self._engine.compute_product_history(
            product_id,
            points_by_variant,
            events,
            brand_id=product.brand_id,
            category_id=product.category_id,
            variant_keys=variant_keys,
        )
        logger.info(
            "sales.product_sale_history.completed",
            extra={
                "product_id": str(product_id),
                "variant_count": len(history.variants),
                "event_count": len(history.events),
                "limit": limit,
                "offset": offset,
            },
        )
        return product_sale_history_read(
            history,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )

    def _read(self, event: SaleEvent, *, at: datetime) -> SaleEventRead:
        return sale_event_read(
            self._view(event, at=at),
            created_at=event.created_at,
            updated_at=event.updated_at,
        )

    def _view(self, event: SaleEvent, *, at: datetime) -> SaleEventView:
        return view_at(self._record(event), at=at)

    @staticmethod
    def _record(event: SaleEvent) -> SaleEventRecord:
        return SaleEventRecord(
            id=event.id,
            name=event.name,
            retailer_id=event.retailer_id,
            category_id=event.category_id,
            brand_id=event.brand_id,
            start_date=event.start_date,
            end_date=event.end_date,
            event_type=event.event_type,
            source=event.source,
            source_ref=event.source_ref,
            confidence=event.confidence,
        )

    @staticmethod
    def _point_from_snapshot(
        snapshot: PriceSnapshot,
        *,
        product: Product,
        variant: ProductVariant,
    ) -> SalePricePoint:
        listing = snapshot.retailer_product
        retailer = listing.retailer
        return SalePricePoint(
            observation=HistoricalObservationPoint(
                snapshot_id=snapshot.id,
                product_id=product.id,
                product_variant_id=variant.id,
                variant_key=variant.variant_key,
                retailer_id=listing.retailer_id,
                retailer_slug=retailer.slug,
                retailer_name=retailer.name,
                retailer_product_id=listing.id,
                seller_id=snapshot.seller_id,
                source_url=snapshot.source_url or listing.url,
                source_type=snapshot.source_type,
                observed_at=snapshot.observed_at,
                created_at=snapshot.created_at,
                currency=snapshot.currency,
                displayed_price=snapshot.displayed_price,
                effective_price=snapshot.effective_price,
                mrp=snapshot.mrp,
                availability=snapshot.availability,
                confidence=snapshot.confidence,
            ),
            brand_id=product.brand_id,
            category_id=product.category_id,
        )
