"""Integration tests for `GET /api/v1/products/{product_id}/recommendation`."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def _seed_listing(db_session: Session, *, slug_prefix: str) -> dict[str, object]:
    brand = make_brand()
    category = make_category()
    product = make_product(
        name="Fictional Phone Rec",
        slug=f"{slug_prefix}-{uuid.uuid4().hex[:8]}",
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
        retailer_sku=f"REC-{uuid.uuid4().hex[:6]}",
        url="https://fictional.example.test/rec-128",
    )
    db_session.add_all([seller, listing])
    db_session.flush()
    return {
        "product": product,
        "variant": variant,
        "listing": listing,
        "seller": seller,
        "brand": brand,
        "category": category,
    }


def _add_snapshots(
    db_session: Session,
    listing,
    *,
    prices: list[str],
    seller_id,
    newest_age_hours: float = 1.0,
    step_hours: float = 1.0,
) -> None:
    now = datetime.now(UTC)
    for index, price in enumerate(reversed(prices)):
        age = newest_age_hours + index * step_hours
        db_session.add(
            make_price_snapshot(
                listing,
                displayed_price=Decimal(price),
                effective_price=Decimal(price),
                observed_at=now - timedelta(hours=age),
                seller_id=seller_id,
            )
        )
    db_session.flush()


def test_unknown_product_recommendation_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/products/{uuid.uuid4()}/recommendation")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_recommendation_without_history_is_insufficient_not_fabricated(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed_listing(db_session, slug_prefix="rec-empty")
    product = seed["product"]
    response = client.get(f"/api/v1/products/{product.id}/recommendation")
    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == str(product.id)
    assert "not a guarantee" in body["disclaimer"].lower()
    assert len(body["variants"]) == 1
    variant = body["variants"][0]
    assert variant["recommendation"] == "INSUFFICIENT_DATA"
    assert variant["expected_saving"] is None
    assert variant["reasons"]
    assert variant["evidence"]["current_effective_price"] is None
    assert variant["evidence"]["predicted_sale_price"] is None


def test_recommendation_buy_now_from_favorable_fresh_history(
    client: TestClient, db_session: Session, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("ML_MODEL_ARTIFACT_PATH", str(tmp_path))
    from ml.config import get_ml_config

    get_ml_config.cache_clear()
    seed = _seed_listing(db_session, slug_prefix="rec-buy")
    _add_snapshots(
        db_session,
        seed["listing"],
        prices=["200.00", "180.00", "160.00", "140.00", "100.00"],
        seller_id=seed["seller"].id,
        newest_age_hours=1.0,
        step_hours=1.0,
    )
    response = client.get(f"/api/v1/products/{seed['product'].id}/recommendation")
    assert response.status_code == 200
    variant = response.json()["variants"][0]
    assert variant["recommendation"] == "BUY_NOW"
    assert variant["expected_saving"] is None
    assert variant["expected_saving_percentage"] is None
    assert variant["buying_window"] == "BUY_NOW"
    assert variant["urgency"] is None
    assert variant["prediction_used"] is False
    assert any("BUY_FAVORABLE_PERCENTILE" in reason for reason in variant["reasons"])
    assert variant["provenance"]["current_price_value_kind"] == "CALCULATED"
    assert variant["evidence"]["predicted_sale_price"] is None
    get_ml_config.cache_clear()


def test_recommendation_wait_from_unfavorable_percentile_and_upcoming_event(
    client: TestClient, db_session: Session, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("ML_MODEL_ARTIFACT_PATH", str(tmp_path))
    from ml.config import get_ml_config

    get_ml_config.cache_clear()
    seed = _seed_listing(db_session, slug_prefix="rec-wait")
    _add_snapshots(
        db_session,
        seed["listing"],
        prices=["100.00", "110.00", "120.00", "130.00", "220.00"],
        seller_id=seed["seller"].id,
        newest_age_hours=1.0,
        step_hours=1.0,
    )
    db_session.add(
        make_sale_event(
            name="FIXTURE: Fictional Upcoming Sale",
            brand=seed["brand"],
            category=seed["category"],
            start_date=datetime.now(UTC) + timedelta(days=6),
            end_date=datetime.now(UTC) + timedelta(days=12),
        )
    )
    db_session.flush()
    response = client.get(f"/api/v1/products/{seed['product'].id}/recommendation")
    assert response.status_code == 200
    variant = response.json()["variants"][0]
    assert variant["recommendation"] == "WAIT"
    assert variant["expected_saving"] is None
    joined = " ".join(variant["reasons"])
    assert "WAIT_UNFAVORABLE_PERCENTILE" in joined or "WAIT_UPCOMING_SALE" in joined
    get_ml_config.cache_clear()


def test_recommendation_stale_current_observation_is_insufficient(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed_listing(db_session, slug_prefix="rec-stale")
    _add_snapshots(
        db_session,
        seed["listing"],
        prices=["200.00", "180.00", "100.00"],
        seller_id=seed["seller"].id,
        newest_age_hours=48.0,
        step_hours=12.0,
    )
    response = client.get(f"/api/v1/products/{seed['product'].id}/recommendation")
    assert response.status_code == 200
    variant = response.json()["variants"][0]
    assert variant["recommendation"] == "INSUFFICIENT_DATA"
    assert variant["insufficient"] == "stale_data"
    assert variant["expected_saving"] is None


def test_recommendation_watch_for_neutral_history(
    client: TestClient, db_session: Session, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("ML_MODEL_ARTIFACT_PATH", str(tmp_path))
    from ml.config import get_ml_config

    get_ml_config.cache_clear()
    seed = _seed_listing(db_session, slug_prefix="rec-watch")
    _add_snapshots(
        db_session,
        seed["listing"],
        prices=["100.00", "110.00", "105.00", "108.00", "106.00"],
        seller_id=seed["seller"].id,
        newest_age_hours=1.0,
        step_hours=1.0,
    )
    response = client.get(f"/api/v1/products/{seed['product'].id}/recommendation")
    assert response.status_code == 200
    variant = response.json()["variants"][0]
    assert variant["recommendation"] == "WATCH"
    # Tight cluster around the current price should not fabricate a saving.
    assert variant["expected_saving"] is None
    assert variant["prediction_used"] is False
    get_ml_config.cache_clear()


def test_phase10_prediction_endpoint_still_returns_insufficient_without_model(
    client: TestClient, db_session: Session, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("ML_MODEL_ARTIFACT_PATH", str(tmp_path))
    from ml.config import get_ml_config

    get_ml_config.cache_clear()
    seed = _seed_listing(db_session, slug_prefix="rec-phase10")
    _add_snapshots(
        db_session,
        seed["listing"],
        prices=["500.00"],
        seller_id=seed["seller"].id,
        newest_age_hours=2.0,
    )
    response = client.get(f"/api/v1/products/{seed['product'].id}/sale-price-prediction")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INSUFFICIENT_DATA"
    assert body["value_kind"] == "PREDICTED"
    assert body["is_prediction"] is True
    assert body["predictions"] == []
    get_ml_config.cache_clear()


def test_recommendation_keeps_variants_separate(
    client: TestClient, db_session: Session, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("ML_MODEL_ARTIFACT_PATH", str(tmp_path))
    from ml.config import get_ml_config

    get_ml_config.cache_clear()
    seed = _seed_listing(db_session, slug_prefix="rec-two")
    other = make_variant(seed["product"], attributes={"storage": "256GB", "color": "Black"})
    db_session.add(other)
    db_session.flush()
    listing_b = make_retailer_product(
        other,
        seed["listing"].retailer,
        retailer_sku="REC-256",
        url="https://fictional.example.test/rec-256",
    )
    db_session.add(listing_b)
    db_session.flush()
    _add_snapshots(
        db_session,
        seed["listing"],
        prices=["200.00", "100.00", "90.00"],
        seller_id=seed["seller"].id,
    )
    _add_snapshots(
        db_session,
        listing_b,
        prices=["300.00", "310.00", "320.00"],
        seller_id=seed["seller"].id,
    )
    response = client.get(f"/api/v1/products/{seed['product'].id}/recommendation")
    assert response.status_code == 200
    variants = response.json()["variants"]
    assert len(variants) == 2
    ids = {item["product_variant_id"] for item in variants}
    assert ids == {str(seed["variant"].id), str(other.id)}
    get_ml_config.cache_clear()


def test_recommendation_urgency_is_optional_and_invalid_value_is_rejected(
    client: TestClient, db_session: Session, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("ML_MODEL_ARTIFACT_PATH", str(tmp_path))
    from ml.config import get_ml_config

    get_ml_config.cache_clear()
    seed = _seed_listing(db_session, slug_prefix="rec-urg")
    _add_snapshots(
        db_session,
        seed["listing"],
        prices=["200.00", "180.00", "160.00", "140.00", "100.00"],
        seller_id=seed["seller"].id,
    )
    none = client.get(f"/api/v1/products/{seed['product'].id}/recommendation")
    urgent = client.get(
        f"/api/v1/products/{seed['product'].id}/recommendation",
        params={"urgency": "urgent"},
    )
    assert none.status_code == 200
    assert urgent.status_code == 200
    assert none.json()["variants"][0]["recommendation"] == "BUY_NOW"
    assert urgent.json()["variants"][0]["recommendation"] == "BUY_NOW"
    assert urgent.json()["variants"][0]["urgency"] == "urgent"
    assert none.json()["variants"][0]["urgency"] is None
    bad = client.get(
        f"/api/v1/products/{seed['product'].id}/recommendation",
        params={"urgency": "panic"},
    )
    assert bad.status_code == 422
    get_ml_config.cache_clear()
