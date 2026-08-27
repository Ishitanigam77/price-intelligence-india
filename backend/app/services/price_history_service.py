"""Price history service: load stored observations and compute historical intelligence.

Uses existing Product / ProductVariant / PriceSnapshot repositories. Calculation rules live
in `app.pricing.history` — this module projects persisted snapshots into
`HistoricalObservationPoint` values, asks `PriceHistoryEngine` to compute per-variant
history, and maps the result onto the API schema. Observations are never overwritten.
Predicted values are not produced.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.api.errors import NotFoundError
from app.db.models import PriceSnapshot, ProductVariant
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.config import PricingConfig, get_pricing_config
from app.pricing.history import PriceHistoryEngine
from app.pricing.history_models import HistoricalObservationPoint
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_variant_repository import ProductVariantRepository
from app.schemas.common import Page
from app.schemas.history import ProductHistoryRead, product_history_read

logger = get_logger(__name__)


class PriceHistoryService:
    """Orchestrates persistence → historical engine → API schema for one product."""

    def __init__(
        self,
        session: Session,
        *,
        metrics_sink: MetricsSink | None = None,
        config: PricingConfig | None = None,
        engine: PriceHistoryEngine | None = None,
    ) -> None:
        self._session = session
        self._products = ProductRepository(session)
        self._variants = ProductVariantRepository(session)
        self._snapshots = PriceSnapshotRepository(session)
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._engine = engine or PriceHistoryEngine(
            config=config if config is not None else get_pricing_config(),
            metrics_sink=self._metrics,
        )

    def get_product_history(
        self,
        product_id: uuid.UUID,
        *,
        variant_id: uuid.UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ProductHistoryRead:
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

        snapshots = self._snapshots.history_for_product(product_id, variant_id=variant_id)
        points_by_variant: dict[uuid.UUID, list[HistoricalObservationPoint]] = {
            variant.id: [] for variant in variants
        }
        for snapshot in snapshots:
            listing = snapshot.retailer_product
            variant = listing.product_variant
            if variant.id not in points_by_variant:
                continue
            points_by_variant[variant.id].append(
                self._point_from_snapshot(snapshot, product_id=product_id, variant=variant)
            )

        variant_keys = {variant.id: variant.variant_key for variant in variants}
        history = self._engine.compute_product(
            product_id,
            points_by_variant,
            variant_keys=variant_keys,
        )
        observation_pages = {
            variant.product_variant_id: _paginate_observations(
                variant.observations,
                since=since,
                until=until,
                limit=limit,
                offset=offset,
            )
            for variant in history.variants
        }
        logger.info(
            "price_history.product_completed",
            extra={
                "product_id": str(product_id),
                "variant_count": len(history.variants),
                "observation_count": sum(len(item.observations) for item in history.variants),
                "limit": limit,
                "offset": offset,
            },
        )
        return product_history_read(history, observation_pages=observation_pages)

    def _point_from_snapshot(
        self,
        snapshot: PriceSnapshot,
        *,
        product_id: uuid.UUID,
        variant: ProductVariant,
    ) -> HistoricalObservationPoint:
        listing = snapshot.retailer_product
        retailer = listing.retailer
        return HistoricalObservationPoint(
            snapshot_id=snapshot.id,
            product_id=product_id,
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
        )


def _paginate_observations(
    observations: tuple[HistoricalObservationPoint, ...],
    *,
    since: datetime | None,
    until: datetime | None,
    limit: int,
    offset: int,
) -> Page[HistoricalObservationPoint]:
    filtered = [
        point
        for point in observations
        if (since is None or point.observed_at >= since)
        and (until is None or point.observed_at <= until)
    ]
    total = len(filtered)
    window = filtered[offset : offset + limit]
    return Page[HistoricalObservationPoint](
        items=list(window), total=total, limit=limit, offset=offset
    )
