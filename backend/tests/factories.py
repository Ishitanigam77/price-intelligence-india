"""Lightweight factory helpers for building Phase 1 model instances in tests.

These are plain constructors with sensible fake defaults — not a full factory_boy setup, which
would be more machinery than Phase 1's test surface needs.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.db.models import (
    Brand,
    Category,
    PriceSnapshot,
    Product,
    ProductIdentifier,
    ProductVariant,
    Retailer,
    RetailerProduct,
    Seller,
)
from app.domain.enums import AvailabilityStatus, ConfidenceLevel, ProductIdentifierType, SourceType


def make_category(*, name: str = "Mobiles", slug: str | None = None, **kwargs) -> Category:
    return Category(name=name, slug=slug or f"cat-{uuid.uuid4().hex[:10]}", **kwargs)


def make_brand(*, name: str | None = None, slug: str | None = None, **kwargs) -> Brand:
    suffix = uuid.uuid4().hex[:8]
    return Brand(name=name or f"Fictional Brand {suffix}", slug=slug or f"brand-{suffix}", **kwargs)


def make_product(*, name: str = "Fictional Phone X", slug: str | None = None, **kwargs) -> Product:
    return Product(name=name, slug=slug or f"product-{uuid.uuid4().hex[:10]}", **kwargs)


def make_variant(
    product: Product, *, attributes: dict[str, str] | None = None, **kwargs
) -> ProductVariant:
    if attributes is None:
        attributes = {"storage": "128GB", "color": "Black"}
    return ProductVariant(product=product, attributes=attributes, **kwargs)


def make_identifier(
    variant: ProductVariant,
    *,
    identifier_type: ProductIdentifierType = ProductIdentifierType.GTIN,
    value: str | None = None,
) -> ProductIdentifier:
    return ProductIdentifier(
        product_variant=variant,
        identifier_type=identifier_type,
        value=value or f"{uuid.uuid4().int % 10**13:013d}",
    )


def make_retailer(*, name: str | None = None, slug: str | None = None, **kwargs) -> Retailer:
    suffix = uuid.uuid4().hex[:8]
    return Retailer(
        name=name or f"Fictional Mart {suffix}", slug=slug or f"retailer-{suffix}", **kwargs
    )


def make_seller(retailer: Retailer, *, name: str = "Fictional Seller", **kwargs) -> Seller:
    return Seller(retailer=retailer, name=name, **kwargs)


def make_retailer_product(
    variant: ProductVariant,
    retailer: Retailer,
    *,
    retailer_sku: str | None = None,
    **kwargs,
) -> RetailerProduct:
    return RetailerProduct(
        product_variant=variant,
        retailer=retailer,
        retailer_sku=retailer_sku or f"SKU-{uuid.uuid4().hex[:10].upper()}",
        url=kwargs.pop("url", "https://example-fictional-retailer.test/listing/123"),
        **kwargs,
    )


def make_price_snapshot(
    retailer_product: RetailerProduct,
    *,
    displayed_price: Decimal | str = "999.00",
    observed_at: datetime | None = None,
    availability: AvailabilityStatus = AvailabilityStatus.IN_STOCK,
    source_type: SourceType = SourceType.OTHER_PERMITTED,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    **kwargs,
) -> PriceSnapshot:
    return PriceSnapshot(
        retailer_product=retailer_product,
        displayed_price=Decimal(displayed_price),
        observed_at=observed_at or datetime.now(UTC),
        availability=availability,
        source_type=source_type,
        confidence=confidence,
        **kwargs,
    )
