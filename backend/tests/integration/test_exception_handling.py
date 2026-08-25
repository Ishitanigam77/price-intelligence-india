"""Tests for centralized exception handling (`app.api.errors`).

Uses a small, isolated `FastAPI` app (registering the same handlers via
`register_exception_handlers`) with purpose-built routes that deliberately raise each error
type. This exercises the handlers directly without adding debug-only routes to the real
application in `app.main`.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.errors import NotFoundError, register_exception_handlers
from app.domain.exceptions import InvalidSlugError


def _build_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom/not-found")
    def _not_found() -> None:
        raise NotFoundError("Widget 42 was not found.")

    @app.get("/boom/domain-error")
    def _domain_error() -> None:
        raise InvalidSlugError("'Not A Slug!' is not a valid slug.")

    @app.get("/boom/database-error")
    def _database_error() -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    @app.get("/boom/unexpected")
    def _unexpected() -> None:
        raise RuntimeError("something truly unexpected happened")

    @app.get("/boom/validated")
    def _validated(count: int) -> dict[str, int]:
        return {"count": count}

    return app


@pytest.fixture()
def error_client() -> TestClient:
    return TestClient(_build_test_app(), raise_server_exceptions=False)


def test_not_found_error_returns_structured_404(error_client: TestClient) -> None:
    response = error_client.get("/boom/not-found")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert "Widget 42" in body["error"]["message"]


def test_domain_error_returns_structured_400(error_client: TestClient) -> None:
    response = error_client.get("/boom/domain-error")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "domain_error"


def test_database_error_is_masked_and_returns_structured_500(error_client: TestClient) -> None:
    response = error_client.get("/boom/database-error")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "database_error"
    # Never leak the underlying SQL / driver error to the client.
    assert "SELECT 1" not in body["error"]["message"]
    assert "connection refused" not in body["error"]["message"]


def test_unexpected_error_is_masked_and_returns_structured_500(error_client: TestClient) -> None:
    response = error_client.get("/boom/unexpected")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "RuntimeError" not in body["error"]["message"]
    assert "truly unexpected" not in body["error"]["message"]


def test_request_validation_error_returns_structured_422_with_field_details(
    error_client: TestClient,
) -> None:
    response = error_client.get("/boom/validated", params={"count": "not-an-int"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["fields"]
    assert body["error"]["fields"][0]["loc"] == ["query", "count"]


def test_unknown_route_returns_structured_404(error_client: TestClient) -> None:
    response = error_client.get("/this-route-does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
