"""Amazon.in RetailerAdapter backed by the Associates Creators API.

Live calls happen only when environment credentials are present. Tests inject an HTTP client
and never contact Amazon.
"""

import os
from collections.abc import Callable, Mapping
from datetime import datetime

import httpx

from app.domain.validation import slugify
from app.observability.metrics import MetricsSink
from app.retailer_adapters.amazon_in import mapping
from app.retailer_adapters.amazon_in.auth import load_credentials
from app.retailer_adapters.amazon_in.client import AmazonInApiClient, search_index_for
from app.retailer_adapters.amazon_in.config import (
    DEFAULT_API_BASE_URL,
    DEFAULT_LANGUAGE,
    DEFAULT_MARKETPLACE,
    DEFAULT_TOKEN_URL,
)
from app.retailer_adapters.base.errors import InvalidRetailerResponseError, ProductNotFoundError
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
from app.retailer_adapters.base.rate_limit import RateLimiter

_ATTRIBUTE_LABELS: dict[str, str] = {
    "Colour": "color",
    "Color": "color",
    "Storage": "storage",
    "Size": "size",
}


class AmazonInAdapter(RetailerAdapter):
    """Adapter for Amazon.in via the official Associates Creators API."""

    def __init__(
        self,
        config,
        *,
        metrics_sink: MetricsSink | None = None,
        rate_limiter: RateLimiter | None = None,
        clock: Callable[[], datetime] | None = None,
        env: Mapping[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(config, metrics_sink=metrics_sink, rate_limiter=rate_limiter, clock=clock)
        self._env: Mapping[str, str] = os.environ if env is None else env
        self._http = http_client
        self._api_client: AmazonInApiClient | None = None

    def _client(self) -> AmazonInApiClient:
        if self._api_client is not None:
            return self._api_client
        credentials = load_credentials(self._env, retailer_id=self.retailer_id)
        http = self._http or httpx.AsyncClient()
        self._http = http
        options = self.config.options
        self._api_client = AmazonInApiClient(
            credentials,
            http_client=http,
            timeout_seconds=self.config.attempt_timeout_seconds,
            api_base_url=options.get("api_base_url", DEFAULT_API_BASE_URL),
            token_url=options.get("oauth_endpoint", DEFAULT_TOKEN_URL),
            marketplace=options.get("marketplace", DEFAULT_MARKETPLACE),
            language=options.get("language", DEFAULT_LANGUAGE),
        )
        return self._api_client

    async def _search_products(self, query: ProductSearchQuery) -> ProductSearchResult:
        keywords = (query.text or "").strip() or (query.category or "").replace("-", " ")
        payload = await self._client().search_items(
            keywords=keywords,
            search_index=search_index_for(query.category),
            item_count=query.limit,
            operation="search_products",
        )
        retrieved_at = self._now()
        products: list[RetailerProduct] = []
        for item in mapping.items_from_payload(payload, retailer_id=self.retailer_id):
            try:
                products.append(
                    mapping.to_retailer_product(
                        item, retailer_id=self.retailer_id, retrieved_at=retrieved_at
                    )
                )
            except InvalidRetailerResponseError:
                # Skip individual unmappable hits rather than failing the whole search.
                continue
            if len(products) >= query.limit:
                break
        return ProductSearchResult(
            retailer_id=self.retailer_id,
            query=query,
            products=tuple(products),
            retrieved_at=retrieved_at,
        )

    async def _get_product(self, retailer_sku: str) -> RetailerProduct:
        item = await self._require_item(retailer_sku, operation="get_product")
        return mapping.to_retailer_product(
            item, retailer_id=self.retailer_id, retrieved_at=self._now()
        )

    async def _get_price(self, retailer_sku: str) -> PriceObservation:
        item = await self._require_item(retailer_sku, operation="get_price")
        return mapping.to_price_observation(
            item, retailer_id=self.retailer_id, observed_at=self._now()
        )

    async def _get_availability(self, retailer_sku: str) -> AvailabilityObservation:
        item = await self._require_item(retailer_sku, operation="get_availability")
        return mapping.to_availability_observation(
            item, retailer_id=self.retailer_id, observed_at=self._now()
        )

    async def _get_product_identifiers(
        self, retailer_sku: str
    ) -> tuple[ProductIdentifierValue, ...]:
        item = await self._require_item(retailer_sku, operation="get_product_identifiers")
        return mapping.to_identifiers(item)

    async def _check_health(self) -> str | None:
        await self._client().ensure_access_token(operation="health_check")
        return "Amazon.in Creators API token endpoint accepted credentials."

    def normalize_product(self, product: RetailerProduct) -> NormalizedProduct:
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

    async def _require_item(self, retailer_sku: str, *, operation: str) -> dict:
        sku = retailer_sku.strip()
        payload = await self._client().get_items(asins=(sku,), operation=operation)
        item = mapping.find_item(payload, asin=sku, retailer_id=self.retailer_id)
        if item is None:
            raise ProductNotFoundError(
                "No listing exists for the requested SKU.",
                retailer_id=self.retailer_id,
                operation=operation,
            )
        return item


__all__ = ["AmazonInAdapter"]
