"""Behaviour of the three fixture-backed mock retailers.

Every assertion below is about *differences* the framework must absorb: identifiers, names,
prices, availability, operations, and categories. Nothing here talks to a network.
"""

from decimal import Decimal

import pytest

from app.domain.enums import (
    AvailabilityStatus,
    ConfidenceLevel,
    ProductIdentifierType,
    SourceType,
)
from app.retailer_adapters.base.errors import ProductNotFoundError, UnsupportedOperationError
from app.retailer_adapters.base.models import ProductSearchQuery
from app.retailer_adapters.mock_retailer_a import create_adapter as create_a
from app.retailer_adapters.mock_retailer_a.fixtures import LISTINGS_BY_SKU
from app.retailer_adapters.mock_retailer_b import create_adapter as create_b
from app.retailer_adapters.mock_retailer_b.fixtures import ROWS_BY_ITEM_ID
from app.retailer_adapters.mock_retailer_c import create_adapter as create_c
from app.retailer_adapters.mock_retailer_c.fixtures import ENTRIES_BY_ITEM_CODE

A_SKU = "A-MOB-1001"
B_SKU = "880011"
C_SKU = "C/AUD/0004"


class TestMockRetailerDifferences:
    async def test_product_identifiers_differ(self) -> None:
        a = await create_a(env={}).get_product_identifiers(A_SKU)
        b = await create_b(env={}).get_product_identifiers(B_SKU)
        assert a[0].identifier_type is ProductIdentifierType.GTIN
        assert a[0].value == "0000000001001"
        assert b[0].identifier_type is ProductIdentifierType.MPN
        assert b[0].value == "FO-AUR-128-MID"
        with pytest.raises(UnsupportedOperationError):
            await create_c(env={}).get_product_identifiers(C_SKU)

    async def test_product_names_differ_for_the_same_fictional_phone(self) -> None:
        a = await create_a(env={}).get_product(A_SKU)
        b = await create_b(env={}).get_product(B_SKU)
        assert a.title != b.title
        assert "Fictional Orchard Aurora" in a.title
        assert "Aurora 5G" in b.title

    async def test_prices_differ(self) -> None:
        a = await create_a(env={}).get_price(A_SKU)
        b = await create_b(env={}).get_price(B_SKU)
        c = await create_c(env={}).get_price(C_SKU)
        assert a.displayed_price == Decimal("59999.00")
        assert b.displayed_price == Decimal("58499.00")
        assert c.displayed_price == Decimal("3299.00")
        assert a.displayed_price != b.displayed_price != c.displayed_price

    async def test_availability_vocabularies_normalize_to_the_same_enum(self) -> None:
        a = await create_a(env={}).get_availability("A-AUD-2001")
        c = await create_c(env={}).get_availability("C/AUD/0088")
        assert a.status is AvailabilityStatus.OUT_OF_STOCK
        assert c.status is AvailabilityStatus.OUT_OF_STOCK
        limited_a = await create_a(env={}).get_availability("A-MOB-1002")
        limited_b_price = await create_b(env={}).get_price("880042")
        assert limited_a.status is AvailabilityStatus.LIMITED_STOCK
        assert limited_b_price.availability is AvailabilityStatus.LIMITED_STOCK

    def test_supported_operations_differ(self) -> None:
        a = create_a(env={})
        b = create_b(env={})
        c = create_c(env={})
        from app.retailer_adapters.base.config import AdapterOperation

        assert a.supports(AdapterOperation.GET_AVAILABILITY)
        assert not b.supports(AdapterOperation.GET_AVAILABILITY)
        assert c.supports(AdapterOperation.GET_AVAILABILITY)
        assert a.supports(AdapterOperation.GET_PRODUCT_IDENTIFIERS)
        assert b.supports(AdapterOperation.GET_PRODUCT_IDENTIFIERS)
        assert not c.supports(AdapterOperation.GET_PRODUCT_IDENTIFIERS)

    def test_supported_categories_differ(self) -> None:
        a, b, c = create_a(env={}), create_b(env={}), create_c(env={})
        assert a.serves_category("mobiles")
        assert a.serves_category("audio")
        assert b.serves_category("mobiles")
        assert b.serves_category("laptops")
        assert not b.serves_category("audio")
        assert c.serves_category("audio")
        assert c.serves_category("home-appliances")
        assert not c.serves_category("mobiles")


class TestSourceMetadata:
    async def test_source_type_and_confidence_differ_per_retailer(self) -> None:
        a = await create_a(env={}).get_price(A_SKU)
        b = await create_b(env={}).get_price(B_SKU)
        c = await create_c(env={}).get_price(C_SKU)
        assert a.source_type is SourceType.OFFICIAL_API
        assert a.confidence is ConfidenceLevel.HIGH
        assert b.source_type is SourceType.AFFILIATE_FEED
        assert b.confidence is ConfidenceLevel.MEDIUM
        assert c.source_type is SourceType.PRODUCT_FEED
        assert c.confidence is ConfidenceLevel.LOW

    async def test_seller_models_differ(self) -> None:
        a = await create_a(env={}).get_product(A_SKU)
        b = await create_b(env={}).get_product(B_SKU)
        c = await create_c(env={}).get_product(C_SKU)
        assert a.seller is not None and a.seller.is_first_party is True
        assert b.seller is not None and b.seller.is_first_party is False
        assert c.seller is not None and c.seller.is_first_party is True

    async def test_effective_price_is_only_set_when_the_source_provided_it(self) -> None:
        a = await create_a(env={}).get_price(A_SKU)
        b = await create_b(env={}).get_price(B_SKU)
        c = await create_c(env={}).get_price(C_SKU)
        assert a.effective_price is None
        assert b.effective_price == Decimal("58549.00")
        assert b.delivery_fee == Decimal("50.00")
        assert c.effective_price is None
        assert c.platform_fee == Decimal("49.00")


class TestDeterminismAndIsolation:
    async def test_repeated_fetches_are_identical(self) -> None:
        adapter = create_a(env={})
        first = await adapter.get_price(A_SKU)
        second = await adapter.get_price(A_SKU)
        assert first.displayed_price == second.displayed_price
        assert first.retailer_sku == second.retailer_sku

    async def test_unknown_sku_is_product_not_found(self) -> None:
        with pytest.raises(ProductNotFoundError) as exc:
            await create_a(env={}).get_price("DOES-NOT-EXIST")
        assert exc.value.operation == "get_price"
        assert exc.value.retailer_id == "mock-retailer-a"

    async def test_search_is_deterministic_and_respects_limit(self) -> None:
        result = await create_a(env={}).search_products(ProductSearchQuery(text="aurora", limit=1))
        assert len(result.products) == 1
        assert result.products[0].retailer_sku == "A-MOB-1001"

    def test_fixtures_are_local_invented_data(self) -> None:
        for sku, listing in LISTINGS_BY_SKU.items():
            assert sku.startswith("A-")
            assert "Fictional" in listing["productName"] or "Fictional" in listing["brand"]
        for item_id, row in ROWS_BY_ITEM_ID.items():
            assert item_id.isdigit()
            assert "Fictional" in row["mfr"]
        for code, entry in ENTRIES_BY_ITEM_CODE.items():
            assert code.startswith("C/")
            assert "Fictional" in entry["title"] or "Fictional" in entry["manufacturer"]
