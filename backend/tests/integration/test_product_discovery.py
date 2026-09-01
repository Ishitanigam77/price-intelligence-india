"""Phase 4 product discovery: HTTP search, adapter fan-out, persistence, and isolation."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_metrics_sink, get_retailer_registry
from app.db.models import PriceSnapshot, Product, RetailerProduct
from app.main import app as fastapi_app
from app.observability.metrics import InMemoryMetricsSink
from app.repositories.product_identifier_repository import ProductIdentifierRepository
from app.repositories.retailer_product_repository import RetailerProductRepository
from app.repositories.retailer_repository import RetailerRepository
from app.retailer_adapters.base.config import RetryPolicy
from app.retailer_adapters.base.errors import TemporaryRetailerFailureError
from app.retailer_adapters.base.metrics import ADAPTER_REQUESTS, ADAPTER_RETRIES, ADAPTER_TIMEOUTS
from app.retailer_adapters.base.models import ProductSearchQuery
from app.retailer_adapters.base.registry import RetailerRegistry
from app.retailer_adapters.mock_retailer_a import create_adapter as create_a
from app.retailer_adapters.mock_retailer_b import create_adapter as create_b
from app.retailer_adapters.mock_retailer_c import create_adapter as create_c
from app.services.product_discovery_service import (
    DISCOVERY_DURATION_MS,
    DISCOVERY_PERSISTED,
    DISCOVERY_RESULTS,
    DISCOVERY_SEARCHES,
    ProductDiscoveryService,
)
from tests.unit.retailer_adapters.helpers import (
    make_config,
    make_retailer_product,
    make_scripted_adapter,
)

REQUIRED_HIT_KEYS = {
    "product",
    "variant",
    "retailer",
    "seller",
    "retailer_product_id",
    "retailer_sku",
    "displayed_price",
    "mrp",
    "effective_price",
    "currency",
    "availability",
    "source_url",
    "observed_at",
    "source_type",
    "confidence",
}


@pytest.fixture()
def metrics_sink() -> InMemoryMetricsSink:
    return InMemoryMetricsSink()


@pytest.fixture()
def mock_registry(metrics_sink: InMemoryMetricsSink) -> RetailerRegistry:
    registry = RetailerRegistry()
    registry.register_all(
        [
            create_a(env={}, metrics_sink=metrics_sink),
            create_b(env={}, metrics_sink=metrics_sink),
            create_c(env={}, metrics_sink=metrics_sink),
        ]
    )
    return registry


@pytest.fixture()
def discovery_service(
    db_session: Session, mock_registry: RetailerRegistry, metrics_sink: InMemoryMetricsSink
) -> ProductDiscoveryService:
    return ProductDiscoveryService(db_session, mock_registry, metrics_sink=metrics_sink)


@pytest.fixture()
def search_client(
    client: TestClient, mock_registry: RetailerRegistry, metrics_sink: InMemoryMetricsSink
) -> Iterator[TestClient]:
    fastapi_app.dependency_overrides[get_retailer_registry] = lambda: mock_registry
    fastapi_app.dependency_overrides[get_metrics_sink] = lambda: metrics_sink
    try:
        yield client
    finally:
        fastapi_app.dependency_overrides.pop(get_retailer_registry, None)
        fastapi_app.dependency_overrides.pop(get_metrics_sink, None)


def _assert_hit_shape(hit: dict) -> None:
    assert set(hit.keys()) == REQUIRED_HIT_KEYS
    assert hit["product"]["id"]
    assert hit["variant"]["id"]
    assert hit["retailer"]["slug"]
    assert hit["displayed_price"] is not None
    assert hit["availability"]
    assert hit["source_url"]
    assert hit["observed_at"]
    assert hit["source_url"].startswith("https://")
    assert ".example.test" in hit["source_url"]


class TestSearchEndpoint:
    def test_search_endpoint_works(self, search_client: TestClient) -> None:
        response = search_client.get("/api/v1/products/search", params={"q": "aurora"})
        assert response.status_code == 200
        body = response.json()
        assert body["query"] == "aurora"
        assert body["total"] == 4
        assert len(body["items"]) == 4
        assert set(body["consulted_retailer_ids"]) == {
            "mock-retailer-a",
            "mock-retailer-b",
            "mock-retailer-c",
        }
        for hit in body["items"]:
            _assert_hit_shape(hit)

    def test_missing_search_text_is_rejected(self, search_client: TestClient) -> None:
        response = search_client.get("/api/v1/products/search")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_blank_search_text_is_rejected(self, search_client: TestClient) -> None:
        response = search_client.get("/api/v1/products/search", params={"q": "   "})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_results_from_multiple_retailers_are_combined(self, search_client: TestClient) -> None:
        response = search_client.get("/api/v1/products/search", params={"q": "aurora"})
        body = response.json()
        retailers = {hit["retailer"]["slug"] for hit in body["items"]}
        assert retailers == {"mock-retailer-a", "mock-retailer-b"}
        skus = {hit["retailer_sku"] for hit in body["items"]}
        assert skus == {"A-MOB-1001", "A-MOB-1002", "880011", "880042"}

    def test_results_are_normalized_into_the_standardized_response_format(
        self, search_client: TestClient
    ) -> None:
        response = search_client.get("/api/v1/products/search", params={"q": "aurora"})
        hit = next(
            item for item in response.json()["items"] if item["retailer_sku"] == "A-MOB-1001"
        )
        assert Decimal(hit["displayed_price"]) == Decimal("59999.00")
        assert Decimal(hit["mrp"]) == Decimal("69999.00")
        assert hit["effective_price"] is None
        assert hit["availability"] == "in_stock"
        assert hit["source_type"] == "official_api"
        assert hit["currency"] == "INR"
        assert hit["variant"]["attributes"]["storage"]
        assert hit["variant"]["variant_key"]

        bazaar = next(item for item in response.json()["items"] if item["retailer_sku"] == "880011")
        assert Decimal(bazaar["displayed_price"]) == Decimal("58499.00")
        assert bazaar["effective_price"] is not None
        assert bazaar["source_type"] == "affiliate_feed"
        assert bazaar["seller"]["is_first_party"] is False

    def test_pagination_works(self, search_client: TestClient) -> None:
        first = search_client.get(
            "/api/v1/products/search", params={"q": "aurora", "limit": 2, "offset": 0}
        )
        second = search_client.get(
            "/api/v1/products/search", params={"q": "aurora", "limit": 2, "offset": 2}
        )
        assert first.status_code == 200
        assert second.status_code == 200
        first_body = first.json()
        second_body = second.json()
        assert first_body["total"] == 4
        assert second_body["total"] == 4
        assert first_body["limit"] == 2
        assert second_body["offset"] == 2
        assert len(first_body["items"]) == 2
        assert len(second_body["items"]) == 2
        first_keys = {
            (item["retailer"]["slug"], item["retailer_sku"]) for item in first_body["items"]
        }
        second_keys = {
            (item["retailer"]["slug"], item["retailer_sku"]) for item in second_body["items"]
        }
        assert first_keys.isdisjoint(second_keys)

    def test_source_url_and_observation_timestamp_are_preserved(
        self, search_client: TestClient
    ) -> None:
        response = search_client.get("/api/v1/products/search", params={"q": "aurora"})
        for hit in response.json()["items"]:
            assert hit["source_url"].startswith("https://")
            assert hit["observed_at"].endswith("+00:00") or "T" in hit["observed_at"]


class TestEnabledRetailers:
    async def test_search_text_is_passed_to_enabled_adapters(
        self, db_session: Session, metrics_sink: InMemoryMetricsSink
    ) -> None:
        seen: list[ProductSearchQuery] = []

        async def capture(query: ProductSearchQuery):
            seen.append(query)
            return []

        registry = RetailerRegistry()
        registry.register(
            make_scripted_adapter(
                config=make_config(retailer_id="scripted-store"),
                script={"search_products": capture},
                metrics_sink=metrics_sink,
            )
        )
        service = ProductDiscoveryService(db_session, registry, metrics_sink=metrics_sink)
        await service.search(text="aurora 5g", limit=20, offset=0, category="mobiles")
        assert len(seen) == 1
        assert seen[0].text == "aurora 5g"
        assert seen[0].category == "mobiles"

    async def test_enabled_retailers_are_queried(
        self, discovery_service: ProductDiscoveryService, mock_registry: RetailerRegistry
    ) -> None:
        page = await discovery_service.search(text="aurora", limit=50, offset=0)
        assert set(page.consulted_retailer_ids) == set(
            mock_registry.retailer_ids(enabled_only=True)
        )
        assert page.total == 4

    async def test_disabled_retailers_are_not_queried(
        self, db_session: Session, metrics_sink: InMemoryMetricsSink
    ) -> None:
        registry = RetailerRegistry()
        enabled = create_a(env={}, metrics_sink=metrics_sink)
        disabled = create_b(env={}, metrics_sink=metrics_sink)
        disabled.disable()
        unused = create_c(env={}, metrics_sink=metrics_sink)
        unused.disable()
        registry.register_all([enabled, disabled, unused])
        service = ProductDiscoveryService(db_session, registry, metrics_sink=metrics_sink)
        page = await service.search(text="aurora", limit=50, offset=0)
        assert page.consulted_retailer_ids == ["mock-retailer-a"]
        assert all(hit.retailer.slug == "mock-retailer-a" for hit in page.items)
        assert (
            metrics_sink.counter_value(
                ADAPTER_REQUESTS, retailer_id="mock-retailer-b", operation="search_products"
            )
            == 0
        )
        assert (
            metrics_sink.counter_value(
                ADAPTER_REQUESTS, retailer_id="mock-retailer-c", operation="search_products"
            )
            == 0
        )
        assert (
            metrics_sink.counter_value(
                ADAPTER_REQUESTS, retailer_id="mock-retailer-a", operation="search_products"
            )
            >= 1
        )


class TestFailureIsolation:
    async def test_individual_retailer_failures_are_isolated(
        self, db_session: Session, metrics_sink: InMemoryMetricsSink
    ) -> None:
        registry = RetailerRegistry()
        registry.register(create_a(env={}, metrics_sink=metrics_sink))
        registry.register(
            make_scripted_adapter(
                config=make_config(retailer_id="scripted-down"),
                script={
                    "search_products": TemporaryRetailerFailureError(
                        "source unavailable",
                        retailer_id="scripted-down",
                        operation="search_products",
                    )
                },
                metrics_sink=metrics_sink,
            )
        )
        service = ProductDiscoveryService(db_session, registry, metrics_sink=metrics_sink)
        page = await service.search(text="aurora", limit=50, offset=0)
        assert page.total >= 1
        assert all(hit.retailer.slug == "mock-retailer-a" for hit in page.items)
        assert any(failure.retailer_id == "scripted-down" for failure in page.failures)
        assert "scripted-down" in page.consulted_retailer_ids
        assert "mock-retailer-a" in page.consulted_retailer_ids

    async def test_partial_results_are_returned_when_one_retailer_fails(
        self, search_client: TestClient, mock_registry: RetailerRegistry
    ) -> None:
        mock_registry.disable("mock-retailer-b")
        failing = make_scripted_adapter(
            config=make_config(retailer_id="scripted-down"),
            script={
                "search_products": TemporaryRetailerFailureError(
                    "source unavailable",
                    retailer_id="scripted-down",
                    operation="search_products",
                )
            },
        )
        mock_registry.register(failing)
        fastapi_app.dependency_overrides[get_retailer_registry] = lambda: mock_registry
        response = search_client.get("/api/v1/products/search", params={"q": "aurora"})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1
        assert {hit["retailer"]["slug"] for hit in body["items"]} == {"mock-retailer-a"}
        assert any(failure["retailer_id"] == "scripted-down" for failure in body["failures"])
        assert body["failures"][0]["error_code"] == "temporary_retailer_failure"


class TestPersistence:
    async def test_product_and_source_information_is_persisted(
        self, discovery_service: ProductDiscoveryService, db_session: Session
    ) -> None:
        page = await discovery_service.search(text="aurora", limit=50, offset=0)
        assert page.total == 4
        retailers = RetailerRepository(db_session)
        listings = RetailerProductRepository(db_session)
        assert retailers.get_by_slug("mock-retailer-a") is not None
        assert retailers.get_by_slug("mock-retailer-b") is not None
        listing = listings.get_by_retailer_and_sku(
            retailers.get_by_slug("mock-retailer-a").id, "A-MOB-1001"
        )
        assert listing is not None
        assert listing.url == "https://mock-retailer-a.example.test/product/A-MOB-1001"
        assert listing.product_variant is not None
        assert listing.product_variant.product.name
        identifiers = ProductIdentifierRepository(db_session)
        gtin = identifiers.get_by_type_and_value(
            listing.product_variant.identifiers[0].identifier_type,
            listing.product_variant.identifiers[0].value,
        )
        assert gtin is not None
        products = list(db_session.scalars(select(Product)).all())
        assert len(products) >= 4

    async def test_price_and_availability_are_persisted_and_returned(
        self, discovery_service: ProductDiscoveryService, db_session: Session
    ) -> None:
        page = await discovery_service.search(text="aurora", limit=50, offset=0)
        hit = next(item for item in page.items if item.retailer_sku == "A-MOB-1001")
        assert hit.displayed_price == Decimal("59999.00")
        assert hit.availability.value == "in_stock"
        snapshot = db_session.scalars(
            select(PriceSnapshot)
            .join(RetailerProduct)
            .where(RetailerProduct.retailer_sku == "A-MOB-1001")
        ).one()
        assert snapshot.displayed_price == Decimal("59999.00")
        assert snapshot.mrp == Decimal("69999.00")
        assert snapshot.availability.value == "in_stock"
        assert snapshot.source_url == hit.source_url
        assert snapshot.observed_at == hit.observed_at
        assert snapshot.seller_id is not None

    async def test_rediscovery_does_not_duplicate_listings(
        self, discovery_service: ProductDiscoveryService, db_session: Session
    ) -> None:
        await discovery_service.search(text="aurora", limit=50, offset=0)
        await discovery_service.search(text="aurora", limit=50, offset=0)
        listing_count = db_session.scalar(select(func.count()).select_from(RetailerProduct))
        assert listing_count == 4


class TestTimeoutAndRetry:
    async def test_timeout_is_isolated_and_uses_adapter_executor(
        self, db_session: Session, metrics_sink: InMemoryMetricsSink
    ) -> None:
        async def hang(_query: ProductSearchQuery) -> list:
            await asyncio.sleep(10)
            return []

        registry = RetailerRegistry()
        registry.register(create_a(env={}, metrics_sink=metrics_sink))
        registry.register(
            make_scripted_adapter(
                config=make_config(
                    retailer_id="scripted-timeout",
                    timeout_seconds=0.05,
                    retry_policy=RetryPolicy(max_attempts=1, jitter_ratio=0.0),
                ),
                script={"search_products": hang},
                metrics_sink=metrics_sink,
            )
        )
        service = ProductDiscoveryService(db_session, registry, metrics_sink=metrics_sink)
        page = await service.search(text="aurora", limit=50, offset=0)
        assert page.total >= 1
        assert any(failure.error_code == "timeout" for failure in page.failures)
        assert (
            metrics_sink.counter_value(
                ADAPTER_TIMEOUTS, retailer_id="scripted-timeout", operation="search_products"
            )
            == 1
        )

    async def test_retry_behavior_uses_adapter_executor(
        self, db_session: Session, metrics_sink: InMemoryMetricsSink
    ) -> None:
        product = make_retailer_product(
            retailer_id="scripted-retry", retailer_sku="SKU-RETRY", title="Retry Phone"
        )
        registry = RetailerRegistry()
        registry.register(
            make_scripted_adapter(
                config=make_config(
                    retailer_id="scripted-retry",
                    retry_policy=RetryPolicy(
                        max_attempts=3, initial_backoff_seconds=0.0, jitter_ratio=0.0
                    ),
                ),
                script={
                    "search_products": [
                        TemporaryRetailerFailureError(
                            "transient",
                            retailer_id="scripted-retry",
                            operation="search_products",
                        ),
                        [product],
                    ]
                },
                metrics_sink=metrics_sink,
            )
        )
        service = ProductDiscoveryService(db_session, registry, metrics_sink=metrics_sink)
        page = await service.search(text="Retry Phone", limit=50, offset=0)
        assert page.total == 1
        assert page.items[0].retailer_sku == "SKU-RETRY"
        assert page.failures == []
        assert (
            metrics_sink.counter_value(
                ADAPTER_RETRIES,
                retailer_id="scripted-retry",
                operation="search_products",
                error_type="temporary_retailer_failure",
            )
            == 1
        )


class TestObservability:
    async def test_structured_logging_is_generated(
        self,
        discovery_service: ProductDiscoveryService,
    ) -> None:
        with (
            patch("app.services.product_discovery_service.logger") as discovery_logger,
            patch("app.retailer_adapters.base.execution.logger") as adapter_logger,
        ):
            await discovery_service.search(text="aurora", limit=50, offset=0)

        info_messages = [call.args[0] for call in discovery_logger.info.call_args_list]
        assert "product_discovery.search_started" in info_messages
        assert "product_discovery.search_completed" in info_messages
        assert "product_discovery.listing_persisted" in info_messages
        started_extras = next(
            call.kwargs["extra"]
            for call in discovery_logger.info.call_args_list
            if call.args[0] == "product_discovery.search_started"
        )
        assert started_extras["query_text"] == "aurora"
        assert "correlation_id" in started_extras
        adapter_messages = [call.args[0] for call in adapter_logger.info.call_args_list]
        assert "retailer_adapter.operation_succeeded" in adapter_messages

    async def test_metrics_hooks_are_invoked(
        self, discovery_service: ProductDiscoveryService, metrics_sink: InMemoryMetricsSink
    ) -> None:
        await discovery_service.search(text="aurora", limit=50, offset=0)
        assert metrics_sink.total_for_name(DISCOVERY_SEARCHES) == 1
        assert metrics_sink.total_for_name(DISCOVERY_RESULTS) == 4
        assert metrics_sink.total_for_name(DISCOVERY_PERSISTED) == 4
        assert metrics_sink.observed_values(DISCOVERY_DURATION_MS)
        assert (
            metrics_sink.counter_value(
                ADAPTER_REQUESTS, retailer_id="mock-retailer-a", operation="search_products"
            )
            >= 1
        )


class TestHttpFailureIsolation:
    def test_search_endpoint_returns_partial_results(
        self, search_client: TestClient, mock_registry: RetailerRegistry
    ) -> None:
        mock_registry.disable("mock-retailer-c")
        mock_registry.get("mock-retailer-b").disable()
        response = search_client.get("/api/v1/products/search", params={"q": "aurora"})
        assert response.status_code == 200
        body = response.json()
        assert body["consulted_retailer_ids"] == ["mock-retailer-a"]
        assert {hit["retailer"]["slug"] for hit in body["items"]} == {"mock-retailer-a"}
        assert body["total"] == 2


class TestCatalogueNameMatch:
    async def test_persisted_catalogue_products_are_merged_into_search(
        self, discovery_service: ProductDiscoveryService, db_session: Session
    ) -> None:
        from tests.factories import (
            make_price_snapshot,
            make_product,
            make_retailer,
            make_retailer_product,
            make_variant,
        )

        product = make_product(name="DEVELOPMENT FIXTURE Catalogue Needle Phone")
        db_session.add(product)
        db_session.flush()
        variant = make_variant(product)
        db_session.add(variant)
        retailer = make_retailer(name="Demo Catalogue Mart")
        db_session.add(retailer)
        db_session.flush()
        listing = make_retailer_product(variant, retailer, retailer_sku="CAT-NEEDLE-1")
        db_session.add(listing)
        db_session.flush()
        db_session.add(make_price_snapshot(listing, displayed_price="12345.00"))
        db_session.flush()

        page = await discovery_service.search(text="Catalogue Needle", limit=50, offset=0)
        skus = {hit.retailer_sku for hit in page.items}
        assert "CAT-NEEDLE-1" in skus
        matched = next(hit for hit in page.items if hit.retailer_sku == "CAT-NEEDLE-1")
        assert matched.product.id == product.id
        assert matched.displayed_price == Decimal("12345.00")
        assert matched.variant.id == variant.id
