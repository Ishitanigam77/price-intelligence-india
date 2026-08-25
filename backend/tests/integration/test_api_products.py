"""Integration tests for `/api/v1/products` (route + schema + repository wiring)."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import make_brand, make_category, make_product, make_variant


def test_list_products_is_empty_page_when_none_exist(client: TestClient) -> None:
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_products_returns_created_products(client: TestClient, db_session: Session) -> None:
    product = make_product(slug="api-test-product")
    db_session.add(product)
    db_session.flush()

    response = client.get("/api/v1/products")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "api-test-product"
    # Internal ORM/session details never leak into the API response.
    assert "brand" not in body["items"][0] or body["items"][0].get("brand") is None
    assert set(body["items"][0].keys()) == {
        "id",
        "name",
        "slug",
        "description",
        "brand_id",
        "category_id",
        "is_active",
        "created_at",
        "updated_at",
    }


def test_get_product_by_id(client: TestClient, db_session: Session) -> None:
    product = make_product(slug="api-get-by-id")
    db_session.add(product)
    db_session.flush()

    response = client.get(f"/api/v1/products/{product.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(product.id)


def test_get_product_by_id_returns_structured_404_when_missing(client: TestClient) -> None:
    response = client.get(f"/api/v1/products/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_get_product_by_invalid_uuid_returns_422(client: TestClient) -> None:
    response = client.get("/api/v1/products/not-a-uuid")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_get_product_by_slug(client: TestClient, db_session: Session) -> None:
    product = make_product(slug="api-get-by-slug")
    db_session.add(product)
    db_session.flush()

    response = client.get("/api/v1/products/slug/api-get-by-slug")
    assert response.status_code == 200
    assert response.json()["slug"] == "api-get-by-slug"


def test_get_product_by_slug_returns_404_when_missing(client: TestClient) -> None:
    response = client.get("/api/v1/products/slug/does-not-exist")
    assert response.status_code == 404


def test_list_products_filtered_by_category(client: TestClient, db_session: Session) -> None:
    category = make_category(slug="api-category")
    other_category = make_category(slug="api-other-category")
    db_session.add_all([category, other_category])
    db_session.flush()

    matching = make_product(slug="api-in-category", category_id=category.id)
    other = make_product(slug="api-in-other-category", category_id=other_category.id)
    db_session.add_all([matching, other])
    db_session.flush()

    response = client.get("/api/v1/products", params={"category_id": str(category.id)})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "api-in-category"


def test_list_products_filtered_by_brand(client: TestClient, db_session: Session) -> None:
    brand = make_brand(slug="api-brand")
    db_session.add(brand)
    db_session.flush()

    product = make_product(slug="api-branded-product", brand_id=brand.id)
    db_session.add(product)
    db_session.flush()

    response = client.get("/api/v1/products", params={"brand_id": str(brand.id)})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["brand_id"] == str(brand.id)


def test_list_products_rejects_limit_below_minimum(client: TestClient) -> None:
    response = client.get("/api/v1/products", params={"limit": 0})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_product_variants(client: TestClient, db_session: Session) -> None:
    product = make_product()
    db_session.add(product)
    db_session.flush()
    variant = make_variant(product, attributes={"storage": "256GB", "color": "Blue"})
    db_session.add(variant)
    db_session.flush()

    response = client.get(f"/api/v1/products/{product.id}/variants")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["variant_key"] == variant.variant_key
