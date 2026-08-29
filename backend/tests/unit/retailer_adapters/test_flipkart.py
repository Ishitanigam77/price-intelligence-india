"""Fixture-backed tests for the Flipkart Affiliate API adapter.

No live Flipkart calls. Payloads are invented fixtures in the documented API shape.
"""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.domain.enums import AvailabilityStatus, SourceType
from app.retailer_adapters.base.config import AdapterOperation
from app.retailer_adapters.base.errors import (
    AdapterMisconfiguredError,
    AdapterTimeoutError,
    AdapterUnavailableError,
    InvalidRetailerResponseError,
    ProductNotFoundError,
    RateLimitExceededError,
    UnsupportedOperationError,
)
from app.retailer_adapters.base.models import ProductSearchQuery
from app.retailer_adapters.flipkart import create_adapter
from app.retailer_adapters.flipkart.config import RETAILER_ID
from app.retailer_adapters.flipkart.fixtures import (
    EMPTY_SEARCH_RESPONSE,
    FIXTURE_PID_IN_STOCK,
    FIXTURE_PID_MISSING,
    FIXTURE_PID_OUT_OF_STOCK,
    MALFORMED_PRODUCT_RESPONSE,
    PRODUCT_IN_STOCK_RESPONSE,
    PRODUCT_OUT_OF_STOCK_RESPONSE,
    SEARCH_RESPONSE,
)
from tests.unit.retailer_adapters.http_helpers import RecordingHandler, mock_client

TEST_ENV = {
    "RETAILER_FLIPKART_AFFILIATE_ID": "test-affiliate-id",
    "RETAILER_FLIPKART_AFFILIATE_TOKEN": "test-affiliate-token",
    "RETAILER_FLIPKART_MAX_ATTEMPTS": "1",
}

TOKEN = TEST_ENV["RETAILER_FLIPKART_AFFILIATE_TOKEN"]


def _product_router(request: httpx.Request) -> httpx.Response:
    product_id = parse_qs(urlparse(str(request.url)).query).get("id", [""])[0]
    if product_id == FIXTURE_PID_MISSING:
        return httpx.Response(404, json={"error": "not found"})
    if product_id == FIXTURE_PID_OUT_OF_STOCK:
        return httpx.Response(200, json=PRODUCT_OUT_OF_STOCK_RESPONSE)
    if product_id == FIXTURE_PID_IN_STOCK:
        return httpx.Response(200, json=PRODUCT_IN_STOCK_RESPONSE)
    return httpx.Response(404, json={"error": "not found"})


def _standard_handler(**overrides: object) -> RecordingHandler:
    routes: dict = {
        "/1.0/search.json": SEARCH_RESPONSE,
        "/1.0/product.json": _product_router,
    }
    routes.update(overrides)
    return RecordingHandler(routes)


def _adapter(handler: RecordingHandler | None = None):
    recorded = handler or _standard_handler()
    adapter = create_adapter(env=TEST_ENV, http_client=mock_client(recorded))
    return adapter, recorded


class TestFlipkartAuthAndRequests:
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
        assert TOKEN not in (result.detail or "")

    async def test_search_sends_affiliate_headers_without_leaking_token_into_url(self) -> None:
        adapter, recorded = _adapter()
        await adapter.search_products(ProductSearchQuery(text="aurora"))
        request = recorded.requests[0]
        assert request.headers["Fk-Affiliate-Id"] == "test-affiliate-id"
        assert request.headers["Fk-Affiliate-Token"] == TOKEN
        assert "test-affiliate-token" not in str(request.url)
        params = parse_qs(urlparse(str(request.url)).query)
        assert params["query"] == ["aurora"]
        assert params["resultCount"] == ["10"]

    async def test_credentials_are_not_copied_into_config_options(self) -> None:
        adapter, _recorded = _adapter()
        joined = " ".join(adapter.config.options.values()).casefold()
        assert "token" not in joined
        assert TOKEN not in adapter.config.options.values()


