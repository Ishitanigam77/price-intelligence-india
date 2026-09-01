"""Integration tests for `GET /api/v1/products/{product_id}/sale-intelligence`."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.enums import SaleEventSource, SaleEventType
from tests.factories import (
    make_brand,
    make_category,
    make_price_snapshot,
    make_product,
    make_retailer,
    make_retailer_product,
    make_sale_event,
    make_seller,
    make_variant,
)


def _seed(db_session: Session) -> dict[str, object]:
    brand = make_brand()
    category = make_category()
    product = make_product(
        name="Fictional Phone Intel",
        slug=f"intel-{uuid.uuid4().hex[:8]}",
        brand=brand,
        category=category,
    )
    variant = make_variant(product, attributes={"storage": "128GB", "color": "Black"})
    retailer = make_retailer()
    db_session.add_all([brand, category, variant, retailer])
    db_session.flush()
    seller = make_seller(retailer, name="Fictional Seller", is_first_party=True)
    listing = make_retailer_product(
        variant,
        retailer,
        retailer_sku=f"INT-{uuid.uuid4().hex[:6]}",
        url="https://fictional.example.test/intel-128",
    )
    db_session.add_all([seller, listing])
    db_session.flush()
    now = datetime.now(UTC)
    db_session.add(
        make_price_snapshot(
            listing,
            displayed_price=Decimal("50000.00"),
            effective_price=Decimal("50000.00"),
            observed_at=now - timedelta(hours=1),
            seller_id=seller.id,
        )
    )
    for year in (now.year - 2, now.year - 1):
        start = datetime(year, 3, 15, tzinfo=UTC)
        db_session.add(
            make_sale_event(
                name=f"FIXTURE: Mid-March Sale {year}",
                event_type=SaleEventType.SEASONAL,
                source=SaleEventSource.MANUAL_CURATION,
                start_date=start,
                end_date=start + timedelta(days=3),
                brand=brand,
                category=category,
            )
        )
        db_session.add(
            make_price_snapshot(
                listing,
                displayed_price=Decimal("43000.00"),
                effective_price=Decimal("43000.00"),
                observed_at=start + timedelta(days=1),
                seller_id=seller.id,
            )
        )
    db_session.flush()
    return {"product": product, "variant": variant, "retailer": retailer}


def test_unknown_product_sale_intelligence_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/products/{uuid.uuid4()}/sale-intelligence")
    assert response.status_code == 404


def test_sale_intelligence_returns_current_and_calendar(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed(db_session)
    response = client.get(f"/api/v1/products/{seed['product'].id}/sale-intelligence")
    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == str(seed["product"].id)
    assert "not guaranteed retailer announcements" in body["disclaimer"].lower()
    assert body["predicted"] is None
    assert len(body["variants"]) == 1
    variant = body["variants"][0]
    assert variant["product_variant_id"] == str(seed["variant"].id)
    assert variant["current_cheapest_retailer_id"] == str(seed["retailer"].id)
    assert Decimal(variant["current_cheapest_price"]) == Decimal("50000.00")
    assert variant["calendar"]
    for window in variant["calendar"]:
        assert window["evidence_status"] in {"confirmed", "expected", "inferred", "unknown"}
        if window["evidence_status"] != "confirmed":
            assert window["mapping_method"] != "confirmed_schedule" or window["expected_start_date"]
    assert variant["predicted"] is None
