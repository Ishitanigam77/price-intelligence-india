"""Fixture-backed tests for the Amazon.in Creators API adapter.

No live Amazon calls. Payloads are invented fixtures in the documented API shape.
"""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest

from app.domain.enums import AvailabilityStatus, ProductIdentifierType, SourceType
from app.retailer_adapters.amazon_in import create_adapter
from app.retailer_adapters.amazon_in.config import RETAILER_ID
from app.retailer_adapters.amazon_in.fixtures import (
    FIXTURE_ASIN_IN_STOCK,
    FIXTURE_ASIN_MISSING,
    FIXTURE_ASIN_OUT_OF_STOCK,
    GET_ITEMS_IN_STOCK_RESPONSE,
    GET_ITEMS_NOT_FOUND_RESPONSE,
    GET_ITEMS_OUT_OF_STOCK_RESPONSE,
    MALFORMED_ITEM_RESPONSE,
    SEARCH_RESPONSE,
    TOKEN_RESPONSE,
)
from app.retailer_adapters.base.errors import (
    AdapterMisconfiguredError,
    AdapterTimeoutError,
    AdapterUnavailableError,
    InvalidRetailerResponseError,
    ProductNotFoundError,
    RateLimitExceededError,
)
from app.retailer_adapters.base.models import ProductSearchQuery
from tests.unit.retailer_adapters.http_helpers import RecordingHandler, mock_client

TEST_ENV = {
    "RETAILER_AMAZON_IN_CREDENTIAL_ID": "test-credential-id",
    "RETAILER_AMAZON_IN_CREDENTIAL_SECRET": "test-credential-secret",
    "RETAILER_AMAZON_IN_PARTNER_TAG": "example-21",
    "RETAILER_AMAZON_IN_MAX_ATTEMPTS": "1",
}

SECRET = TEST_ENV["RETAILER_AMAZON_IN_CREDENTIAL_SECRET"]


def _get_items_router(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content.decode("utf-8")) if request.content else {}
    ids = [str(item).upper() for item in body.get("itemIds", [])]
    if FIXTURE_ASIN_MISSING in ids:
        return httpx.Response(200, json=GET_ITEMS_NOT_FOUND_RESPONSE)
    if FIXTURE_ASIN_OUT_OF_STOCK in ids:
        return httpx.Response(200, json=GET_ITEMS_OUT_OF_STOCK_RESPONSE)
    return httpx.Response(200, json=GET_ITEMS_IN_STOCK_RESPONSE)


def _standard_handler(**overrides: object) -> RecordingHandler:
    routes: dict = {
        "/auth/o2/token": TOKEN_RESPONSE,
        "/catalog/v1/searchItems": SEARCH_RESPONSE,
        "/catalog/v1/getItems": _get_items_router,
    }
    routes.update(overrides)
    return RecordingHandler(routes)


def _adapter(handler: RecordingHandler | None = None):
    recorded = handler or _standard_handler()
    adapter = create_adapter(env=TEST_ENV, http_client=mock_client(recorded))
    return adapter, recorded


class TestAmazonInAuthAndRequests:
    def test_adapter_constructs_without_credentials(self) -> None:
        handler = _standard_handler()
        adapter = create_adapter(env={}, http_client=mock_client(handler))
        assert adapter.retailer_id == RETAILER_ID
        assert handler.requests == []

    async def test_health_without_credentials_is_unhealthy(self) -> None:
        handler = _standard_handler()
        adapter = create_adapter(env={}, http_client=mock_client(handler))
        result = await adapter.health_check()
        assert result.is_healthy is False
        assert result.error_code is not None
        assert result.error_code.value == "adapter_misconfigured"
        assert handler.requests == []
        assert SECRET not in (result.detail or "")

    async def test_token_and_search_request_construction_does_not_expose_secret_in_catalog_call(
        self,
    ) -> None:
        adapter, recorded = _adapter()
        await adapter.search_products(ProductSearchQuery(text="fictional orchard"))
        assert len(recorded.requests) >= 2
        token_req = recorded.requests[0]
        search_req = next(req for req in recorded.requests if "searchItems" in str(req.url))
        token_body = json.loads(token_req.content.decode("utf-8"))
        assert token_body["client_id"] == "test-credential-id"
        assert token_body["grant_type"] == "client_credentials"
        search_body = json.loads(search_req.content.decode("utf-8"))
        assert search_body["partnerTag"] == "example-21"
        assert search_body["marketplace"] == "www.amazon.in"
        assert search_body["keywords"] == "fictional orchard"
        assert SECRET not in json.dumps(search_body)
        assert SECRET not in search_req.headers.get("Authorization", "")
        assert search_req.headers["Authorization"] == "Bearer test-access-token-not-a-secret"
        assert search_req.headers["x-marketplace"] == "www.amazon.in"

    async def test_credentials_are_not_copied_into_config_options(self) -> None:
        adapter, _recorded = _adapter()
        assert "credential" not in " ".join(adapter.config.options).casefold()
        assert SECRET not in adapter.config.options.values()


