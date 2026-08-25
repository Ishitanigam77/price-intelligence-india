"""Integration tests for `/api/v1/retailers` (route + schema + repository wiring)."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import make_retailer, make_seller


def test_list_retailers_is_empty_page_when_none_exist(client: TestClient) -> None:
    response = client.get("/api/v1/retailers")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_retailers_returns_created_retailers(client: TestClient, db_session: Session) -> None:
    retailer = make_retailer(slug="api-test-retailer")
    db_session.add(retailer)
    db_session.flush()

    response = client.get("/api/v1/retailers")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "api-test-retailer"
    assert body["items"][0]["country_code"] == "IN"


def test_list_retailers_active_only_filter(client: TestClient, db_session: Session) -> None:
    active = make_retailer(slug="api-active-retailer", is_active=True)
    inactive = make_retailer(slug="api-inactive-retailer", is_active=False)
    db_session.add_all([active, inactive])
    db_session.flush()

    response = client.get("/api/v1/retailers", params={"active_only": True})
    assert response.status_code == 200
    body = response.json()
    slugs = {item["slug"] for item in body["items"]}
    assert "api-active-retailer" in slugs
    assert "api-inactive-retailer" not in slugs


def test_get_retailer_by_id(client: TestClient, db_session: Session) -> None:
    retailer = make_retailer(slug="api-get-retailer-by-id")
    db_session.add(retailer)
    db_session.flush()

    response = client.get(f"/api/v1/retailers/{retailer.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(retailer.id)


def test_get_retailer_by_id_returns_404_when_missing(client: TestClient) -> None:
    response = client.get(f"/api/v1/retailers/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_get_retailer_by_slug(client: TestClient, db_session: Session) -> None:
    retailer = make_retailer(slug="api-get-retailer-by-slug")
    db_session.add(retailer)
    db_session.flush()

    response = client.get("/api/v1/retailers/slug/api-get-retailer-by-slug")
    assert response.status_code == 200
    assert response.json()["slug"] == "api-get-retailer-by-slug"


def test_list_retailer_sellers(client: TestClient, db_session: Session) -> None:
    retailer = make_retailer()
    db_session.add(retailer)
    db_session.flush()
    seller = make_seller(retailer, name="API Test Seller")
    db_session.add(seller)
    db_session.flush()

    response = client.get(f"/api/v1/retailers/{retailer.id}/sellers")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "API Test Seller"