class TestFlipkartSearchLookupPriceAvailability:
    async def test_product_search(self) -> None:
        adapter, _recorded = _adapter()
        result = await adapter.search_products(ProductSearchQuery(text="aurora", limit=10))
        assert result.retailer_id == RETAILER_ID
        assert len(result.products) == 2
        first = result.products[0]
        assert first.retailer_sku == FIXTURE_PID_IN_STOCK
        assert first.price is not None
        assert first.price.displayed_price == Decimal("58499.00")
        assert first.price.mrp == Decimal("69999.00")
        assert first.price.delivery_fee == Decimal("40.00")
        assert first.price.source_type is SourceType.AFFILIATE_FEED
        assert first.price.effective_price is None
        assert first.availability is not None
        assert first.availability.status is AvailabilityStatus.IN_STOCK
        assert first.category_path == ("Mobiles", "Handsets")

    async def test_search_uses_category_as_keywords_when_text_missing(self) -> None:
        adapter, recorded = _adapter()
        await adapter.search_products(ProductSearchQuery(category="mobiles"))
        params = parse_qs(urlparse(str(recorded.requests[0].url)).query)
        assert params["query"] == ["mobiles"]

    async def test_empty_search_is_valid(self) -> None:
        handler = _standard_handler(**{"/1.0/search.json": EMPTY_SEARCH_RESPONSE})
        adapter, _recorded = _adapter(handler)
        result = await adapter.search_products(ProductSearchQuery(text="zzzz"))
        assert result.products == ()

    async def test_product_lookup(self) -> None:
        adapter, _recorded = _adapter()
        product = await adapter.get_product(FIXTURE_PID_IN_STOCK)
        assert product.title.startswith("Fictional Orchard Aurora")
        assert product.brand_name == "Fictional Orchard"
        assert product.seller is not None
        assert product.seller.is_first_party is False

    async def test_product_lookup_missing_sku(self) -> None:
        adapter, _recorded = _adapter()
        with pytest.raises(ProductNotFoundError):
            await adapter.get_product(FIXTURE_PID_MISSING)

    async def test_price_retrieval(self) -> None:
        adapter, _recorded = _adapter()
        observation = await adapter.get_price(FIXTURE_PID_IN_STOCK)
        assert observation.displayed_price == Decimal("58499.00")
        assert observation.mrp == Decimal("69999.00")
        assert observation.currency == "INR"
        assert observation.source_url is not None

    async def test_availability_in_and_out_of_stock(self) -> None:
        adapter, _recorded = _adapter()
        in_stock = await adapter.get_availability(FIXTURE_PID_IN_STOCK)
        out = await adapter.get_availability(FIXTURE_PID_OUT_OF_STOCK)
        assert in_stock.status is AvailabilityStatus.IN_STOCK
        assert out.status is AvailabilityStatus.OUT_OF_STOCK
        assert out.seller is not None
        assert out.seller.is_first_party is True

    async def test_identifiers_are_not_declared(self) -> None:
        adapter, _recorded = _adapter()
        assert not adapter.supports(AdapterOperation.GET_PRODUCT_IDENTIFIERS)
        with pytest.raises(UnsupportedOperationError):
            await adapter.get_product_identifiers(FIXTURE_PID_IN_STOCK)

    async def test_normalization(self) -> None:
        adapter, _recorded = _adapter()
        product = await adapter.get_product(FIXTURE_PID_IN_STOCK)
        normalized = adapter.normalize_product(product)
        assert normalized.variant_attributes["color"] == "midnight"
        assert normalized.variant_attributes["storage"] == "128 gb"
        assert normalized.brand_slug == "fictional-orchard"
        assert normalized.category_slug == "handsets"
        assert "  " not in normalized.normalized_title

    async def test_health_with_credentials(self) -> None:
        adapter, recorded = _adapter()
        result = await adapter.health_check()
        assert result.is_healthy
        assert any("search.json" in str(req.url) for req in recorded.requests)


class TestFlipkartErrors:
    async def test_timeout(self) -> None:
        def hang(_request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out")

        handler = _standard_handler(**{"/1.0/search.json": hang})
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(AdapterTimeoutError):
            await adapter.search_products(ProductSearchQuery(text="aurora"))

    async def test_connection_failure(self) -> None:
        def down(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        handler = _standard_handler(**{"/1.0/search.json": down})
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(AdapterUnavailableError):
            await adapter.search_products(ProductSearchQuery(text="aurora"))

    async def test_http_429_is_rate_limited(self) -> None:
        handler = _standard_handler(
            **{
                "/1.0/search.json": httpx.Response(
                    429, headers={"Retry-After": "1"}, json={"error": "rate limited"}
                )
            }
        )
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(RateLimitExceededError) as exc:
            await adapter.search_products(ProductSearchQuery(text="aurora"))
        assert exc.value.retry_after_seconds == 1.0

    async def test_malformed_json(self) -> None:
        handler = _standard_handler(**{"/1.0/product.json": b"not-json{"})
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(InvalidRetailerResponseError):
            await adapter.get_product(FIXTURE_PID_IN_STOCK)

    async def test_malformed_product_without_title(self) -> None:
        handler = _standard_handler(**{"/1.0/product.json": MALFORMED_PRODUCT_RESPONSE})
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(InvalidRetailerResponseError):
            await adapter.get_product(FIXTURE_PID_IN_STOCK)

    async def test_unauthorized(self) -> None:
        handler = _standard_handler(
            **{"/1.0/search.json": httpx.Response(403, json={"error": "forbidden"})}
        )
        adapter = create_adapter(env=TEST_ENV, http_client=mock_client(handler))
        with pytest.raises(AdapterMisconfiguredError):
            await adapter.search_products(ProductSearchQuery(text="aurora"))
