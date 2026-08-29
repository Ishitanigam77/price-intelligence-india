"""Flipkart RetailerAdapter backed by the official Affiliate API.

Live calls happen only when environment credentials are present. Tests inject an HTTP client
and never contact Flipkart.
"""

import os
from collections.abc import Callable, Mapping
from datetime import datetime

import httpx

from app.domain.validation import slugify
from app.observability.metrics import MetricsSink
from app.retailer_adapters.base.errors import InvalidRetailerResponseError
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.models import (
    AvailabilityObservation,
    NormalizedProduct,
    PriceObservation,
    ProductSearchQuery,
    ProductSearchResult,
    RetailerProduct,
)
from app.retailer_adapters.base.rate_limit import RateLimiter
from app.retailer_adapters.flipkart import mapping
from app.retailer_adapters.flipkart.auth import load_credentials
from app.retailer_adapters.flipkart.client import FlipkartApiClient
from app.retailer_adapters.flipkart.config import DEFAULT_API_BASE_URL

_ATTRIBUTE_LABELS: dict[str, str] = {
    "color": "color",
    "Colour": "color",
    "storage": "storage",
    "size": "size",
    "displaySize": "display_size",
}


class FlipkartAdapter(RetailerAdapter):
    """Adapter for Flipkart via the official Affiliate Product APIs."""

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
        self._api_client: FlipkartApiClient | None = None

    def _client(self) -> FlipkartApiClient:
        if self._api_client is not None:
            return self._api_client
        credentials = load_credentials(self._env, retailer_id=self.retailer_id)
        http = self._http or httpx.AsyncClient()
        self._http = http
        self._api_client = FlipkartApiClient(
            credentials,
            http_client=http,
            timeout_seconds=self.config.attempt_timeout_seconds,
            api_base_url=self.config.options.get("api_base_url", DEFAULT_API_BASE_URL),
        )
        return self._api_client

    async def _search_products(self, query: ProductSearchQuery) -> ProductSearchResult:
        text = (query.text or "").strip() or (query.category or "").replace("-", " ")
        payload = await self._client().search(
            query=text, result_count=query.limit, operation="search_products"
        )
        retrieved_at = self._now()
        products: list[RetailerProduct] = []
        for entry in mapping.product_entries_from_search(payload, retailer_id=self.retailer_id):
            try:
                product = mapping.to_retailer_product(
                    entry, retailer_id=self.retailer_id, retrieved_at=retrieved_at
                )
            except InvalidRetailerResponseError:
                continue
            products.append(product)
            if len(products) >= query.limit:
                break
        return ProductSearchResult(
            retailer_id=self.retailer_id,
            query=query,
            products=tuple(products),
            retrieved_at=retrieved_at,
        )

    async def _get_product(self, retailer_sku: str) -> RetailerProduct:
        payload = await self._client().get_product(
            product_id=retailer_sku.strip(), operation="get_product"
        )
        return mapping.to_retailer_product(
            payload, retailer_id=self.retailer_id, retrieved_at=self._now()
        )

    async def _get_price(self, retailer_sku: str) -> PriceObservation:
        payload = await self._client().get_product(
            product_id=retailer_sku.strip(), operation="get_price"
        )
        return mapping.to_price_observation(
            payload, retailer_id=self.retailer_id, observed_at=self._now()
        )

    async def _get_availability(self, retailer_sku: str) -> AvailabilityObservation:
        payload = await self._client().get_product(
            product_id=retailer_sku.strip(), operation="get_availability"
        )
        return mapping.to_availability_observation(
            payload, retailer_id=self.retailer_id, observed_at=self._now()
        )

    async def _check_health(self) -> str | None:
        await self._client().search(query="ok", result_count=1, operation="health_check")
        return "Flipkart Affiliate search endpoint accepted credentials."

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


__all__ = ["FlipkartAdapter"]
