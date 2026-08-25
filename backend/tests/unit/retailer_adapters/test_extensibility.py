"""Extensibility: a fourth retailer can be added without touching core comparison logic.

This is the architectural proof required by the Phase 2 adapter-framework scope:

1. MockRetailerA/B/C register, discover, enable, and disable through the common registry.
2. Their standardized outputs are consumed by `RetailerFleet` (the retailer-agnostic consumer).
3. A fourth mock retailer is introduced *in this test*, by implementing `RetailerAdapter`.
4. Core comparison (`lowest_price`) and `RetailerFleet` are not modified to know about it.
"""

from decimal import Decimal
from pathlib import Path

from app.domain.enums import AvailabilityStatus, ConfidenceLevel, SourceType
from app.domain.validation import slugify
from app.retailer_adapters.base.config import AdapterOperation
from app.retailer_adapters.base.discovery import AdapterKind, discover_adapters
from app.retailer_adapters.base.fleet import RetailerFleet
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.models import (
    NormalizedProduct,
    PriceObservation,
    ProductSearchQuery,
    ProductSearchResult,
    RetailerProduct,
    SellerInformation,
)
from app.retailer_adapters.base.registry import RetailerRegistry
from app.retailer_adapters.mock_retailer_a import create_adapter as create_a
from app.retailer_adapters.mock_retailer_b import create_adapter as create_b
from app.retailer_adapters.mock_retailer_c import create_adapter as create_c
from tests.unit.retailer_adapters.helpers import lowest_price, make_config

BACKEND_ROOT = Path(__file__).resolve().parents[3]
FLEET_SOURCE = (BACKEND_ROOT / "app/retailer_adapters/base/fleet.py").read_text()
REGISTRY_SOURCE = (BACKEND_ROOT / "app/retailer_adapters/base/registry.py").read_text()
INTERFACE_SOURCE = (BACKEND_ROOT / "app/retailer_adapters/base/interface.py").read_text()

FOURTH_ID = "mock-retailer-d"
FOURTH_SKU = "D-HOM-77"
FOURTH_PRICE = Decimal("13999.00")


class MockRetailerDAdapter(RetailerAdapter):
    """Fourth retailer, defined only in this test. Not a production adapter."""

    async def _search_products(self, query: ProductSearchQuery) -> ProductSearchResult:
        product = self._listing()
        matches = () if query.category not in (None, "home-appliances") else (product,)
        if query.text and query.text.strip().lower() not in product.title.lower():
            matches = ()
        return ProductSearchResult(
            retailer_id=self.retailer_id,
            query=query,
            products=matches,
            retrieved_at=self._now(),
        )

    async def _get_product(self, retailer_sku: str) -> RetailerProduct:
        return self._listing()

    async def _get_price(self, retailer_sku: str) -> PriceObservation:
        listing = self._listing()
        assert listing.price is not None
        return listing.price

    async def _check_health(self) -> str | None:
        return "fourth mock retailer healthy"

    def normalize_product(self, product: RetailerProduct) -> NormalizedProduct:
        return NormalizedProduct(
            retailer_id=product.retailer_id,
            retailer_sku=product.retailer_sku,
            normalized_title=product.title,
            brand_name=product.brand_name,
            brand_slug=slugify(product.brand_name) if product.brand_name else None,
            category_slug="home-appliances",
            variant_attributes=dict(product.attributes),
            source_url=product.url,
            source_type=product.source_type,
            normalized_at=self._now(),
        )

    def _listing(self) -> RetailerProduct:
        price = PriceObservation(
            retailer_id=self.retailer_id,
            retailer_sku=FOURTH_SKU,
            observed_at=self._now(),
            displayed_price=FOURTH_PRICE,
            mrp=Decimal("18999.00"),
            availability=AvailabilityStatus.IN_STOCK,
            source_type=SourceType.OTHER_PERMITTED,
            source_url="https://mock-retailer-d.example.test/d-hom-77",
            confidence=ConfidenceLevel.MEDIUM,
            seller=SellerInformation(name="Fictional Mock D", is_first_party=True),
        )
        return RetailerProduct(
            retailer_id=self.retailer_id,
            retailer_sku=FOURTH_SKU,
            title="Fictional Hearthline Air Purifier 300 (from Mock D)",
            url=price.source_url,
            brand_name="Fictional Hearthline",
            category_path=("Home Appliances",),
            attributes={"coverage": "300 sq ft", "colour": "White"},
            seller=price.seller,
            price=price,
            source_type=SourceType.OTHER_PERMITTED,
            retrieved_at=self._now(),
        )