class TestAmazonInSearchLookupPriceAvailability:
    async def test_product_search(self) -> None:
        adapter, _recorded = _adapter()
        result = await adapter.search_products(ProductSearchQuery(text="aurora", limit=10))
        assert result.retailer_id == RETAILER_ID
        assert len(result.products) == 2
        first = result.products[0]
        assert first.retailer_sku == FIXTURE_ASIN_IN_STOCK
        assert first.price is not None
        assert first.price.displayed_price == Decimal("59999.00")
        assert first.price.mrp == Decimal("69999.00")
        assert first.price.source_type is SourceType.AFFILIATE_FEED
        assert first.price.effective_price is None
        assert first.availability is not None
        assert first.availability.status is AvailabilityStatus.IN_STOCK

    async def test_search_uses_category_as_search_index_and_keywords_when_text_missing(
        self,
    ) -> None:
        adapter, recorded = _adapter()
        await adapter.search_products(ProductSearchQuery(category="mobiles"))
        search_req = next(req for req in recorded.requests if "searchItems" in str(req.url))
        body = json.loads(search_req.content.decode("utf-8"))
        assert body["searchIndex"] == "Electronics"
        assert body["keywords"] == "mobiles"
        assert body["itemCount"] == 10  # API maximum

    async def test_product_lookup(self) -> None:
        adapter, _recorded = _adapter()
        product = await adapter.get_product(FIXTURE_ASIN_IN_STOCK)
        assert product.title.startswith("Fictional Orchard Aurora")
        assert product.brand_name == "Fictional Orchard"
        assert "Mobiles" in product.category_path
        assert product.seller is not None
        assert product.seller.is_first_party is True

    async def test_product_lookup_missing_sku(self) -> None:
        adapter, _recorded = _adapter()
        with pytest.raises(ProductNotFoundError):
            await adapter.get_product(FIXTURE_ASIN_MISSING)

    async def test_price_retrieval(self) -> None:
        adapter, _recorded = _adapter()
        observation = await adapter.get_price(FIXTURE_ASIN_IN_STOCK)
        assert observation.displayed_price == Decimal("59999.00")
        assert observation.mrp == Decimal("69999.00")
        assert observation.currency == "INR"
        assert observation.availability is AvailabilityStatus.IN_STOCK
        assert observation.source_url is not None
        assert observation.confidence.value == "high"

    async def test_availability_in_and_out_of_stock(self) -> None:
        adapter, _recorded = _adapter()
        in_stock = await adapter.get_availability(FIXTURE_ASIN_IN_STOCK)
        out = await adapter.get_availability(FIXTURE_ASIN_OUT_OF_STOCK)
        assert in_stock.status is AvailabilityStatus.IN_STOCK
        assert out.status is AvailabilityStatus.OUT_OF_STOCK
        assert out.seller is not None
        assert out.seller.is_first_party is False

    async def test_identifiers(self) -> None:
        adapter, _recorded = _adapter()
        identifiers = await adapter.get_product_identifiers(FIXTURE_ASIN_IN_STOCK)
        types = {item.identifier_type for item in identifiers}
        values = {item.value for item in identifiers}
        assert ProductIdentifierType.EAN in types
        assert "8900000001001" in values
        assert ProductIdentifierType.MPN in types

    async def test_normalization_maps_colour_to_color(self) -> None:
        adapter, _recorded = _adapter()
        product = await adapter.get_product(FIXTURE_ASIN_IN_STOCK)
        normalized = adapter.normalize_product(product)
        assert normalized.variant_attributes["color"] == "midnight"
        assert normalized.variant_attributes["storage"] == "128 gb"
        assert normalized.brand_slug == "fictional-orchard"
        assert normalized.category_slug == "mobiles"
        assert "  " not in normalized.normalized_title

    async def test_health_with_credentials(self) -> None:
        adapter, recorded = _adapter()
        result = await adapter.health_check()
        assert result.is_healthy
        assert any("/token" in str(req.url) for req in recorded.requests)


class TestAmazonInErrors:
    async def test_timeout(self) -> None:
        def hang(_request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out")

        handler = _standard_handler(**{"/auth/o2/token": hang})
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(AdapterTimeoutError):
            await adapter.search_products(ProductSearchQuery(text="aurora"))

    async def test_connection_failure(self) -> None:
        def down(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        handler = _standard_handler(**{"/auth/o2/token": down})
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(AdapterUnavailableError):
            await adapter.search_products(ProductSearchQuery(text="aurora"))

    async def test_http_429_is_rate_limited(self) -> None:
        handler = _standard_handler(
            **{
                "/catalog/v1/searchItems": httpx.Response(
                    429, headers={"Retry-After": "2"}, json={"message": "TooManyRequests"}
                )
            }
        )
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(RateLimitExceededError) as exc:
            await adapter.search_products(ProductSearchQuery(text="aurora"))
        assert exc.value.retry_after_seconds == 2.0

    async def test_malformed_json(self) -> None:
        handler = _standard_handler(**{"/catalog/v1/getItems": b"not-json{"})
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(InvalidRetailerResponseError):
            await adapter.get_product(FIXTURE_ASIN_IN_STOCK)

    async def test_malformed_item_without_title(self) -> None:
        handler = _standard_handler(**{"/catalog/v1/getItems": MALFORMED_ITEM_RESPONSE})
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(InvalidRetailerResponseError):
            await adapter.get_product(FIXTURE_ASIN_IN_STOCK)

    async def test_unauthorized_token_endpoint(self) -> None:
        handler = _standard_handler(
            **{"/auth/o2/token": httpx.Response(401, json={"error": "invalid_client"})}
        )
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(AdapterMisconfiguredError):
            await adapter.search_products(ProductSearchQuery(text="aurora"))
