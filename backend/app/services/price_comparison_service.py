"""Price comparison service: load matched listings and rank verified offers.

Uses existing Product / ProductVariant / RetailerProduct / PriceSnapshot / Seller repositories
plus optional `PriceAdjustment` rows. Comparison rules live in `app.pricing` — this module
only projects persisted data into `OfferInput` values and maps the engine result to the API
schema. No ML, no sale-event logic, no retailer-identity branching.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from app.api.errors import NotFoundError
from app.db.models import PriceSnapshot, RetailerProduct
from app.db.models.price_adjustment import PriceAdjustment as PriceAdjustmentRow
from app.domain.enums import AvailabilityStatus, SourceType
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.config import PricingConfig, get_pricing_config
from app.pricing.engine import PriceComparisonEngine
from app.pricing.models import OfferInput, PriceAdjustment, SellerSnapshot
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_variant_repository import ProductVariantRepository
from app.repositories.retailer_product_repository import RetailerProductRepository
from app.schemas.comparison import ProductPricesRead, product_prices_read

logger = get_logger(__name__)


class PriceComparisonService:
    """Orchestrates persistence → comparison engine → API schema for one product."""

    def __init__(
        self,
        session: Session,
        *,
        metrics_sink: MetricsSink | None = None,
        config: PricingConfig | None = None,
        engine: PriceComparisonEngine | None = None,
    ) -> None:
        self._session = session
        self._products = ProductRepository(session)
        self._variants = ProductVariantRepository(session)
        self._listings = RetailerProductRepository(session)
        self._snapshots = PriceSnapshotRepository(session)
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._engine = engine or PriceComparisonEngine(
            config=config if config is not None else get_pricing_config(),
            metrics_sink=self._metrics,
        )

    def compare_product(self, product_id: uuid.UUID) -> ProductPricesRead:
        product = self._products.get_by_id(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} was not found.")

        variants = self._variants.list_for_product(product_id)
        listings = self._listings.list_for_product(product_id)
        listing_ids = [listing.id for listing in listings]
        snapshots = self._snapshots.latest_per_seller_for_retailer_products(listing_ids)
        snapshots_by_listing: dict[uuid.UUID, list[PriceSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            snapshots_by_listing[snapshot.retailer_product_id].append(snapshot)

        listings_by_variant: dict[uuid.UUID, list[RetailerProduct]] = defaultdict(list)
        for listing in listings:
            listings_by_variant[listing.product_variant_id].append(listing)

        variant_keys = {variant.id: variant.variant_key for variant in variants}
        offer_map: dict[uuid.UUID, list[OfferInput]] = {}
        for variant in variants:
            offers: list[OfferInput] = []
            for listing in listings_by_variant.get(variant.id, []):
                listing_snapshots = snapshots_by_listing.get(listing.id, [])
                if not listing_snapshots:
                    offers.append(self._listing_without_snapshot(listing, variant.id))
                    continue
                offers.extend(
                    self._offer_from_snapshot(listing, snapshot, variant.id)
                    for snapshot in listing_snapshots
                )
            offer_map[variant.id] = offers

        comparison = self._engine.compare_product(
            product_id,
            offer_map,
            variant_keys=variant_keys,
        )
        logger.info(
            "price_comparison.product_completed",
            extra={
                "product_id": str(product_id),
                "variant_count": len(comparison.variants),
                "offer_count": sum(len(item.offers) for item in comparison.variants),
            },
        )
        return product_prices_read(comparison)

    def _listing_without_snapshot(
        self, listing: RetailerProduct, variant_id: uuid.UUID
    ) -> OfferInput:
        retailer = listing.retailer
        return OfferInput(
            offer_id=f"listing:{listing.id}",
            variant_id=variant_id,
            retailer_id=listing.retailer_id,
            retailer_slug=retailer.slug,
            retailer_name=retailer.name,
            retailer_product_id=listing.id,
            source_url=listing.url,
            source_type=None,
            observed_at=None,
            displayed_price=None,
            availability=AvailabilityStatus.UNKNOWN,
            observation_confidence=None,
        )

    def _offer_from_snapshot(
        self,
        listing: RetailerProduct,
        snapshot: PriceSnapshot,
        variant_id: uuid.UUID,
    ) -> OfferInput:
        retailer = listing.retailer
        seller_row = snapshot.seller
        seller = SellerSnapshot()
        if seller_row is not None:
            seller = SellerSnapshot(
                seller_id=seller_row.id,
                name=seller_row.name,
                is_first_party=seller_row.is_first_party,
                is_active=seller_row.is_active,
            )
        source_type: SourceType | None = snapshot.source_type
        return OfferInput(
            offer_id=str(snapshot.id),
            variant_id=variant_id,
            retailer_id=listing.retailer_id,
            retailer_slug=retailer.slug,
            retailer_name=retailer.name,
            retailer_product_id=listing.id,
            source_url=snapshot.source_url or listing.url,
            source_type=source_type,
            observed_at=snapshot.observed_at,
            currency=snapshot.currency,
            displayed_price=snapshot.displayed_price,
            mrp=snapshot.mrp,
            source_effective_price=snapshot.effective_price,
            delivery_fee=snapshot.delivery_fee,
            platform_fee=snapshot.platform_fee,
            availability=snapshot.availability,
            observation_confidence=snapshot.confidence,
            seller=seller,
            promotional_adjustments=tuple(_domain_adjustment(row) for row in snapshot.adjustments),
        )


def _domain_adjustment(row: PriceAdjustmentRow) -> PriceAdjustment:
    return PriceAdjustment(
        kind=row.kind,
        amount=row.amount,
        source=row.source,
        eligibility=row.eligibility,
        observed_at=row.observed_at,
        confidence=row.confidence,
    )
