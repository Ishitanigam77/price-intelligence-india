"""Per-retailer collection job implementations.

Each handler talks only to the `RetailerAdapter` contract (plus sale-event detection on stored
observations). No handler names a mock or real retailer. Per-SKU failures are captured and
returned so one bad listing cannot abort the rest of that retailer's work; the orchestrator
still isolates retailers from each other.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.collectors.errors import CollectionFailure
from app.collectors.ingest import CollectionIngestor
from app.collectors.mapping import collection_failure_from_exception
from app.retailer_adapters.base.config import AdapterOperation
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.models import ProductSearchQuery
from app.sales.detection import SaleEventDetector


@dataclass
class RetailerJobOutcome:
    """Counts produced by one retailer's job body (before status mapping)."""

    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    item_errors: list[CollectionFailure] = field(default_factory=list)

    @property
    def attempted(self) -> int:
        return self.succeeded + self.failed


async def run_product_search(
    adapter: RetailerAdapter,
    ingestor: CollectionIngestor,
    *,
    query_text: str,
    limit: int,
    category: str | None,
) -> RetailerJobOutcome:
    result = await adapter.search_products(
        ProductSearchQuery(text=query_text, category=category, limit=limit)
    )
    persisted = ingestor.ingest_search_result(adapter, result)
    return RetailerJobOutcome(
        succeeded=persisted, skipped=max(0, len(result.products) - persisted)
    )


async def run_product_refresh(
    adapter: RetailerAdapter,
    ingestor: CollectionIngestor,
    *,
    skus: Sequence[str] | None = None,
) -> RetailerJobOutcome:
    outcome = RetailerJobOutcome()
    for sku in _sku_targets(adapter.retailer_id, ingestor, skus):
        try:
            product = await adapter.get_product(sku)
            if ingestor.ingest_adapter_product(adapter, product) is not None:
                outcome.succeeded += 1
            else:
                outcome.skipped += 1
        except Exception as exc:
            outcome.failed += 1
            outcome.item_errors.append(
                collection_failure_from_exception(
                    exc,
                    retailer_id=adapter.retailer_id,
                    operation=AdapterOperation.GET_PRODUCT.value,
                    operation_target=sku,
                )
            )
    return outcome


async def run_price_refresh(
    adapter: RetailerAdapter,
    ingestor: CollectionIngestor,
    *,
    skus: Sequence[str] | None = None,
) -> RetailerJobOutcome:
    outcome = RetailerJobOutcome()
    for listing in _listings(adapter.retailer_id, ingestor, skus):
        sku = listing.retailer_sku
        try:
            observation = await adapter.get_price(sku)
            snapshot = ingestor.ingest_price(listing, observation)
            if snapshot is None:
                outcome.skipped += 1
            else:
                outcome.succeeded += 1
        except Exception as exc:
            outcome.failed += 1
            outcome.item_errors.append(
                collection_failure_from_exception(
                    exc,
                    retailer_id=adapter.retailer_id,
                    operation=AdapterOperation.GET_PRICE.value,
                    operation_target=sku,
                )
            )
    return outcome


async def run_availability_refresh(
    adapter: RetailerAdapter,
    ingestor: CollectionIngestor,
    *,
    skus: Sequence[str] | None = None,
) -> RetailerJobOutcome:
    outcome = RetailerJobOutcome()
    for listing in _listings(adapter.retailer_id, ingestor, skus):
        sku = listing.retailer_sku
        try:
            availability = await adapter.get_availability(sku)
            snapshot = ingestor.ingest_availability(listing, availability)
            if snapshot is None and adapter.supports(AdapterOperation.GET_PRICE):
                observation = await adapter.get_price(sku)
                snapshot = ingestor.ingest_price(listing, observation)
            if snapshot is None:
                outcome.skipped += 1
            else:
                outcome.succeeded += 1
        except Exception as exc:
            outcome.failed += 1
            outcome.item_errors.append(
                collection_failure_from_exception(
                    exc,
                    retailer_id=adapter.retailer_id,
                    operation=AdapterOperation.GET_AVAILABILITY.value,
                    operation_target=sku,
                )
            )
    return outcome


async def run_sale_event_refresh(
    adapter: RetailerAdapter,
    ingestor: CollectionIngestor,
    detector: SaleEventDetector,
) -> RetailerJobOutcome:
    points = ingestor.sale_price_points_for_retailer(adapter.retailer_id)
    windows = detector.detect(points)
    created = ingestor.ingest_detected_windows(windows)
    return RetailerJobOutcome(succeeded=created, skipped=max(0, len(windows) - created))


def _listings(retailer_id: str, ingestor: CollectionIngestor, skus: Sequence[str] | None):
    listings = ingestor.listings_for_retailer(retailer_id)
    if skus is None:
        return listings
    wanted = {sku for sku in skus}
    return [listing for listing in listings if listing.retailer_sku in wanted]


def _sku_targets(
    retailer_id: str, ingestor: CollectionIngestor, skus: Sequence[str] | None
) -> tuple[str, ...]:
    if skus is not None:
        return tuple(skus)
    return tuple(listing.retailer_sku for listing in ingestor.listings_for_retailer(retailer_id))
