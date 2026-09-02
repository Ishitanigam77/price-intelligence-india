"""Integration tests for `GET /api/v1/products/{product_id}/prices`."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.enums import (
    AdjustmentEligibility,
    AdjustmentKind,
    AvailabilityStatus,
    ConfidenceLevel,
)
from tests.factories import (
    make_price_adjustment,
    make_price_snapshot,
    make_product,
    make_retailer,
    make_retailer_product,
    make_seller,
    make_variant,
)


def _seed_catalogue(db_session: Session):
    product = make_product(name="Fictional Phone X", slug=f"phone-{uuid.uuid4().hex[:8]}")
    variant_128 = make_variant(product, attributes={"storage": "128GB", "color": "Black"})
    variant_256 = make_variant(product, attributes={"storage": "256GB", "color": "Black"})
    retailer_a = make_retailer(name="Fictional Mart A", slug=f"mart-a-{uuid.uuid4().hex[:6]}")
    retailer_b = make_retailer(name="Fictional Mart B", slug=f"mart-b-{uuid.uuid4().hex[:6]}")
    retailer_c = make_retailer(name="Fictional Mart C", slug=f"mart-c-{uuid.uuid4().hex[:6]}")
    db_session.add_all([variant_128, variant_256, retailer_a, retailer_b, retailer_c])
    db_session.flush()
    seller_a = make_seller(retailer_a, name="Fictional Seller A", is_first_party=True)
    seller_b = make_seller(retailer_b, name="Fictional Seller B", is_first_party=False)
    db_session.add_all([seller_a, seller_b])
    db_session.flush()
    listing_a = make_retailer_product(
        variant_128, retailer_a, retailer_sku="SKU-A-128", url="https://fictional-a.example.test/a"
    )
    listing_b = make_retailer_product(
        variant_128, retailer_b, retailer_sku="SKU-B-128", url="https://fictional-b.example.test/b"
    )
    listing_c = make_retailer_product(
        variant_128, retailer_c, retailer_sku="SKU-C-128", url="https://fictional-c.example.test/c"
    )
    listing_256 = make_retailer_product(
        variant_256,
        retailer_a,
        retailer_sku="SKU-A-256",
        url="https://fictional-a.example.test/256",
    )
    listing_no_obs = make_retailer_product(
        variant_128,
        retailer_a,
        retailer_sku="SKU-A-128-EMPTY",
        url="https://fictional-a.example.test/empty",
    )
    db_session.add_all([listing_a, listing_b, listing_c, listing_256, listing_no_obs])
    db_session.flush()
    return {
        "product": product,
        "variant_128": variant_128,
        "variant_256": variant_256,
        "retailer_a": retailer_a,
        "retailer_b": retailer_b,
        "retailer_c": retailer_c,
        "seller_a": seller_a,
        "seller_b": seller_b,
        "listing_a": listing_a,
        "listing_b": listing_b,
        "listing_c": listing_c,
        "listing_256": listing_256,
        "listing_no_obs": listing_no_obs,
    }


def test_unknown_product_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/products/{uuid.uuid4()}/prices")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_product_with_no_offers_returns_empty_comparison(
    client: TestClient, db_session: Session
) -> None:
    product = make_product(slug=f"empty-{uuid.uuid4().hex[:8]}")
    db_session.add(make_variant(product))
    db_session.flush()

    response = client.get(f"/api/v1/products/{product.id}/prices")
    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == str(product.id)
    assert len(body["variants"]) == 1
    variant = body["variants"][0]
    assert variant["offers"] == []
    assert variant["lowest_verified_offer"] is None
    assert variant["ranking_reason"]["criterion"] == "no_applicable_offer"
    assert variant["data_freshness"]["status"] == "missing"


def test_compares_multiple_retailers_sellers_and_keeps_variants_separate(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed_catalogue(db_session)
    now = datetime.now(UTC)
    snap_a = make_price_snapshot(
        seed["listing_a"],
        displayed_price=Decimal("1000.00"),
        mrp=Decimal("1200.00"),
        delivery_fee=Decimal("40.00"),
        platform_fee=Decimal("10.00"),
        observed_at=now - timedelta(hours=1),
        availability=AvailabilityStatus.IN_STOCK,
        confidence=ConfidenceLevel.HIGH,
        seller=seed["seller_a"],
        source_url="https://fictional-a.example.test/a",
    )
    snap_b = make_price_snapshot(
        seed["listing_b"],
        displayed_price=Decimal("950.00"),
        mrp=Decimal("1200.00"),
        observed_at=now - timedelta(hours=2),
        availability=AvailabilityStatus.IN_STOCK,
        confidence=ConfidenceLevel.HIGH,
        seller=seed["seller_b"],
        source_url="https://fictional-b.example.test/b",
    )
    snap_c = make_price_snapshot(
        seed["listing_c"],
        displayed_price=Decimal("100.00"),
        observed_at=now - timedelta(days=4),
        availability=AvailabilityStatus.OUT_OF_STOCK,
        confidence=ConfidenceLevel.MEDIUM,
        source_url="https://fictional-c.example.test/c",
    )
    snap_256 = make_price_snapshot(
        seed["listing_256"],
        displayed_price=Decimal("50.00"),
        observed_at=now,
        availability=AvailabilityStatus.IN_STOCK,
        seller=seed["seller_a"],
        source_url="https://fictional-a.example.test/256",
    )
    db_session.add_all([snap_a, snap_b, snap_c, snap_256])
    db_session.flush()
    db_session.add(
        make_price_adjustment(
            snap_a,
            kind=AdjustmentKind.COUPON,
            amount=Decimal("80.00"),
            eligibility=AdjustmentEligibility.VERIFIED_ELIGIBLE,
            source="test.verified_coupon",
        )
    )
    db_session.add(
        make_price_adjustment(
            snap_b,
            kind=AdjustmentKind.CASHBACK,
            amount=Decimal("200.00"),
            eligibility=AdjustmentEligibility.UNVERIFIED,
            source="test.unverified_cashback",
        )
    )
    db_session.flush()

    response = client.get(f"/api/v1/products/{seed['product'].id}/prices")
    assert response.status_code == 200
    body = response.json()
    variants = {item["variant_id"]: item for item in body["variants"]}
    v128 = variants[str(seed["variant_128"].id)]
    v256 = variants[str(seed["variant_256"].id)]

    offer_ids = {item["offer_id"] for item in v128["offers"]}
    assert str(snap_256.id) not in offer_ids
    assert v256["lowest_verified_offer"]["offer_id"] == str(snap_256.id)
    assert Decimal(v256["lowest_verified_offer"]["displayed_price"]) == Decimal("50.00")

    winner = v128["lowest_verified_offer"]
    assert winner is not None
    # Verified coupon on A: 1000 - 80 + 40 + 10 = 970. B displayed 950 (cashback not applied).
    assert winner["offer_id"] == str(snap_b.id)
    assert Decimal(winner["effective_price"]) == Decimal("950.00")
    b_offer = next(item for item in v128["offers"] if item["offer_id"] == str(snap_b.id))
    assert Decimal(b_offer["unverified_estimated_price"]) == Decimal("750.00")
    assert b_offer["unverified_price_kind"] == "estimated_unverified"
    assert b_offer["cashback"] == "200.00" or Decimal(b_offer["cashback"]) == Decimal("200.00")

    a_offer = next(item for item in v128["offers"] if item["offer_id"] == str(snap_a.id))
    assert Decimal(a_offer["effective_price"]) == Decimal("970.00")
    assert Decimal(a_offer["coupon_discount"]) == Decimal("80.00")
    assert Decimal(a_offer["discount_percentage"]) == Decimal("16.67")
    assert a_offer["price_kind"] == "verified_effective"
    coupon = next(item for item in a_offer["adjustments"] if item["kind"] == "coupon")
    assert coupon["source"] == "test.verified_coupon"
    assert coupon["eligibility"] == "verified_eligible"
    assert coupon["affects_effective_price"] is True
    assert coupon["observed_at"]

    oos = next(item for item in v128["offers"] if item["offer_id"] == str(snap_c.id))
    assert oos["can_win_verified_ranking"] is False
    assert oos["availability"] == "out_of_stock"
    assert oos["freshness"]["status"] == "stale"

    missing = next(item for item in v128["offers"] if item["offer_id"].startswith("listing:"))
    assert missing["displayed_price"] is None
    assert missing["freshness"]["status"] == "missing"
    assert missing["can_win_verified_ranking"] is False

    retailers = {item["retailer_id"] for item in v128["offers"]}
    assert str(seed["retailer_a"].id) in retailers
    assert str(seed["retailer_b"].id) in retailers
    assert str(seed["retailer_c"].id) in retailers
    assert v128["offer_count"] == len(v128["offers"])
    assert v128["distinct_retailer_count"] == len(retailers)
    assert v128["displayed_price_min"] is not None
    assert v128["displayed_price_max"] is not None
    assert Decimal(v128["displayed_price_min"]) <= Decimal(v128["displayed_price_max"])

    assert v128["ranking_reason"]["reason"]
    assert v128["data_freshness"]["stale_offer_count"] >= 1
    assert v128["data_freshness"]["missing_observation_count"] >= 1
    assert body["lowest_verified_offer"] is None  # multiple variants: never combined
    assert a_offer["source_url"] == "https://fictional-a.example.test/a"
    assert a_offer["seller"]["is_first_party"] is True
    assert b_offer["seller"]["is_first_party"] is False


def test_ineligible_coupon_does_not_reduce_api_effective_price(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed_catalogue(db_session)
    now = datetime.now(UTC)
    snap = make_price_snapshot(
        seed["listing_a"],
        displayed_price=Decimal("800.00"),
        observed_at=now,
        seller=seed["seller_a"],
    )
    db_session.add(snap)
    db_session.flush()
    db_session.add(
        make_price_adjustment(
            snap,
            kind=AdjustmentKind.COUPON,
            amount=Decimal("400.00"),
            eligibility=AdjustmentEligibility.INELIGIBLE,
            source="test.ineligible_coupon",
        )
    )
    db_session.add(
        make_price_adjustment(
            snap,
            kind=AdjustmentKind.PAYMENT_DISCOUNT,
            amount=Decimal("50.00"),
            eligibility=AdjustmentEligibility.PAYMENT_METHOD_SPECIFIC,
            source="test.card_offer",
        )
    )
    db_session.flush()

    response = client.get(f"/api/v1/products/{seed['product'].id}/prices")
    assert response.status_code == 200
    v128 = next(
        item
        for item in response.json()["variants"]
        if item["variant_id"] == str(seed["variant_128"].id)
    )
    offer = next(item for item in v128["offers"] if item["offer_id"] == str(snap.id))
    assert Decimal(offer["effective_price"]) == Decimal("800.00")
    assert Decimal(offer["coupon_discount"]) == Decimal("400.00")
    assert Decimal(offer["payment_discount"]) == Decimal("50.00")
    coupon = next(item for item in offer["adjustments"] if item["kind"] == "coupon")
    assert coupon["eligibility"] == "ineligible"
    assert coupon["affects_effective_price"] is False
    payment = next(item for item in offer["adjustments"] if item["kind"] == "payment_discount")
    assert payment["eligibility"] == "payment_method_specific"
    assert payment["affects_effective_price"] is False
