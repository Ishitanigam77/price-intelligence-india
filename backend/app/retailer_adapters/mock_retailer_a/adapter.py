"""MockRetailerA: a mock adapter used to exercise the framework end to end.

It reads deterministic fixtures instead of making any network call — there is no real retailer,
no endpoint, and no credential involved. Its purpose is to prove that the framework's contract,
registry, error handling, and normalization work against a realistic-shaped integration, and to
give the core domain something to consume before any real retailer is onboarded.

Characteristics that distinguish it from the other mocks: an official-API source type, integer
paise amounts, first-party fulfilment, GTIN identifiers, HIGH confidence, and support for all
five optional operations.
"""

from app.domain.validation import slugify
from app.retailer_adapters.base.errors import ProductNotFoundError
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.models import (
    AvailabilityObservation,
    NormalizedProduct,
    PriceObservation,
    ProductIdentifierValue,
    ProductSearchQuery,
    ProductSearchResult,
    RetailerProduct,
)
from app.retailer_adapters.mock_retailer_a import fixtures, mapping

#: This retailer labels its attributes in its own way ("Colour", "Form Factor"); reconciling
#: those labels is exactly the kind of quirk that belongs inside an adapter.
_ATTRIBUTE_LABELS: dict[str, str] = {
    "Storage": "storage",
    "Colour": "color",
    "Form Factor": "form_factor",
}


class MockRetailerAAdapter(RetailerAdapter):
    """Adapter for the fictional retailer "Fictional Mock Mart A"."""

    def _listing(self, retailer_sku: str, *, operation: str) -> dict:
        try:
            return fixtures.LISTINGS_BY_SKU[retailer_sku]
        except KeyError as exc:
            raise ProductNotFoundError(
                "No listing exists for the requested SKU.",
                retailer_id=self.retailer_id,
                operation=operation,
            ) from exc

    async def _search_products(self, query: ProductSearchQuery) -> ProductSearchResult:
        retrieved_at = self._now()
        text = (query.text or "").strip().lower()
        matches = [
            listing
            for listing in fixtures.LISTINGS
            if (not text or text in listing["productName"].lower())
            and (query.category is None or listing["categorySlug"] == query.category)
        ]
        return ProductSearchResult(
            retailer_id=self.retailer_id,
            query=query,
            products=tuple(
                mapping.to_retailer_product(
                    listing, retailer_id=self.retailer_id, retrieved_at=retrieved_at
                )
                for listing in matches[: query.limit]
            ),
            retrieved_at=retrieved_at,
        )

    async def _get_product(self, retailer_sku: str) -> RetailerProduct:
        return mapping.to_retailer_product(
            self._listing(retailer_sku, operation="get_product"),
            retailer_id=self.retailer_id,
            retrieved_at=self._now(),
        )

    async def _get_price(self, retailer_sku: str) -> PriceObservation:
        return mapping.to_price_observation(
            self._listing(retailer_sku, operation="get_price"),
            retailer_id=self.retailer_id,
            observed_at=self._now(),
        )

    async def _get_availability(self, retailer_sku: str) -> AvailabilityObservation:
        return mapping.to_availability_observation(
            self._listing(retailer_sku, operation="get_availability"),
            retailer_id=self.retailer_id,
            observed_at=self._now(),
        )

    async def _get_product_identifiers(
        self, retailer_sku: str
    ) -> tuple[ProductIdentifierValue, ...]:
        return mapping.to_identifiers(
            self._listing(retailer_sku, operation="get_product_identifiers")
        )

    async def _check_health(self) -> str | None:
        return f"{len(fixtures.LISTINGS)} fixture listings available."

    def normalize_product(self, product: RetailerProduct) -> NormalizedProduct:
        """Map this retailer's vocabulary onto the retailer-agnostic shape."""
        variant_attributes = {
            _ATTRIBUTE_LABELS.get(label, slugify(label).replace("-", "_")): value
            for label, value in product.attributes.items()
        }
        category_slug = slugify(product.category_path[-1]) if product.category_path else None
        return NormalizedProduct(
            retailer_id=product.retailer_id,
            retailer_sku=product.retailer_sku,
            normalized_title=" ".join(product.title.split()),
            brand_name=product.brand_name,
            brand_slug=slugify(product.brand_name) if product.brand_name else None,
            category_slug=category_slug,
            variant_attributes=variant_attributes,
            identifiers=product.identifiers,
            source_url=product.url,
            source_type=product.source_type,
            normalized_at=self._now(),
        )


__all__ = ["MockRetailerAAdapter"]
