"""Seed clearly labelled DEVELOPMENT / TEST FIXTURE data for local verification.

This is a *development-only* convenience script, not a fixture used by the automated test
suite (see `backend/tests/factories.py` for that). Every name, retailer, SKU, price, and
sale window below is invented for this seed — none of it is live retailer data and none of
it represents Amazon, Flipkart, Ubuy, Myntra, or any other real store.

Re-running the script replaces previous copies of these fixture rows. It does not touch
unrelated catalogue products created by retailer adapters.

Usage (from `backend/`, with `DATABASE_URL` pointing at a dev database):

    python -m scripts.seed_dev_data
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Brand,
    Category,
    PriceSnapshot,
    Product,
    ProductIdentifier,
    ProductVariant,
    Retailer,
    RetailerProduct,
    SaleEvent,
    Seller,
)
from app.db.session import SessionLocal
from app.domain.enums import (
    AvailabilityStatus,
    ConfidenceLevel,
    ProductIdentifierType,
    SaleEventSource,
    SaleEventType,
    SourceType,
)

FIXTURE_SOURCE_REFS = ("test.fixture.seed", "dev.fixture.phase19")
SOURCE_REF = "dev.fixture.phase19"
PRODUCT_SLUGS = ("fictional-orchard-phone-z", "demo-phone-z")
BRAND_SLUGS = ("fictional-orchard", "demo-brand")
CATEGORY_SLUGS = ("electronics-mobiles", "demo-electronics", "demo-mobiles")
RETAILER_SLUGS = (
    "fictional-big-mart",
    "fictional-local-store",
    "demo-retailer-a",
    "demo-retailer-b",
    "demo-retailer-c",
    "demo-retailer-d",
    "demo-retailer-e",
    "demo-retailer-f",
)
MRP_128 = Decimal("24999.00")
MRP_256 = Decimal("29999.00")


def _purge_previous_fixture(session: Session) -> None:
    """Remove earlier copies of this development seed so the script is re-runnable."""
    retailer_ids = list(
        session.scalars(select(Retailer.id).where(Retailer.slug.in_(RETAILER_SLUGS)))
    )
    brand_ids = list(session.scalars(select(Brand.id).where(Brand.slug.in_(BRAND_SLUGS))))
    sale_filters = [SaleEvent.source_ref.in_(FIXTURE_SOURCE_REFS)]
    if retailer_ids:
        sale_filters.append(SaleEvent.retailer_id.in_(retailer_ids))
    if brand_ids:
        sale_filters.append(SaleEvent.brand_id.in_(brand_ids))
    session.execute(delete(SaleEvent).where(or_(*sale_filters)))
    session.flush()
    products = list(session.scalars(select(Product).where(Product.slug.in_(PRODUCT_SLUGS))))
    for product in products:
        session.delete(product)
    session.flush()
    retailers = list(session.scalars(select(Retailer).where(Retailer.slug.in_(RETAILER_SLUGS))))
    for retailer in retailers:
        session.delete(retailer)
    session.flush()
    brands = list(session.scalars(select(Brand).where(Brand.slug.in_(BRAND_SLUGS))))
    for brand in brands:
        session.delete(brand)
    session.flush()
    categories = list(
        session.scalars(select(Category).where(Category.slug.in_(CATEGORY_SLUGS))).all()
    )
    for category in sorted(categories, key=lambda item: 0 if item.parent_id else 1):
        remaining = session.scalar(
            select(Product.id).where(Product.category_id == category.id).limit(1)
        )
        if remaining is None:
            session.delete(category)
    session.flush()


def _snapshot(
    *,
    listing: RetailerProduct,
    observed_at: datetime,
    price: Decimal,
    mrp: Decimal,
    availability: AvailabilityStatus,
    seller_id: object | None = None,
    delivery_fee: Decimal | None = None,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> PriceSnapshot:
    return PriceSnapshot(
        retailer_product=listing,
        seller_id=seller_id,
        observed_at=observed_at,
        mrp=mrp,
        displayed_price=price,
        effective_price=price,
        delivery_fee=delivery_fee,
        availability=availability,
        source_type=SourceType.OTHER_PERMITTED,
        source_url=listing.url,
        confidence=confidence,
    )


def seed(session: Session) -> Product:
    _purge_previous_fixture(session)

    electronics = Category(name="DEVELOPMENT FIXTURE Electronics", slug="demo-electronics")
    mobiles = Category(
        name="DEVELOPMENT FIXTURE Mobiles",
        slug="demo-mobiles",
        parent=electronics,
    )
    session.add_all([electronics, mobiles])

    brand = Brand(
        name="DEVELOPMENT FIXTURE Demo Brand",
        slug="demo-brand",
        description="Invented brand used only for local Phase 19 verification. Not a real brand.",
    )
    session.add(brand)

    product = Product(
        name="DEVELOPMENT FIXTURE: Demo Phone Z",
        slug="demo-phone-z",
        brand=brand,
        category=mobiles,
        description=(
            "DEVELOPMENT / TEST FIXTURE. Invented catalogue row for local verification of "
            "all-retailer comparison, monthly intelligence, and sale timing. These prices, "
            "sellers, and sale windows are not live retailer data and must not be treated as "
            "Amazon, Flipkart, Ubuy, Myntra, or any other real-store observations."
        ),
    )
    session.add(product)

    variant_128 = ProductVariant(
        product=product,
        name="128GB / Midnight",
        attributes={"storage": "128GB", "color": "Midnight"},
    )
    variant_256 = ProductVariant(
        product=product,
        name="256GB / Midnight",
        attributes={"storage": "256GB", "color": "Midnight"},
    )
    session.add_all([variant_128, variant_256])
    session.add(
        ProductIdentifier(
            product_variant=variant_128,
            identifier_type=ProductIdentifierType.GTIN,
            value="0000000000128",
        )
    )
    session.add(
        ProductIdentifier(
            product_variant=variant_256,
            identifier_type=ProductIdentifierType.GTIN,
            value="0000000000256",
        )
    )

    retailers: list[Retailer] = []
    for letter in "ABCDEF":
        retailers.append(
            Retailer(
                name=f"Demo Retailer {letter}",
                slug=f"demo-retailer-{letter.lower()}",
                website_url=f"https://demo-retailer-{letter.lower()}.example.test",
            )
        )
    session.add_all(retailers)
    retailer_a, retailer_b, retailer_c, retailer_d, retailer_e, retailer_f = retailers

    sellers_first = [
        Seller(retailer=retailer, name=retailer.name, is_first_party=True) for retailer in retailers
    ]
    marketplace_seller = Seller(
        retailer=retailer_e,
        name="DEVELOPMENT FIXTURE Marketplace Seller Co.",
        is_first_party=False,
    )
    session.add_all([*sellers_first, marketplace_seller])
    (
        seller_a,
        seller_b,
        seller_c,
        seller_d,
        seller_e,
        seller_f,
    ) = sellers_first

    listings_128 = [
        RetailerProduct(
            product_variant=variant_128,
            retailer=retailer,
            retailer_sku=f"DEMO-Z-128-{letter}",
            url=f"https://demo-retailer-{letter.lower()}.example.test/listing/demo-z-128",
        )
        for letter, retailer in zip("ABCDEF", retailers, strict=True)
    ]
    listing_256_a = RetailerProduct(
        product_variant=variant_256,
        retailer=retailer_a,
        retailer_sku="DEMO-Z-256-A",
        url="https://demo-retailer-a.example.test/listing/demo-z-256",
    )
    listing_256_b = RetailerProduct(
        product_variant=variant_256,
        retailer=retailer_b,
        retailer_sku="DEMO-Z-256-B",
        url="https://demo-retailer-b.example.test/listing/demo-z-256",
    )
    session.add_all([*listings_128, listing_256_a, listing_256_b])
    session.flush()

    now = datetime.now(UTC).replace(microsecond=0)
    listing_by_letter = dict(zip("ABCDEF", listings_128, strict=True))
    seller_by_letter = {
        "A": seller_a.id,
        "B": seller_b.id,
        "C": seller_c.id,
        "D": seller_d.id,
        "E": seller_e.id,
        "F": seller_f.id,
    }
    # Current verified prices: F is cheapest now; A is historically cheapest in the major sale.
    current_128 = {
        "A": (Decimal("22199.00"), AvailabilityStatus.IN_STOCK, Decimal("0.00")),
        "B": (Decimal("19999.00"), AvailabilityStatus.IN_STOCK, Decimal("49.00")),
        "C": (Decimal("19499.00"), AvailabilityStatus.LIMITED_STOCK, None),
        "D": (Decimal("18999.00"), AvailabilityStatus.IN_STOCK, None),
        "E": (Decimal("18500.00"), AvailabilityStatus.IN_STOCK, None),
        "F": (Decimal("18179.00"), AvailabilityStatus.IN_STOCK, None),
    }
    for letter, (price, availability, delivery) in current_128.items():
        session.add(
            _snapshot(
                listing=listing_by_letter[letter],
                observed_at=now,
                price=price,
                mrp=MRP_128,
                availability=availability,
                seller_id=seller_by_letter[letter],
                delivery_fee=delivery,
            )
        )
    session.add(
        _snapshot(
            listing=listing_by_letter["E"],
            observed_at=now,
            price=Decimal("19200.00"),
            mrp=MRP_128,
            availability=AvailabilityStatus.IN_STOCK,
            seller_id=marketplace_seller.id,
            confidence=ConfidenceLevel.MEDIUM,
        )
    )
    session.add(
        _snapshot(
            listing=listing_256_a,
            observed_at=now,
            price=Decimal("27999.00"),
            mrp=MRP_256,
            availability=AvailabilityStatus.OUT_OF_STOCK,
            seller_id=seller_a.id,
        )
    )
    session.add(
        _snapshot(
            listing=listing_256_b,
            observed_at=now,
            price=Decimal("26999.00"),
            mrp=MRP_256,
            availability=AvailabilityStatus.IN_STOCK,
            seller_id=seller_b.id,
        )
    )

    # Monthly intelligence: January is cheaper than April/August; needs ≥3 obs per month.
    monthly_schedule: list[tuple[int, int, int, str, str]] = []
    for year in (2025, 2026):
        for day in (6, 14, 22):
            monthly_schedule.append((year, 1, day, "A", "16800.00"))
            monthly_schedule.append((year, 1, day, "F", "17200.00"))
        for day in (5, 13, 21):
            monthly_schedule.append((year, 4, day, "A", "19800.00"))
            monthly_schedule.append((year, 4, day, "F", "19100.00"))
    for day in (4, 12, 20):
        monthly_schedule.append((2025, 8, day, "A", "21400.00"))
        monthly_schedule.append((2025, 8, day, "B", "20500.00"))
        monthly_schedule.append((2025, 8, day, "F", "19600.00"))
    for year, month, day, letter, amount in monthly_schedule:
        session.add(
            _snapshot(
                listing=listing_by_letter[letter],
                observed_at=datetime(year, month, day, 12, 0, tzinfo=UTC),
                price=Decimal(amount),
                mrp=MRP_128,
                availability=AvailabilityStatus.IN_STOCK,
                seller_id=seller_by_letter[letter],
            )
        )

    major_windows = (
        (datetime(2024, 10, 15, 0, 0, tzinfo=UTC), datetime(2024, 10, 20, 0, 0, tzinfo=UTC)),
        (datetime(2025, 10, 15, 0, 0, tzinfo=UTC), datetime(2025, 10, 20, 0, 0, tzinfo=UTC)),
        (datetime(2026, 10, 15, 0, 0, tzinfo=UTC), datetime(2026, 10, 20, 0, 0, tzinfo=UTC)),
    )
    ordinary_windows = (
        (datetime(2024, 9, 8, 0, 0, tzinfo=UTC), datetime(2024, 9, 10, 0, 0, tzinfo=UTC)),
        (datetime(2025, 9, 8, 0, 0, tzinfo=UTC), datetime(2025, 9, 10, 0, 0, tzinfo=UTC)),
        (datetime(2026, 9, 11, 0, 0, tzinfo=UTC), datetime(2026, 9, 13, 0, 0, tzinfo=UTC)),
    )
    for start, end in major_windows:
        year = start.year
        session.add(
            SaleEvent(
                name=f"DEVELOPMENT FIXTURE: Demo Seasonal Mega Sale {year}",
                event_type=SaleEventType.SEASONAL,
                source=SaleEventSource.MANUAL_CURATION,
                source_ref=SOURCE_REF,
                confidence=ConfidenceLevel.HIGH,
                start_date=start,
                end_date=end,
            )
        )
        if year >= 2026:
            continue
        pre = start - timedelta(days=7)
        mid = start + timedelta(days=2)
        sale_prices = {
            "A": Decimal("15999.00"),
            "B": Decimal("16800.00"),
            "C": Decimal("17000.00"),
            "D": Decimal("17200.00"),
            "E": Decimal("17400.00"),
            "F": Decimal("17500.00"),
        }
        baseline = {
            "A": Decimal("22000.00"),
            "B": Decimal("21500.00"),
            "C": Decimal("21200.00"),
            "D": Decimal("21000.00"),
            "E": Decimal("20800.00"),
            "F": Decimal("20600.00"),
        }
        for letter, listing in listing_by_letter.items():
            session.add(
                _snapshot(
                    listing=listing,
                    observed_at=pre.replace(hour=12),
                    price=baseline[letter],
                    mrp=MRP_128,
                    availability=AvailabilityStatus.IN_STOCK,
                    seller_id=seller_by_letter[letter],
                )
            )
            session.add(
                _snapshot(
                    listing=listing,
                    observed_at=mid.replace(hour=12),
                    price=sale_prices[letter],
                    mrp=MRP_128,
                    availability=AvailabilityStatus.IN_STOCK,
                    seller_id=seller_by_letter[letter],
                )
            )
            session.add(
                _snapshot(
                    listing=listing,
                    observed_at=(mid + timedelta(days=1)).replace(hour=15),
                    price=sale_prices[letter] + Decimal("50.00"),
                    mrp=MRP_128,
                    availability=AvailabilityStatus.IN_STOCK,
                    seller_id=seller_by_letter[letter],
                )
            )

    for start, end in ordinary_windows:
        year = start.year
        session.add(
            SaleEvent(
                name=f"DEVELOPMENT FIXTURE: Demo Brand Refresh Sale {year}",
                event_type=SaleEventType.BRAND,
                source=SaleEventSource.MANUAL_CURATION,
                source_ref=SOURCE_REF,
                confidence=ConfidenceLevel.MEDIUM,
                brand=brand,
                start_date=start,
                end_date=end,
            )
        )
        if year >= 2026:
            continue
        mid = start + timedelta(days=1)
        ordinary_prices = {
            "A": Decimal("20500.00"),
            "B": Decimal("19800.00"),
            "F": Decimal("19000.00"),
        }
        for letter, price in ordinary_prices.items():
            session.add(
                _snapshot(
                    listing=listing_by_letter[letter],
                    observed_at=mid.replace(hour=11),
                    price=price,
                    mrp=MRP_128,
                    availability=AvailabilityStatus.IN_STOCK,
                    seller_id=seller_by_letter[letter],
                )
            )

    session.add(
        SaleEvent(
            name="DEVELOPMENT FIXTURE: Demo Retailer C Weekend Promo",
            event_type=SaleEventType.RETAILER_SPECIFIC,
            source=SaleEventSource.MANUAL_CURATION,
            source_ref=SOURCE_REF,
            confidence=ConfidenceLevel.MEDIUM,
            retailer=retailer_c,
            start_date=now + timedelta(days=4),
            end_date=now + timedelta(days=5),
        )
    )

    session.commit()
    return product


def main() -> None:
    session = SessionLocal()
    try:
        product = seed(session)
        print(
            "Seeded DEVELOPMENT / TEST FIXTURE data for Phase 19 local verification "
            f"(product_id={product.id}, slug={product.slug}). "
            "Six fictional Demo Retailer identities share the 128GB variant; "
            "prices are invented and are not live retailer observations."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
