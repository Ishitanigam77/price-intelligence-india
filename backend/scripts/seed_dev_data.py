"""Seed clearly-fake development data for manually validating the Phase 1 schema.

This is a *development-only* convenience script, not a fixture used by the automated test
suite (see `backend/tests/factories.py` for that). Every name, retailer, SKU, and price below is
invented for this seed script — none of it comes from, or represents, a real retailer, per
`DEVELOPMENT_RULES.md` §3 ("never fabricate ... retailer data" — which applies to code that
claims to represent real retailers; this data is explicitly fictional and labeled as such).

Usage (from `backend/`, with `DATABASE_URL` pointing at a dev database):

    python -m scripts.seed_dev_data
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

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


def seed(session: Session) -> None:
    electronics = Category(name="Electronics", slug="electronics")
    mobiles = Category(name="Mobiles", slug="electronics-mobiles", parent=electronics)
    session.add_all([electronics, mobiles])

    brand = Brand(
        name="Fictional Orchard",
        slug="fictional-orchard",
        description="A made-up brand used only to validate the Phase 1 schema.",
    )
    session.add(brand)

    product = Product(
        name="Fictional Orchard Phone Z (fake, for schema validation only)",
        slug="fictional-orchard-phone-z",
        brand=brand,
        category=mobiles,
        description="Not a real product. Seeded purely to exercise the Phase 1 domain model.",
    )
    session.add(product)

    variant_128gb = ProductVariant(
        product=product,
        name="128GB / Midnight",
        attributes={"storage": "128GB", "color": "Midnight"},
    )
    variant_256gb = ProductVariant(
        product=product,
        name="256GB / Midnight",
        attributes={"storage": "256GB", "color": "Midnight"},
    )
    session.add_all([variant_128gb, variant_256gb])

    session.add(
        ProductIdentifier(
            product_variant=variant_128gb,
            identifier_type=ProductIdentifierType.GTIN,
            value="0000000000128",
        )
    )
    session.add(
        ProductIdentifier(
            product_variant=variant_256gb,
            identifier_type=ProductIdentifierType.GTIN,
            value="0000000000256",
        )
    )

    retailer_large = Retailer(
        name="Fictional Big Mart",
        slug="fictional-big-mart",
        website_url="https://fictional-big-mart.example.test",
    )
    retailer_small = Retailer(
        name="Fictional Local Store",
        slug="fictional-local-store",
        website_url="https://fictional-local-store.example.test",
    )
    session.add_all([retailer_large, retailer_small])

    first_party_seller = Seller(
        retailer=retailer_large, name="Fictional Big Mart", is_first_party=True
    )
    third_party_seller = Seller(retailer=retailer_large, name="Fictional Third-Party Seller Co.")
    session.add_all([first_party_seller, third_party_seller])

    rp_large_128gb = RetailerProduct(
        product_variant=variant_128gb,
        retailer=retailer_large,
        retailer_sku="FBM-128-MID",
        url="https://fictional-big-mart.example.test/listing/fbm-128-mid",
    )
    rp_small_128gb = RetailerProduct(
        product_variant=variant_128gb,
        retailer=retailer_small,
        retailer_sku="FLS-128",
        url="https://fictional-local-store.example.test/listing/fls-128",
    )
    rp_large_256gb = RetailerProduct(
        product_variant=variant_256gb,
        retailer=retailer_large,
        retailer_sku="FBM-256-MID",
        url="https://fictional-big-mart.example.test/listing/fbm-256-mid",
    )
    session.add_all([rp_large_128gb, rp_small_128gb, rp_large_256gb])
    session.flush()

    now = datetime.now(UTC)
    price_history = [
        (now - timedelta(days=6), Decimal("64999.00"), None),
        (now - timedelta(days=4), Decimal("62999.00"), None),
        (now - timedelta(days=2), Decimal("59999.00"), third_party_seller.id),
        (now, Decimal("59999.00"), None),
    ]
    for observed_at, price, seller_id in price_history:
        session.add(
            PriceSnapshot(
                retailer_product=rp_large_128gb,
                seller_id=seller_id,
                observed_at=observed_at,
                mrp=Decimal("69999.00"),
                displayed_price=price,
                availability=AvailabilityStatus.IN_STOCK,
                source_type=SourceType.PRODUCT_FEED,
                source_url=rp_large_128gb.url,
                confidence=ConfidenceLevel.HIGH,
            )
        )

    session.add(
        PriceSnapshot(
            retailer_product=rp_small_128gb,
            observed_at=now,
            mrp=Decimal("69999.00"),
            displayed_price=Decimal("61499.00"),
            availability=AvailabilityStatus.LIMITED_STOCK,
            source_type=SourceType.OTHER_PERMITTED,
            source_url=rp_small_128gb.url,
            confidence=ConfidenceLevel.MEDIUM,
        )
    )
    session.add(
        PriceSnapshot(
            retailer_product=rp_large_256gb,
            observed_at=now,
            mrp=Decimal("74999.00"),
            displayed_price=Decimal("67999.00"),
            availability=AvailabilityStatus.OUT_OF_STOCK,
            source_type=SourceType.PRODUCT_FEED,
            source_url=rp_large_256gb.url,
            confidence=ConfidenceLevel.HIGH,
        )
    )

    session.add(
        SaleEvent(
            name="FIXTURE: Fictional Past Seasonal Sale (seed data only)",
            event_type=SaleEventType.SEASONAL,
            source=SaleEventSource.MANUAL_CURATION,
            source_ref="test.fixture.seed",
            confidence=ConfidenceLevel.HIGH,
            start_date=now - timedelta(days=20),
            end_date=now - timedelta(days=14),
        )
    )
    session.add(
        SaleEvent(
            name="FIXTURE: Fictional Current Retailer Sale (seed data only)",
            event_type=SaleEventType.RETAILER_SPECIFIC,
            source=SaleEventSource.MANUAL_CURATION,
            source_ref="test.fixture.seed",
            confidence=ConfidenceLevel.MEDIUM,
            retailer=retailer_large,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=3),
        )
    )
    session.add(
        SaleEvent(
            name="FIXTURE: Fictional Upcoming Brand Sale (seed data only)",
            event_type=SaleEventType.BRAND,
            source=SaleEventSource.MANUAL_CURATION,
            source_ref="test.fixture.seed",
            confidence=ConfidenceLevel.HIGH,
            brand=brand,
            start_date=now + timedelta(days=10),
            end_date=now + timedelta(days=14),
        )
    )

    session.commit()


def main() -> None:
    session = SessionLocal()
    try:
        seed(session)
        print(
            "Seeded fake development data for schema validation (including fictional sale events)."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
