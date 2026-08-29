"""Integration tests for `GET /api/v1/products/{product_id}/sale-history`."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.enums import ConfidenceLevel, SaleEventType
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


def _seed_product(db_session: Session) -> dict[str, object]:
    brand = make_brand()
    category = make_category()
    product = make_product(
        name="Fictional Phone X",
        slug=f"sale-hist-{uuid.uuid4().hex[:8]}",
        brand=brand,
        category=category,
    )
    variant = make_variant(product, attributes={"storage": "128GB", "color": "Black"})
    other_variant = make_variant(product, attributes={"storage": "256GB", "color": "Black"})
    retailer = make_retailer()
    db_session.add_all([brand, category, variant, other_variant, retailer])
    db_session.flush()
    seller = make_seller(retailer, name="Fictional Seller", is_first_party=True)
    listing = make_retailer_product(
        variant,
        retailer,
        retailer_sku="SALE-128",
        url="https://fictional.example.test/sale-128",
    )
    other_listing = make_retailer_product(
        other_variant,
        retailer,
        retailer_sku="SALE-256",
        url="https://fictional.example.test/sale-256",
    )
    db_session.add_all([seller, listing, other_listing])
    db_session.flush()
    return {
        "product": product,
        "variant": variant,
        "other_variant": other_variant,
        "retailer": retailer,
        "seller": seller,
        "listing": listing,
        "other_listing": other_listing,
        "brand": brand,
        "category": category,
    }


def test_unknown_product_sale_history_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/products/{uuid.uuid4()}/sale-history")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_sale_history_without_events_is_insufficient_not_fabricated(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed_product(db_session)
    now = datetime.now(UTC)
    db_session.add(
        make_price_snapshot(
            seed["listing"],
            displayed_price=Decimal("500.00"),
            observed_at=now - timedelta(days=2),
            seller=seed["seller"],
            source_url="https://fictional.example.test/sale-128",
        )
    )
    db_session.flush()
    response = client.get(f"/api/v1/products/{seed['product'].id}/sale-history")
    assert response.status_code == 200
    body = response.json()
    assert body["predicted"] is None
    assert body["events"] == []
    assert body["provenance"]["observations_value_kind"] == "OBSERVED"
    assert body["provenance"]["calculations_value_kind"] == "CALCULATED"
    assert body["provenance"]["predicted"] is None
    variant = body["variants"][0]
    assert variant["overall_sale_average"]["status"] == "insufficient_history"
    assert variant["overall_sale_average"]["value"] is None
    assert variant["overall_sale_average"]["insufficient"]["code"] == "no_applicable_events"


def test_sale_history_uses_observed_in_window_prices(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed_product(db_session)
    now = datetime.now(UTC)
    event = make_sale_event(
        name="FIXTURE: Fictional Product Sale Window",
        event_type=SaleEventType.SEASONAL,
        start_date=now - timedelta(days=5),
        end_date=now - timedelta(days=1),
    )
    db_session.add(event)
    snapshots = [
        make_price_snapshot(
            seed["listing"],
            displayed_price=Decimal("1000.00"),
            observed_at=now - timedelta(days=12),
            seller=seed["seller"],
            source_url="https://fictional.example.test/sale-128",
        ),
        make_price_snapshot(
            seed["listing"],
            displayed_price=Decimal("700.00"),
            observed_at=now - timedelta(days=4),
            seller=seed["seller"],
            source_url="https://fictional.example.test/sale-128",
        ),
        make_price_snapshot(
            seed["listing"],
            displayed_price=Decimal("500.00"),
            observed_at=now - timedelta(days=2),
            seller=seed["seller"],
            source_url="https://fictional.example.test/sale-128",
        ),
        make_price_snapshot(
            seed["other_listing"],
            displayed_price=Decimal("800.00"),
            observed_at=now - timedelta(days=3),
            seller=seed["seller"],
            source_url="https://fictional.example.test/sale-256",
        ),
        make_price_snapshot(
            seed["listing"],
            displayed_price=Decimal("50.00"),
            observed_at=now - timedelta(days=3),
            seller=seed["seller"],
            source_url="https://fictional.example.test/sale-128-unverified",
            confidence=ConfidenceLevel.LOW,
        ),
    ]
    db_session.add_all(snapshots)
    db_session.flush()

    response = client.get(f"/api/v1/products/{seed['product'].id}/sale-history")
    assert response.status_code == 200
    body = response.json()
    assert body["predicted"] is None
    assert len(body["events"]) == 1
    assert body["events"][0]["name"] == "FIXTURE: Fictional Product Sale Window"
    by_variant = {item["product_variant_id"]: item for item in body["variants"]}
    variant_128 = by_variant[str(seed["variant"].id)]
    variant_256 = by_variant[str(seed["other_variant"].id)]
    assert variant_128["overall_sale_average"]["value"] == "600.00"
    assert variant_128["overall_sale_low"]["value"] == "500.00"
    assert variant_128["overall_sale_high"]["value"] == "700.00"
    assert variant_128["excluded_unverified_observation_count"] == 1
    window = variant_128["event_windows"][0]
    assert all(obs["value_kind"] == "OBSERVED" for obs in window["observations"]["items"])
    assert all(obs["displayed_price"] != "50.00" for obs in window["observations"]["items"])
    assert variant_256["overall_sale_average"]["value"] == "800.00"
    assert (
        variant_128["overall_sale_average"]["value"] != variant_256["overall_sale_average"]["value"]
    )


def test_sale_history_unknown_variant_returns_404(client: TestClient, db_session: Session) -> None:
    seed = _seed_product(db_session)
    response = client.get(
        f"/api/v1/products/{seed['product'].id}/sale-history",
        params={"variant_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404
