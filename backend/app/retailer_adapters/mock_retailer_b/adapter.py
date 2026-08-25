"""MockRetailerB: a mock marketplace adapter used to exercise the framework.

Reads deterministic fixture rows; makes no network call, has no endpoint, and needs no
credential. Differences from the other mocks that the framework has to absorb: an affiliate-feed
source type, string amounts in rupees, third-party sellers, MPN-only identifiers, MEDIUM
confidence, a source-provided effective price, a delivery fee, laptops as a category, and **no**
standalone availability operation.
"""

from app.domain.validation import slugify
from app.retailer_adapters.base.errors import ProductNotFoundError
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.models import (
    NormalizedProduct,
    PriceObservation,
    ProductIdentifierValue,
    ProductSearchQuery,
    ProductSearchResult,
    RetailerProduct,
)
from app.retailer_adapters.mock_retailer_b import fixtures, mapping


class MockRetailerBAdapter(RetailerAdapter):
    """Adapter for the fictional marketplace "Fictional Mock Bazaar B"."""

    def _row(self, retailer_sku: str, *, operation: str) -> dict:
        try:
            return fixtures.ROWS_BY_ITEM_ID[retailer_sku]
        except KeyError as exc:
            raise ProductNotFoundError(
                "No feed row exists for the requested item id.",
                retailer_id=self.retailer_id,
                operation=operation,
            ) from exc

    async def _search_products(self, query: ProductSearchQuery) -> ProductSearchResult:
        retrieved_at = self._now()
        text = (query.text or "").strip().lower()
        matches = [
            row
            for row in fixtures.ROWS
            if (not text or text in row["name"].lower())
            and (query.category is None or row["cat_slug"] == query.category)
        ]
        return ProductSearchResult(
            retailer_id=self.retailer_id,
            query=query,
            products=tuple(
                mapping.to_retailer_product(
                    row, retailer_id=self.retailer_id, retrieved_at=retrieved_at
                )
                for row in matches[: query.limit]
            ),
            retrieved_at=retrieved_at,
        )

    async def _get_product(self, retailer_sku: str) -> RetailerProduct:
        return mapping.to_retailer_product(
            self._row(retailer_sku, operation="get_product"),
            retailer_id=self.retailer_id,
            retrieved_at=self._now(),
        )

    async def _get_price(self, retailer_sku: str) -> PriceObservation:
        return mapping.to_price_observation(
            self._row(retailer_sku, operation="get_price"),
            retailer_id=self.retailer_id,
            observed_at=self._now(),
        )

    async def _get_product_identifiers(
        self, retailer_sku: str
    ) -> tuple[ProductIdentifierValue, ...]:
        return mapping.to_identifiers(self._row(retailer_sku, operation="get_product_identifiers"))

    async def _check_health(self) -> str | None:
        return f"{len(fixtures.ROWS)} fixture feed rows available."

    def normalize_product(self, product: RetailerProduct) -> NormalizedProduct:
        """Map this retailer's vocabulary onto the retailer-agnostic shape.

        This feed already labels specs in lowercase snake-ish form, so normalization is mostly
        the shared Phase 1 attribute normalization plus a title tidy-up.
        """
        return NormalizedProduct(
            retailer_id=product.retailer_id,
            retailer_sku=product.retailer_sku,
            normalized_title=" ".join(product.title.split()),
            brand_name=product.brand_name,
            brand_slug=slugify(product.brand_name) if product.brand_name else None,
            category_slug=slugify(product.category_path[-1]) if product.category_path else None,
            variant_attributes=dict(product.attributes),
            identifiers=product.identifiers,
            source_url=product.url,
            source_type=product.source_type,
            normalized_at=self._now(),
        )


__all__ = ["MockRetailerBAdapter"]
