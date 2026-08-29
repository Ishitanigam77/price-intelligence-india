"""API authorization tests for Phase 12 user-owned resources.

Uses `StaticTokenVerifier` (not live Clerk) so ownership and 401/403/404 behaviour can be
asserted without fabricating a real Clerk session.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import make_product
from tests.integration.auth_helpers import bearer, register_identity


def _product(db_session: Session, slug: str | None = None):
    product = make_product(slug=slug or f"auth-prod-{uuid.uuid4().hex[:10]}")
    db_session.add(product)
    db_session.flush()
    return product


def test_unauthenticated_watchlist_get_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/watchlists")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_unauthenticated_watchlist_post_returns_401(client: TestClient) -> None:
    response = client.post("/api/v1/watchlists", json={"product_id": str(uuid.uuid4())})
    assert response.status_code == 401


def test_unauthenticated_alerts_return_401(client: TestClient) -> None:
    assert client.get("/api/v1/alerts").status_code == 401
    assert (
        client.post(
            "/api/v1/alerts",
            json={"product_id": str(uuid.uuid4()), "threshold_amount": "1.00"},
        ).status_code
        == 401
    )


def test_unauthenticated_saved_products_return_401(client: TestClient) -> None:
    assert client.get("/api/v1/saved-products").status_code == 401
    assert (
        client.post("/api/v1/saved-products", json={"product_id": str(uuid.uuid4())}).status_code
        == 401
    )


def test_unauthenticated_target_prices_return_401(client: TestClient) -> None:
    assert client.get("/api/v1/target-prices").status_code == 401


def test_unauthenticated_profile_returns_401(client: TestClient) -> None:
    assert client.get("/api/v1/me").status_code == 401


def test_malformed_authorization_header_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/watchlists", headers={"Authorization": "NotBearer abc"})
    assert response.status_code == 401


def test_invalid_static_token_returns_401(auth_client: TestClient, token_mapping: dict) -> None:
    register_identity(token_mapping, "good-token", clerk_user_id="user_good")
    response = auth_client.get("/api/v1/watchlists", headers=bearer("forged-token"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_real_verifier_rejects_garbage_token_when_clerk_is_not_configured(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/watchlists", headers=bearer("not-a-jwt"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_authenticated_user_can_create_and_list_own_watchlist(
    auth_client: TestClient, token_mapping: dict, db_session: Session
) -> None:
    product = _product(db_session)
    register_identity(
        token_mapping, "token-a", clerk_user_id="user_owner_a", email="a@example.test"
    )

    created = auth_client.post(
        "/api/v1/watchlists",
        json={"product_id": str(product.id)},
        headers=bearer("token-a"),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["product_id"] == str(product.id)
    assert "user_id" not in body

    listed = auth_client.get("/api/v1/watchlists", headers=bearer("token-a"))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == body["id"]


def test_authenticated_user_retrieves_only_own_watchlists(
    auth_client: TestClient, token_mapping: dict, db_session: Session
) -> None:
    product_a = _product(db_session, slug="iso-watch-a")
    product_b = _product(db_session, slug="iso-watch-b")
    register_identity(token_mapping, "token-a", clerk_user_id="user_iso_a")
    register_identity(token_mapping, "token-b", clerk_user_id="user_iso_b")

    auth_client.post(
        "/api/v1/watchlists", json={"product_id": str(product_a.id)}, headers=bearer("token-a")
    )
    auth_client.post(
        "/api/v1/watchlists", json={"product_id": str(product_b.id)}, headers=bearer("token-b")
    )

    listed_a = auth_client.get("/api/v1/watchlists", headers=bearer("token-a")).json()
    listed_b = auth_client.get("/api/v1/watchlists", headers=bearer("token-b")).json()
    assert listed_a["total"] == 1
    assert listed_b["total"] == 1
    assert listed_a["items"][0]["product_id"] == str(product_a.id)
    assert listed_b["items"][0]["product_id"] == str(product_b.id)


def test_authenticated_user_cannot_access_another_users_watchlist(
    auth_client: TestClient, token_mapping: dict, db_session: Session
) -> None:
    product = _product(db_session)
    register_identity(token_mapping, "token-a", clerk_user_id="user_watch_owner")
    register_identity(token_mapping, "token-b", clerk_user_id="user_watch_other")

    created = auth_client.post(
        "/api/v1/watchlists", json={"product_id": str(product.id)}, headers=bearer("token-a")
    )
    item_id = created.json()["id"]

    response = auth_client.get(f"/api/v1/watchlists/{item_id}", headers=bearer("token-b"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"

    deleted = auth_client.delete(f"/api/v1/watchlists/{item_id}", headers=bearer("token-b"))
    assert deleted.status_code == 404


def test_client_supplied_user_id_cannot_override_watchlist_owner(
    auth_client: TestClient, token_mapping: dict, db_session: Session
) -> None:
    product = _product(db_session)
    register_identity(token_mapping, "token-a", clerk_user_id="user_body_owner")
    register_identity(token_mapping, "token-b", clerk_user_id="user_body_other")

    rejected = auth_client.post(
        "/api/v1/watchlists",
        json={"product_id": str(product.id), "user_id": str(uuid.uuid4())},
        headers=bearer("token-a"),
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "validation_error"

    created = auth_client.post(
        "/api/v1/watchlists", json={"product_id": str(product.id)}, headers=bearer("token-a")
    )
    assert created.status_code == 201

    listed_b = auth_client.get(
        "/api/v1/watchlists",
        params={"user_id": created.json()["id"]},
        headers=bearer("token-b"),
    )
    assert listed_b.status_code == 200
    assert listed_b.json()["total"] == 0


def test_duplicate_watchlist_returns_409(
    auth_client: TestClient, token_mapping: dict, db_session: Session
) -> None:
    product = _product(db_session)
    register_identity(token_mapping, "token-a", clerk_user_id="user_dup_watch")
    headers = bearer("token-a")
    first = auth_client.post(
        "/api/v1/watchlists", json={"product_id": str(product.id)}, headers=headers
    )
    second = auth_client.post(
        "/api/v1/watchlists", json={"product_id": str(product.id)}, headers=headers
    )
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


def test_watchlist_invalid_product_returns_404(
    auth_client: TestClient, token_mapping: dict
) -> None:
    register_identity(token_mapping, "token-a", clerk_user_id="user_missing_product")
    response = auth_client.post(
        "/api/v1/watchlists",
        json={"product_id": str(uuid.uuid4())},
        headers=bearer("token-a"),
    )
    assert response.status_code == 404


def test_authenticated_user_can_create_and_list_own_alerts(
    auth_client: TestClient, token_mapping: dict, db_session: Session
) -> None:
    product = _product(db_session)
    register_identity(token_mapping, "token-a", clerk_user_id="user_alert_owner")
    created = auth_client.post(
        "/api/v1/alerts",
        json={
            "product_id": str(product.id),
            "threshold_amount": "499.00",
            "currency": "INR",
            "is_enabled": True,
        },
        headers=bearer("token-a"),
    )
    assert created.status_code == 201
    assert created.json()["threshold_amount"] == "499.00"
    assert created.json()["is_enabled"] is True
    listed = auth_client.get("/api/v1/alerts", headers=bearer("token-a"))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_authenticated_user_retrieves_only_own_alerts(
    auth_client: TestClient, token_mapping: dict, db_session: Session
) -> None:
    product_a = _product(db_session, slug="iso-alert-a")
    product_b = _product(db_session, slug="iso-alert-b")
    register_identity(token_mapping, "token-a", clerk_user_id="user_alert_a")
    register_identity(token_mapping, "token-b", clerk_user_id="user_alert_b")
    payload = {"threshold_amount": "100.00", "currency": "INR", "is_enabled": True}
    auth_client.post(
        "/api/v1/alerts",
        json={"product_id": str(product_a.id), **payload},
        headers=bearer("token-a"),
    )
    auth_client.post(
        "/api/v1/alerts",
        json={"product_id": str(product_b.id), **payload},
        headers=bearer("token-b"),
    )
    listed_a = auth_client.get("/api/v1/alerts", headers=bearer("token-a")).json()
    listed_b = auth_client.get("/api/v1/alerts", headers=bearer("token-b")).json()
    assert listed_a["total"] == 1
    assert listed_b["total"] == 1
    assert listed_a["items"][0]["product_id"] == str(product_a.id)
    assert listed_b["items"][0]["product_id"] == str(product_b.id)


def test_authenticated_user_cannot_access_another_users_alert(
    auth_client: TestClient, token_mapping: dict, db_session: Session
) -> None:
    product = _product(db_session)
    register_identity(token_mapping, "token-a", clerk_user_id="user_alert_keep")
    register_identity(token_mapping, "token-b", clerk_user_id="user_alert_intruder")
    created = auth_client.post(
        "/api/v1/alerts",
        json={"product_id": str(product.id), "threshold_amount": "50.00"},
        headers=bearer("token-a"),
    )
    item_id = created.json()["id"]
    response = auth_client.get(f"/api/v1/alerts/{item_id}", headers=bearer("token-b"))
    assert response.status_code == 404
    patched = auth_client.patch(
        f"/api/v1/alerts/{item_id}", json={"is_enabled": False}, headers=bearer("token-b")
    )
    assert patched.status_code == 404


def test_client_supplied_user_id_cannot_override_alert_owner(
    auth_client: TestClient, token_mapping: dict, db_session: Session
) -> None:
    product = _product(db_session)
    register_identity(token_mapping, "token-a", clerk_user_id="user_alert_body")
    response = auth_client.post(
        "/api/v1/alerts",
        json={
            "product_id": str(product.id),
            "threshold_amount": "10.00",
            "user_id": str(uuid.uuid4()),
        },
        headers=bearer("token-a"),
    )
    assert response.status_code == 422


def test_saved_products_are_user_isolated(
    auth_client: TestClient, token_mapping: dict, db_session: Session
) -> None:
    product = _product(db_session)
    register_identity(token_mapping, "token-a", clerk_user_id="user_save_a")
    register_identity(token_mapping, "token-b", clerk_user_id="user_save_b")
    created = auth_client.post(
        "/api/v1/saved-products", json={"product_id": str(product.id)}, headers=bearer("token-a")
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    listed_b = auth_client.get("/api/v1/saved-products", headers=bearer("token-b"))
    assert listed_b.json()["total"] == 0
    assert (
        auth_client.get(f"/api/v1/saved-products/{item_id}", headers=bearer("token-b")).status_code
        == 404
    )

    duplicate = auth_client.post(
        "/api/v1/saved-products", json={"product_id": str(product.id)}, headers=bearer("token-a")
    )
    assert duplicate.status_code == 409


def test_target_prices_are_user_isolated(
    auth_client: TestClient, token_mapping: dict, db_session: Session
) -> None:
    product = _product(db_session)
    register_identity(token_mapping, "token-a", clerk_user_id="user_target_a")
    register_identity(token_mapping, "token-b", clerk_user_id="user_target_b")
    created = auth_client.post(
        "/api/v1/target-prices",
        json={"product_id": str(product.id), "amount": "799.00", "currency": "INR"},
        headers=bearer("token-a"),
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    listed_b = auth_client.get("/api/v1/target-prices", headers=bearer("token-b"))
    assert listed_b.json()["total"] == 0
    assert (
        auth_client.get(f"/api/v1/target-prices/{item_id}", headers=bearer("token-b")).status_code
        == 404
    )
    patched = auth_client.patch(
        f"/api/v1/target-prices/{item_id}",
        json={"amount": "1.00"},
        headers=bearer("token-b"),
    )
    assert patched.status_code == 404

    own_patch = auth_client.patch(
        f"/api/v1/target-prices/{item_id}",
        json={"amount": "750.00"},
        headers=bearer("token-a"),
    )
    assert own_patch.status_code == 200
    assert own_patch.json()["amount"] == "750.00"


def test_profile_is_user_isolated(auth_client: TestClient, token_mapping: dict) -> None:
    register_identity(
        token_mapping,
        "token-a",
        clerk_user_id="user_profile_a",
        email="a@example.test",
        display_name="Ada",
    )
    register_identity(
        token_mapping,
        "token-b",
        clerk_user_id="user_profile_b",
        email="b@example.test",
        display_name="Bob",
    )

    profile_a = auth_client.get("/api/v1/me", headers=bearer("token-a"))
    profile_b = auth_client.get("/api/v1/me", headers=bearer("token-b"))
    assert profile_a.status_code == 200
    assert profile_a.json()["clerk_user_id"] == "user_profile_a"
    assert profile_a.json()["email"] == "a@example.test"
    assert profile_b.json()["clerk_user_id"] == "user_profile_b"
    assert profile_a.json()["id"] != profile_b.json()["id"]

    updated = auth_client.patch(
        "/api/v1/me",
        json={"display_name": "Ada Lovelace", "preferences": {"email_alerts_enabled": False}},
        headers=bearer("token-a"),
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Ada Lovelace"
    assert updated.json()["preferences"]["email_alerts_enabled"] is False

    other = auth_client.get("/api/v1/me", headers=bearer("token-b"))
    assert other.json()["display_name"] == "Bob"
    assert other.json()["preferences"]["email_alerts_enabled"] is True

    forged = auth_client.patch(
        "/api/v1/me",
        json={"clerk_user_id": "user_forged", "user_id": str(uuid.uuid4())},
        headers=bearer("token-a"),
    )
    assert forged.status_code == 422


def test_public_catalogue_routes_remain_unauthenticated(
    client: TestClient, db_session: Session
) -> None:
    product = _product(db_session, slug="public-still-public")
    response = client.get(f"/api/v1/products/{product.id}")
    assert response.status_code == 200
    assert response.json()["slug"] == "public-still-public"
