"""Sale-timing intelligence service: calendar, major vs ordinary, expected retailers.

Projects persisted observations, comparison offers, sale events, and optional Phase 10
predictions into `SaleIntelligenceEngine`. Does not train models or invent dates/prices.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.api.errors import NotFoundError
from app.db.models import Product, ProductVariant
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.config import PricingConfig, get_pricing_config
from app.pricing.engine import PriceComparisonEngine
from app.pricing.freshness import utc_now
from app.pricing.models import OfferInput, VariantComparison
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_variant_repository import ProductVariantRepository
from app.repositories.retailer_product_repository import RetailerProductRepository
from app.repositories.sale_event_repository import SaleEventRepository
from app.sales.calendar import map_sale_calendar
from app.sales.config import SalesConfig, get_sales_config
from app.sales.intelligence import SaleIntelligenceEngine
from app.sales.timing_models import ListingPredictionInput, ProductSaleIntelligence
from app.schemas.intelligence import (
    ProductSaleIntelligenceRead,
    SaleCalendarPage,
    expected_window_read,
    product_sale_intelligence_read,
)
from app.schemas.prediction import SalePricePredictionRead
from app.services.price_comparison_service import PriceComparisonService
from app.services.sale_event_service import SaleEventService
from app.services.sale_price_prediction_service import SalePricePredictionService

logger = get_logger(__name__)


class SaleIntelligenceService:
    """Orchestrates persistence → comparison + calendar + optional ML → API schema."""

    def __init__(
        self,
        session: Session,
        *,
        metrics_sink: MetricsSink | None = None,
        clock: Callable[[], datetime] | None = None,
        sales_config: SalesConfig | None = None,
        pricing_config: PricingConfig | None = None,
        comparison_service: PriceComparisonService | None = None,
        prediction_service: SalePricePredictionService | None = None,
        engine: SaleIntelligenceEngine | None = None,
    ) -> None:
        self._session = session
        self._products = ProductRepository(session)
        self._variants = ProductVariantRepository(session)
        self._listings = RetailerProductRepository(session)
        self._snapshots = PriceSnapshotRepository(session)
        self._events = SaleEventRepository(session)
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._clock = clock if clock is not None else utc_now
        self._sales_config = sales_config if sales_config is not None else get_sales_config()
        self._pricing_config = (
            pricing_config if pricing_config is not None else get_pricing_config()
        )
        self._comparison = comparison_service or PriceComparisonService(
            session, metrics_sink=self._metrics, config=self._pricing_config
        )
        self._prediction = prediction_service or SalePricePredictionService(
            session, metrics_sink=self._metrics, clock=self._clock
        )
        self._engine = engine or SaleIntelligenceEngine(config=self._sales_config)

    def get_product_intelligence(
        self,
        product_id: uuid.UUID,
        *,
        variant_id: uuid.UUID | None = None,
        as_of: datetime | None = None,
        model_version: str | None = None,
    ) -> ProductSaleIntelligenceRead:
        product = self._products.get_by_id(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} was not found.")
        at = as_of if as_of is not None else self._clock()
        variants = self._variants.list_for_product(product_id)
        if variant_id is not None:
            variants = [variant for variant in variants if variant.id == variant_id]
            if not variants:
                raise NotFoundError(
                    f"Product variant {variant_id} was not found on product {product_id}."
                )

        payload = self.compute_product(
            product,
            variants,
            as_of=at,
            model_version=model_version,
            variant_id=variant_id,
        )
        logger.info(
            "sale_intelligence.product_completed",
            extra={
                "product_id": str(product_id),
                "variant_count": len(payload.variants),
                "as_of": at.isoformat(),
            },
        )
        return product_sale_intelligence_read(payload)

    def compute_product(
        self,
        product: Product,
        variants: list[ProductVariant],
        *,
        as_of: datetime,
        model_version: str | None = None,
        variant_id: uuid.UUID | None = None,
    ) -> ProductSaleIntelligence:
        engine_comparison = self._engine_comparison(product.id, variants)
        events = [
            SaleEventService._record(row)
            for row in self._events.list_applicable_to_product(
                brand_id=product.brand_id, category_id=product.category_id
            )
        ]
        snapshots = self._snapshots.history_for_product(product.id, variant_id=variant_id)
        points_by_variant: dict[uuid.UUID, list] = {variant.id: [] for variant in variants}
        for snapshot in snapshots:
            listing = snapshot.retailer_product
            variant = listing.product_variant
            if variant.id not in points_by_variant:
                continue
            points_by_variant[variant.id].append(
                SaleEventService._point_from_snapshot(snapshot, product=product, variant=variant)
            )
        predictions = self._prediction.predict_product(
            product.id, variant_id=variant_id, as_of=as_of, model_version=model_version
        )
        pred_by_variant: dict[uuid.UUID, list[ListingPredictionInput]] = defaultdict(list)
        for item in predictions.predictions:
            if item.product_variant_id is None or item.retailer_id is None:
                continue
            pred_by_variant[item.product_variant_id].append(_listing_prediction(item))

        variant_keys = {variant.id: variant.variant_key for variant in variants}
        return self._engine.compute_product(
            product_id=product.id,
            variant_comparisons=engine_comparison,
            points_by_variant=points_by_variant,
            events=events,
            predictions_by_variant=pred_by_variant,
            variant_keys=variant_keys,
            as_of=as_of,
        )

    def list_calendar(
        self,
        *,
        as_of: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SaleCalendarPage:
        at = as_of if as_of is not None else self._clock()
        rows = self._events.list_filtered(limit=1000, offset=0)
        events = [SaleEventService._record(row) for row in rows]
        windows = map_sale_calendar(events, (), as_of=at, config=self._sales_config)
        total = len(windows)
        page = windows[offset : offset + limit]
        return SaleCalendarPage(
            as_of=at,
            items=[expected_window_read(item) for item in page],
            total=total,
            limit=limit,
            offset=offset,
        )

    def _engine_comparison(
        self, product_id: uuid.UUID, variants: list[ProductVariant]
    ) -> dict[uuid.UUID, VariantComparison]:
        """Reuse PriceComparisonEngine on the same snapshots the compare API uses."""
        listings = self._listings.list_for_product(product_id)
        listing_ids = [listing.id for listing in listings]
        snapshots = self._snapshots.latest_per_seller_for_retailer_products(listing_ids)
        by_listing: dict[uuid.UUID, list] = defaultdict(list)
        for snapshot in snapshots:
            by_listing[snapshot.retailer_product_id].append(snapshot)
        listings_by_variant: dict[uuid.UUID, list] = defaultdict(list)
        for listing in listings:
            listings_by_variant[listing.product_variant_id].append(listing)
        offer_map: dict[uuid.UUID, list[OfferInput]] = {}
        for variant in variants:
            offers: list[OfferInput] = []
            for listing in listings_by_variant.get(variant.id, []):
                listing_snapshots = by_listing.get(listing.id, [])
                if not listing_snapshots:
                    offers.append(self._comparison._listing_without_snapshot(listing, variant.id))
                    continue
                offers.extend(
                    self._comparison._offer_from_snapshot(listing, snapshot, variant.id)
                    for snapshot in listing_snapshots
                )
            offer_map[variant.id] = offers
        engine = PriceComparisonEngine(config=self._pricing_config, metrics_sink=self._metrics)
        keys = {variant.id: variant.variant_key for variant in variants}
        comparison = engine.compare_product(product_id, offer_map, variant_keys=keys)
        return {item.variant_id: item for item in comparison.variants}


def _listing_prediction(item: SalePricePredictionRead) -> ListingPredictionInput:
    status = item.status.value if hasattr(item.status, "value") else str(item.status)
    assert item.retailer_id is not None
    return ListingPredictionInput(
        retailer_id=item.retailer_id,
        seller_id=item.seller_id,
        status=status,
        predicted_price=item.predicted_price,
        lower_bound=item.lower_bound,
        upper_bound=item.upper_bound,
        confidence=item.confidence,
    )
