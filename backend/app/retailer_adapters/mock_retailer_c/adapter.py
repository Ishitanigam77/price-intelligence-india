"""MockRetailerC: a mock first-party-store adapter used to exercise the framework.

Reads deterministic fixture entries; makes no network call, has no endpoint, and needs no
credential. Differences the framework has to absorb: a product-feed source type, LOW confidence
(nightly feed), a first-party seller, a nested variant block, a platform fee, no product
identifiers at all, and categories that do not overlap the other mocks' phone catalogue.
"""

from app.domain.validation import slugify
from app.retailer_adapters.base.errors import ProductNotFoundError
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.models import (
    AvailabilityObservation,
    NormalizedProduct,
    PriceObservation,
    ProductSearchQuery,
    ProductSearchResult,
    RetailerProduct,
)
from app.retailer_adapters.mock_retailer_c import fixtures, mapping


class MockRetailerCAdapter(RetailerAdapter):
    """Adapter for the fictional first-party store "Fictional Mock Depot C"."""

    def _entry(self, retailer_sku: str, *, operation: str) -> dict:
        try:
            return fixtures.ENTRIES_BY_ITEM_CODE[retailer_sku]
        except KeyError as exc:
            raise ProductNotFoundError(
                "No feed entry exists for the requested item code.",
                retailer_id=self.retailer_id,
                operation=operation,
            ) from exc

    async def _search_products(self, query: ProductSearchQuery) -> ProductSearchResult:
        retrieved_at = self._now()
        text = (query.text or "").strip().lower()
        matches = [
            entry
            for entry in fixtures.ENTRIES
            if (not text or text in entry["title"].lower())
            and (query.category is None or entry["department_slug"] == query.category)
        ]
        return ProductSearchResult(
            retailer_id=self.retailer_id,
            query=query,
            products=tuple(
                mapping.to_retailer_product(
                    entry, retailer_id=self.retailer_id, retrieved_at=retrieved_at
                )
                for entry in matches[: query.limit]
            ),
            retrieved_at=retrieved_at,
        )

    async def _get_product(self, retailer_sku: str) -> RetailerProduct:
        return mapping.to_retailer_product(
            self._entry(retailer_sku, operation="get_product"),
            retailer_id=self.retailer_id,
            retrieved_at=self._now(),
        )

    async def _get_price(self, retailer_sku: str) -> PriceObservation:
        return mapping.to_price_observation(
            self._entry(retailer_sku, operation="get_price"),
            retailer_id=self.retailer_id,
            observed_at=self._now(),
        )

    async def _get_availability(self, retailer_sku: str) -> AvailabilityObservation:
        return mapping.to_availability_observation(
            self._entry(retailer_sku, operation="get_availability"),
            retailer_id=self.retailer_id,
            observed_at=self._now(),
        )

    async def _check_health(self) -> str | None:
        return f"Feed snapshot {fixtures.FEED_GENERATED_AT} with {len(fixtures.ENTRIES)} entries."

    def normalize_product(self, product: RetailerProduct) -> NormalizedProduct:
        """Map this retailer's vocabulary onto the retailer-agnostic shape.

        This retailer's department name doubles as its only category signal, so it becomes the
        category slug; mapping it onto the platform's own taxonomy is a later-phase concern.
        """
        return NormalizedProduct(
            retailer_id=product.retailer_id,
            retailer_sku=product.retailer_sku,
            normalized_title=" ".join(product.title.split()),
            brand_name=product.brand_name,
            brand_slug=slugify(product.brand_name) if product.brand_name else None,
            category_slug=slugify(product.category_path[0]) if product.category_path else None,
            variant_attributes=dict(product.attributes),
            identifiers=product.identifiers,
            source_url=product.url,
            source_type=product.source_type,
            normalized_at=self._now(),
        )


__all__ = ["MockRetailerCAdapter"]