def _fourth_adapter() -> MockRetailerDAdapter:
    return MockRetailerDAdapter(
        make_config(
            retailer_id=FOURTH_ID,
            retailer_name="Fictional Mock D",
            source_type=SourceType.OTHER_PERMITTED,
            supported_categories=("home-appliances",),
            supported_operations=frozenset(
                {
                    AdapterOperation.SEARCH_PRODUCTS,
                    AdapterOperation.GET_PRODUCT,
                    AdapterOperation.GET_PRICE,
                }
            ),
        )
    )


def test_core_modules_do_not_name_the_fourth_retailer() -> None:
    """Adding MockRetailerD must not require edits to fleet/registry/interface."""
    for source in (FLEET_SOURCE, REGISTRY_SOURCE, INTERFACE_SOURCE):
        assert FOURTH_ID not in source
        assert "MockRetailerD" not in source
        assert "mock-retailer-a" not in source
        assert "mock-retailer-b" not in source
        assert "mock-retailer-c" not in source


async def test_three_mocks_register_discover_enable_disable_and_are_consumed() -> None:
    registry = RetailerRegistry()
    registry.register_all([create_a(env={}), create_b(env={}), create_c(env={})])
    assert registry.retailer_ids() == ("mock-retailer-a", "mock-retailer-b", "mock-retailer-c")

    discovered = {entry.retailer_id for entry in discover_adapters(kinds=(AdapterKind.MOCK,))}
    assert discovered == {"mock-retailer-a", "mock-retailer-b", "mock-retailer-c"}

    registry.disable("mock-retailer-c")
    fleet = RetailerFleet(registry)
    outcome = await fleet.search(ProductSearchQuery(text="aurora"))
    assert "mock-retailer-a" in outcome.consulted_retailer_ids
    assert "mock-retailer-b" in outcome.consulted_retailer_ids
    assert "mock-retailer-c" not in outcome.consulted_retailer_ids
    assert outcome.products
    assert outcome.normalized_products
    assert {product.retailer_id for product in outcome.products} <= {
        "mock-retailer-a",
        "mock-retailer-b",
    }

    registry.enable("mock-retailer-c")
    health = await fleet.health_report()
    assert set(health) == {"mock-retailer-a", "mock-retailer-b", "mock-retailer-c"}


async def test_fourth_retailer_joins_the_fleet_without_core_changes() -> None:
    registry = RetailerRegistry()
    registry.register_all([create_a(env={}), create_b(env={}), create_c(env={}), _fourth_adapter()])
    assert FOURTH_ID in registry
    assert registry.get(FOURTH_ID).supports(AdapterOperation.GET_PRICE)
    assert not registry.get(FOURTH_ID).supports(AdapterOperation.GET_AVAILABILITY)

    fleet = RetailerFleet(registry)
    d_only = await fleet.search(ProductSearchQuery(text="from Mock D"))
    assert FOURTH_ID in d_only.consulted_retailer_ids
    d_products = d_only.products_for(FOURTH_ID)
    assert len(d_products) == 1
    assert d_products[0].retailer_sku == FOURTH_SKU
    assert d_only.normalized_products
    assert any(item.retailer_id == FOURTH_ID for item in d_only.normalized_products)

    # Retailer-agnostic comparison over every priced listing the fleet returned for a
    # home-appliances query — including the new retailer — without a single retailer branch.
    appliances = await fleet.search(ProductSearchQuery(category="home-appliances"))
    priced = appliances.price_observations
    assert {observation.retailer_id for observation in priced} == {
        "mock-retailer-c",
        FOURTH_ID,
    }
    winner = lowest_price(priced)
    # The comparison function did not look at retailer_id to decide; we only read it afterwards.
    assert winner.displayed_price == min(item.displayed_price for item in priced)
    assert winner.retailer_id in {"mock-retailer-c", FOURTH_ID}
