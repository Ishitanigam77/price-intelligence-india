"""Lightweight factory helpers for building Phase 1 model instances in tests.

These are plain constructors with sensible fake defaults — not a full factory_boy setup, which
would be more machinery than Phase 1's test surface needs.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.db.models import (
    Brand,
    Category,
    PriceAdjustment,
    PriceAlert,
    PriceSnapshot,
    Product,
    ProductIdentifier,
    ProductVariant,
    Retailer,
    RetailerProduct,
    SaleEvent,
    SavedProduct,
    Seller,
    TargetPrice,
    User,
    UserPreference,
    WatchlistItem,
)
from app.domain.enums import (
    AdjustmentEligibility,
    AdjustmentKind,
    AvailabilityStatus,
    ConfidenceLevel,
    ProductIdentifierType,
    SaleEventSource,
    SaleEventType,
    SourceType,
)


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


def make_price_adjustment(
    snapshot: PriceSnapshot,
    *,
    kind: AdjustmentKind = AdjustmentKind.COUPON,
    amount: Decimal | str | None = "50.00",
    source: str = "test.observed_coupon",
    eligibility: AdjustmentEligibility = AdjustmentEligibility.VERIFIED_ELIGIBLE,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    observed_at: datetime | None = None,
    **kwargs,
) -> PriceAdjustment:
    return PriceAdjustment(
        price_snapshot=snapshot,
        kind=kind,
        amount=None if amount is None else Decimal(amount),
        source=source,
        eligibility=eligibility,
        observed_at=observed_at or snapshot.observed_at,
        confidence=confidence,
        **kwargs,
    )


def make_sale_event(
    *,
    name: str = "FIXTURE: Fictional Catalogue Sale",
    event_type: SaleEventType = SaleEventType.SEASONAL,
    source: SaleEventSource = SaleEventSource.MANUAL_CURATION,
    source_ref: str | None = "test.fixture",
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    retailer: Retailer | None = None,
    category: Category | None = None,
    brand: Brand | None = None,
    **kwargs,
) -> SaleEvent:
    """Build a clearly labeled fictional sale event. Not a real-world campaign."""
    start = start_date or datetime.now(UTC)
    end = end_date or (start + timedelta(days=7))
    retailer_id = kwargs.pop("retailer_id", retailer.id if retailer is not None else None)
    category_id = kwargs.pop("category_id", category.id if category is not None else None)
    brand_id = kwargs.pop("brand_id", brand.id if brand is not None else None)
    return SaleEvent(
        name=name,
        event_type=event_type,
        source=source,
        source_ref=source_ref,
        confidence=confidence,
        start_date=start,
        end_date=end,
        retailer=retailer,
        retailer_id=retailer_id,
        category=category,
        category_id=category_id,
        brand=brand,
        brand_id=brand_id,
        **kwargs,
    )


def make_user(
    *,
    clerk_user_id: str | None = None,
    email: str | None = None,
    display_name: str | None = None,
    **kwargs,
) -> User:
    suffix = uuid.uuid4().hex[:10]
    return User(
        clerk_user_id=clerk_user_id or f"user_clerk_{suffix}",
        email=email,
        display_name=display_name,
        **kwargs,
    )


def make_user_preference(user: User, **kwargs) -> UserPreference:
    return UserPreference(user=user, **kwargs)


def make_watchlist_item(user: User, product: Product, **kwargs) -> WatchlistItem:
    return WatchlistItem(user=user, product=product, **kwargs)


def make_saved_product(user: User, product: Product, **kwargs) -> SavedProduct:
    return SavedProduct(user=user, product=product, **kwargs)


def make_target_price(
    user: User,
    product: Product,
    *,
    amount: Decimal | str = "999.00",
    currency: str = "INR",
    **kwargs,
) -> TargetPrice:
    return TargetPrice(
        user=user,
        product=product,
        amount=Decimal(amount),
        currency=currency,
        **kwargs,
    )


def make_price_alert(
    user: User,
    product: Product,
    *,
    threshold_amount: Decimal | str = "899.00",
    currency: str = "INR",
    is_enabled: bool = True,
    **kwargs,
) -> PriceAlert:
    return PriceAlert(
        user=user,
        product=product,
        threshold_amount=Decimal(threshold_amount),
        currency=currency,
        is_enabled=is_enabled,
        **kwargs,
    )
