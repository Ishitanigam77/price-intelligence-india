"""Integration tests for `GET /api/v1/products/{product_id}/history` and persistence."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.enums import AvailabilityStatus, ConfidenceLevel
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from tests.factories import (
    make_price_snapshot,
    make_product,
    make_retailer,
    make_retailer_product,
    make_seller,
    make_variant,
)


def _seed(db_session: Session):
    product = make_product(name="Fictional Phone X", slug=f"hist-{uuid.uuid4().hex[:8]}")
    variant_128 = make_variant(product, attributes={"storage": "128GB", "color": "Black"})
    variant_256 = make_variant(product, attributes={"storage": "256GB", "color": "Black"})
    retailer_a = make_retailer(name="Fictional Mart A", slug=f"hist-a-{uuid.uuid4().hex[:6]}")
    retailer_b = make_retailer(name="Fictional Mart B", slug=f"hist-b-{uuid.uuid4().hex[:6]}")
    db_session.add_all([variant_128, variant_256, retailer_a, retailer_b])
    db_session.flush()
    seller_a = make_seller(retailer_a, name="Fictional Seller A", is_first_party=True)
    seller_b = make_seller(retailer_b, name="Fictional Seller B", is_first_party=False)
    db_session.add_all([seller_a, seller_b])
    db_session.flush()
    listing_a = make_retailer_product(
        variant_128, retailer_a, retailer_sku="HIST-A-128", url="https://fictional-a.example.test/a"
    )
    listing_b = make_retailer_product(
        variant_128, retailer_b, retailer_sku="HIST-B-128", url="https://fictional-b.example.test/b"
    )
    listing_256 = make_retailer_product(
        variant_256,
        retailer_a,
        retailer_sku="HIST-A-256",
        url="https://fictional-a.example.test/256",
    )
    db_session.add_all([listing_a, listing_b, listing_256])
    db_session.flush()
    return {
        "product": product,
        "variant_128": variant_128,
        "variant_256": variant_256,
        "retailer_a": retailer_a,
        "retailer_b": retailer_b,
        "seller_a": seller_a,
        "seller_b": seller_b,
        "listing_a": listing_a,
        "listing_b": listing_b,
        "listing_256": listing_256,
    }


def test_unknown_product_history_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/products/{uuid.uuid4()}/history")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_unknown_variant_on_known_product_returns_404(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed(db_session)
    response = client.get(
        f"/api/v1/products/{seed['product'].id}/history",
        params={"variant_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_new_observation_does_not_overwrite_previous_ones(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed(db_session)
    now = datetime.now(UTC)
    first = make_price_snapshot(
        seed["listing_a"],
        displayed_price=Decimal("200.00"),
        observed_at=now - timedelta(days=2),
        seller=seed["seller_a"],
        source_url="https://fictional-a.example.test/a",
        confidence=ConfidenceLevel.HIGH,
    )
    second = make_price_snapshot(
        seed["listing_a"],
        displayed_price=Decimal("150.00"),
        observed_at=now - timedelta(hours=1),
        seller=seed["seller_a"],
        source_url="https://fictional-a.example.test/a",
        confidence=ConfidenceLevel.HIGH,
    )
    db_session.add_all([first, second])
    db_session.flush()

    repo = PriceSnapshotRepository(db_session)
    history = repo.history_for_product(seed["product"].id, variant_id=seed["variant_128"].id)
    assert len(history) == 2
    assert [snap.displayed_price for snap in history] == [Decimal("200.00"), Decimal("150.00")]
    assert first.id != second.id
    # Original row is unchanged.
    assert db_session.get(type(first), first.id).displayed_price == Decimal("200.00")


def test_history_api_returns_observations_and_calculated_aggregates(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed(db_session)
    now = datetime.now(UTC)
    snapshots = [
        make_price_snapshot(
            seed["listing_a"],
            displayed_price=Decimal("400.00"),
            observed_at=now - timedelta(days=40),
            seller=seed["seller_a"],
            source_url="https://fictional-a.example.test/a",
        ),
        make_price_snapshot(
            seed["listing_a"],
            displayed_price=Decimal("300.00"),
            observed_at=now - timedelta(days=10),
            seller=seed["seller_a"],
            source_url="https://fictional-a.example.test/a",
        ),
        make_price_snapshot(
            seed["listing_a"],
            displayed_price=Decimal("200.00"),
            observed_at=now - timedelta(days=3),
            seller=seed["seller_a"],
            source_url="https://fictional-a.example.test/a",
        ),
        make_price_snapshot(
            seed["listing_a"],
            displayed_price=Decimal("100.00"),
            observed_at=now - timedelta(hours=1),
            seller=seed["seller_a"],
            source_url="https://fictional-a.example.test/a-current",
            availability=AvailabilityStatus.IN_STOCK,
            confidence=ConfidenceLevel.HIGH,
        ),
        make_price_snapshot(
            seed["listing_b"],
            displayed_price=Decimal("180.00"),
            observed_at=now - timedelta(hours=2),
            seller=seed["seller_b"],
            source_url="https://fictional-b.example.test/b",
        ),
        make_price_snapshot(
            seed["listing_256"],
            displayed_price=Decimal("50.00"),
            observed_at=now - timedelta(hours=1),
            seller=seed["seller_a"],
            source_url="https://fictional-a.example.test/256",
        ),
        make_price_snapshot(
            seed["listing_a"],
            displayed_price=Decimal("1.00"),
            observed_at=now - timedelta(hours=3),
            seller=seed["seller_a"],
            confidence=ConfidenceLevel.LOW,
            source_url="https://fictional-a.example.test/unverified",
        ),
    ]
    db_session.add_all(snapshots)
    db_session.flush()

    response = client.get(f"/api/v1/products/{seed['product'].id}/history")
    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == str(seed["product"].id)
    assert body["predicted"] is None
    assert body["provenance"]["observations_value_kind"] == "OBSERVED"
    assert body["provenance"]["calculations_value_kind"] == "CALCULATED"
    assert body["provenance"]["predicted"] is None
    assert "PREDICTED" not in str(body["variants"][0]["average_7d"])

    by_variant = {item["product_variant_id"]: item for item in body["variants"]}
    v128 = by_variant[str(seed["variant_128"].id)]
    v256 = by_variant[str(seed["variant_256"].id)]

    prices_128 = [Decimal(item["displayed_price"]) for item in v128["observations"]["items"]]
    assert Decimal("50.00") not in prices_128
    assert Decimal("1.00") in prices_128
    assert v128["excluded_unverified_observation_count"] == 1
    assert v128["qualifying_observation_count"] == 5

    assert v128["average_7d"]["status"] == "available"
    assert Decimal(v128["average_7d"]["value"]) == Decimal("160.00")
    assert v128["average_7d"]["value_kind"] == "CALCULATED"
    assert v128["average_30d"]["status"] == "available"
    assert Decimal(v128["average_30d"]["value"]) == Decimal("195.00")
    assert v128["average_90d"]["status"] == "available"
    assert v128["average_180d"]["status"] == "available"

    assert Decimal(v128["historical_low"]["value"]) == Decimal("100.00")
    assert Decimal(v128["historical_high"]["value"]) == Decimal("400.00")
    assert v128["current_price_percentile"]["status"] == "available"
    assert v128["volatility"]["status"] == "available"
    assert v128["percentage_change"]["status"] == "available"
    assert v128["price_drop"]["drop_occurred"] is True
    assert "retailer listing" in v128["price_drop"]["baseline_description"]
    assert v128["trend"]["value_kind"] == "CALCULATED"
    assert v128["trend"]["direction"] in {"falling", "rising", "stable"}
    assert v128["monthly"]["value_kind"] == "CALCULATED"
    assert len(v128["monthly"]["months"]) == 12
    assert v128["monthly"]["predicted"] is None
    assert v128["data_freshness"]["newest_observation"] is not None
    assert v128["data_freshness"]["as_of"] == body["calculated_at"]

    retailers = {item["retailer_id"] for item in v128["observations"]["items"]}
    assert str(seed["retailer_a"].id) in retailers
    assert str(seed["retailer_b"].id) in retailers
    sellers = {item["seller_id"] for item in v128["observations"]["items"]}
    assert str(seed["seller_a"].id) in sellers
    assert str(seed["seller_b"].id) in sellers

    assert Decimal(v256["historical_low"]["value"]) == Decimal("50.00")
    assert Decimal(v256["historical_high"]["value"]) == Decimal("50.00")
    assert v256["price_drop"]["status"] == "insufficient_history"
    assert v256["volatility"]["status"] == "insufficient_history"


def test_history_observation_pagination(client: TestClient, db_session: Session) -> None:
    seed = _seed(db_session)
    now = datetime.now(UTC)
    for index in range(5):
        db_session.add(
            make_price_snapshot(
                seed["listing_a"],
                displayed_price=Decimal("100.00") + Decimal(index),
                observed_at=now - timedelta(days=5 - index),
                seller=seed["seller_a"],
                source_url="https://fictional-a.example.test/a",
            )
        )
    db_session.flush()

    response = client.get(
        f"/api/v1/products/{seed['product'].id}/history",
        params={"variant_id": str(seed["variant_128"].id), "limit": 2, "offset": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["variants"]) == 1
    page = body["variants"][0]["observations"]
    assert page["total"] == 5
    assert page["limit"] == 2
    assert page["offset"] == 1
    assert len(page["items"]) == 2
    # Calculations still see the full history, not the page window.
    assert body["variants"][0]["qualifying_observation_count"] == 5
    assert body["variants"][0]["historical_high"]["status"] == "available"


def test_missing_observations_do_not_return_zero_averages(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed(db_session)
    response = client.get(f"/api/v1/products/{seed['product'].id}/history")
    assert response.status_code == 200
    body = response.json()
    variant = body["variants"][0]
    assert variant["observations"]["items"] == []
    assert variant["average_7d"]["value"] is None
    assert variant["average_7d"]["status"] == "insufficient_history"
    assert variant["average_7d"]["insufficient"]["code"] == "no_observations_in_window"
    assert variant["historical_low"]["value"] is None
    assert variant["data_freshness"]["status"] == "missing"
    assert variant["data_freshness"]["newest_observation"] is None
    assert body["predicted"] is None
