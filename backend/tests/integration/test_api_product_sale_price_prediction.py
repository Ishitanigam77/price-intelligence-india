"""Integration tests for `GET /api/v1/products/{product_id}/sale-price-prediction`."""

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
    make_seller,
    make_variant,
)


def _seed_product(db_session: Session) -> dict[str, object]:
    brand = make_brand()
    category = make_category()
    product = make_product(
        name="Fictional Phone X",
        slug=f"sale-pred-{uuid.uuid4().hex[:8]}",
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
        retailer_sku="PRED-128",
        url="https://fictional.example.test/pred-128",
    )
    db_session.add_all([seller, listing])
    db_session.flush()
    now = datetime.now(UTC)
    db_session.add(
        make_price_snapshot(
            listing,
            displayed_price=Decimal("500.00"),
            effective_price=Decimal("500.00"),
            observed_at=now - timedelta(days=2),
            seller_id=seller.id,
        )
    )
    db_session.flush()
    return {"product": product, "variant": variant}


def test_unknown_product_sale_price_prediction_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/products/{uuid.uuid4()}/sale-price-prediction")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_prediction_without_trained_model_is_insufficient_not_fabricated(
    client: TestClient, db_session: Session, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("ML_MODEL_ARTIFACT_PATH", str(tmp_path))
    from ml.config import get_ml_config

    get_ml_config.cache_clear()
    seed = _seed_product(db_session)
    product = seed["product"]
    response = client.get(f"/api/v1/products/{product.id}/sale-price-prediction")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INSUFFICIENT_DATA"
    assert body["value_kind"] == "PREDICTED"
    assert body["is_prediction"] is True
    assert body["predictions"] == []
    assert body["insufficient"]["code"] == "no_trained_model"
    assert (
        "fabricated" in body["insufficient"]["reason"].lower()
        or "not" in body["insufficient"]["reason"].lower()
    )
