"""Persist collection results using existing uniqueness rules. Never invent retailer data."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import PriceSnapshot, Product, ProductVariant, SaleEvent
from app.domain.enums import SaleEventSource
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.pricing.history_models import HistoricalObservationPoint
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.retailer_product_repository import RetailerProductRepository
from app.repositories.retailer_repository import RetailerRepository
from app.repositories.sale_event_repository import SaleEventRepository
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.models import (
    AvailabilityObservation,
    PriceObservation,
    ProductSearchResult,
)
from app.retailer_adapters.base.models import RetailerProduct as AdapterRetailerProduct
from app.retailer_adapters.base.registry import RetailerRegistry
from app.sales.models import DetectedSaleWindow, SalePricePoint
from app.services.product_discovery_service import ProductDiscoveryService


class CollectionIngestor:
    """Hands adapter payloads and calculated sale windows to existing persistence."""

    def __init__(
        self,
        session: Session,
        registry: RetailerRegistry,
        *,
        metrics_sink: MetricsSink | None = None,
    ) -> None:
        self._session = session
        self._discovery = ProductDiscoveryService(
            session, registry, metrics_sink=metrics_sink or NullMetricsSink()
        )
        self._listings = RetailerProductRepository(session)
        self._snapshots = PriceSnapshotRepository(session)
        self._retailers = RetailerRepository(session)
        self._events = SaleEventRepository(session)

    def ingest_search_result(self, adapter: RetailerAdapter, result: ProductSearchResult) -> int:
        persisted = 0
        for product in result.products:
            if self.ingest_adapter_product(adapter, product) is not None:
                persisted += 1
        return persisted

    def ingest_adapter_product(
        self, adapter: RetailerAdapter, product: AdapterRetailerProduct
    ) -> object | None:
        normalized = adapter.normalize_product(product)
        return self._discovery.persist_discovered_listing(product, normalized)

    def ingest_price(self, listing, price: PriceObservation) -> PriceSnapshot | None:
        return self._discovery.persist_price_observation(listing, price.seller, price)

    def ingest_availability(
        self, listing, availability: AvailabilityObservation
    ) -> PriceSnapshot | None:
        return self._discovery.persist_availability_observation(listing, availability)

    def listings_for_retailer(self, retailer_slug: str) -> list:
        return self._listings.list_active_for_retailer_slug(retailer_slug)

    def persisted_retailer(self, retailer_slug: str):
        return self._retailers.get_by_slug(retailer_slug)

    def sale_price_points_for_retailer(self, retailer_slug: str) -> list[SalePricePoint]:
        retailer = self._retailers.get_by_slug(retailer_slug)
        if retailer is None:
            return []
        snapshots = self._snapshots.history_for_retailer(retailer.id)
        points: list[SalePricePoint] = []
        for snapshot in snapshots:
            listing = snapshot.retailer_product
            variant: ProductVariant = listing.product_variant
            product: Product = variant.product
            points.append(
                SalePricePoint(
                    observation=HistoricalObservationPoint(
                        snapshot_id=snapshot.id,
                        product_id=product.id,
                        product_variant_id=variant.id,
                        variant_key=variant.variant_key,
                        retailer_id=listing.retailer_id,
                        retailer_slug=listing.retailer.slug,
                        retailer_name=listing.retailer.name,
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
            )
        return points

    def ingest_detected_windows(self, windows: tuple[DetectedSaleWindow, ...]) -> int:
        created = 0
        for window in windows:
            existing = self._events.get_equivalent_inferred_window(
                name=window.name,
                start_date=window.start_date,
                end_date=window.end_date,
                event_type=window.event_type,
                source=SaleEventSource.OBSERVED_PRICE_INFERENCE,
                retailer_id=window.retailer_id,
                category_id=window.category_id,
                brand_id=window.brand_id,
            )
            if existing is not None:
                continue
            self._events.add(
                SaleEvent(
                    name=window.name,
                    retailer_id=window.retailer_id,
                    category_id=window.category_id,
                    brand_id=window.brand_id,
                    start_date=window.start_date,
                    end_date=window.end_date,
                    event_type=window.event_type,
                    source=SaleEventSource.OBSERVED_PRICE_INFERENCE,
                    source_ref=window.source_ref,
                    confidence=window.confidence,
                )
            )
            created += 1
        return created

    def newest_observation_age_seconds(self, retailer_slug: str, *, now) -> float | None:
        retailer = self._retailers.get_by_slug(retailer_slug)
        if retailer is None:
            return None
        snapshots = self._snapshots.history_for_retailer(retailer.id)
        if not snapshots:
            return None
        newest = max(snapshot.observed_at for snapshot in snapshots)
        return (now - newest).total_seconds()
