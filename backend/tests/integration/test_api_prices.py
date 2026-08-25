"""Integration tests for `/api/v1/prices` (route + `PriceService` + repository wiring).

Covers the distinction the service layer exists for: a retailer listing that doesn't exist at
all (404) versus one that exists but has no observations yet (empty history / 404 on "latest"
with a clear "no observation recorded" message, never a fabricated price).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    make_price_snapshot,
    make_product,
    make_retailer,
    make_retailer_product,
    make_variant,
)


def _make_retailer_product(db_session: Session):
    product = make_product()
    variant = make_variant(product)
    retailer = make_retailer()
    db_session.add_all([variant, retailer])
    db_session.flush()
    rp = make_retailer_product(variant, retailer)
    db_session.add(rp)
    db_session.flush()
    return rp


def test_get_latest_price_returns_404_for_unknown_retailer_product(client: TestClient) -> None:
    response = client.get(f"/api/v1/prices/retailer-products/{uuid.uuid4()}/latest")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_get_latest_price_returns_404_when_retailer_product_has_no_observations(
    client: TestClient, db_session: Session
) -> None:
    rp = _make_retailer_product(db_session)

    response = client.get(f"/api/v1/prices/retailer-products/{rp.id}/latest")
    assert response.status_code == 404
    assert "recorded" in response.json()["error"]["message"]


def test_get_latest_price_returns_the_most_recent_observation(
    client: TestClient, db_session: Session
) -> None:
    rp = _make_retailer_product(db_session)
    now = datetime.now(UTC)
    db_session.add(
        make_price_snapshot(rp, displayed_price=Decimal("100"), observed_at=now - timedelta(days=1))
    )
    db_session.add(make_price_snapshot(rp, displayed_price=Decimal("90"), observed_at=now))
    db_session.flush()

    response = client.get(f"/api/v1/prices/retailer-products/{rp.id}/latest")
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["displayed_price"]) == Decimal("90")


def test_get_price_history_returns_404_for_unknown_retailer_product(client: TestClient) -> None:
    response = client.get(f"/api/v1/prices/retailer-products/{uuid.uuid4()}/history")
    assert response.status_code == 404


def test_get_price_history_returns_empty_page_when_no_observations_exist(
    client: TestClient, db_session: Session
) -> None:
    rp = _make_retailer_product(db_session)

    response = client.get(f"/api/v1/prices/retailer-products/{rp.id}/history")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 500, "offset": 0}


def test_get_price_history_returns_observations_oldest_first(
    client: TestClient, db_session: Session
) -> None:
    rp = _make_retailer_product(db_session)
    now = datetime.now(UTC)
    older = make_price_snapshot(
        rp, displayed_price=Decimal("120"), observed_at=now - timedelta(days=2)
    )
    newer = make_price_snapshot(rp, displayed_price=Decimal("110"), observed_at=now)
    db_session.add_all([newer, older])
    db_session.flush()

    response = client.get(f"/api/v1/prices/retailer-products/{rp.id}/history")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [Decimal(item["displayed_price"]) for item in body["items"]] == [
        Decimal("120"),
        Decimal("110"),
    ]


def test_get_price_history_respects_limit_query_param(
    client: TestClient, db_session: Session
) -> None:
    rp = _make_retailer_product(db_session)
    now = datetime.now(UTC)
    for i in range(3):
        db_session.add(
            make_price_snapshot(
                rp, observed_at=now - timedelta(days=3 - i), displayed_price=Decimal("100")
            )
        )
    db_session.flush()

    response = client.get(f"/api/v1/prices/retailer-products/{rp.id}/history", params={"limit": 2})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["limit"] == 2
