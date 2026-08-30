"""Integration tests for the application factory (`app.main.create_app`) and its lifecycle.

Covers: the app starts up and shuts down cleanly, CORS is configured from settings, both the
legacy (Phase 1) and versioned (Phase 2) health routes are mounted, and the versioned prefix
matches `Settings.api_v1_prefix`.
"""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _all_route_paths(app) -> set[str]:
    """Every mounted path, read from the OpenAPI schema (a stable public contract) rather than
    FastAPI's internal route-tree representation, which is not part of any compatibility
    guarantee."""
    return set(app.openapi()["paths"].keys())


def test_create_app_mounts_legacy_and_versioned_health_routes() -> None:
    app = create_app()
    paths = _all_route_paths(app)

    assert "/health" in paths
    assert "/health/ready" in paths
    assert "/api/v1/health" in paths
    assert "/api/v1/health/ready" in paths
    assert "/api/v1/health/live" in paths


def test_create_app_mounts_every_v1_resource_route() -> None:
    app = create_app()
    paths = _all_route_paths(app)

    assert any(path.startswith("/api/v1/products") for path in paths)
    assert "/api/v1/products/search" in paths
    assert "/api/v1/products/{product_id}/prices" in paths
    assert "/api/v1/products/{product_id}/history" in paths
    assert "/api/v1/products/{product_id}/sale-history" in paths
    assert "/api/v1/products/{product_id}/sale-price-prediction" in paths
    assert "/api/v1/products/{product_id}/recommendation" in paths
    assert any(path.startswith("/api/v1/retailers") for path in paths)
    assert any(path.startswith("/api/v1/prices") for path in paths)
    assert "/api/v1/deals" in paths
    assert "/api/v1/sale-events" in paths
    assert "/api/v1/sale-events/upcoming" in paths
    assert "/api/v1/me" in paths
    assert "/api/v1/watchlists" in paths
    assert "/api/v1/saved-products" in paths
    assert "/api/v1/target-prices" in paths
    assert "/api/v1/alerts" in paths


def test_app_starts_up_and_shuts_down_cleanly() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200


def test_cors_allowed_origins_are_read_from_settings() -> None:
    app = create_app(Settings(_env_file=None, cors_allowed_origins="https://custom.example.com"))
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/deals",
            headers={
                "Origin": "https://custom.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://custom.example.com"
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "*" not in allow_methods
    assert "GET" in allow_methods


def test_cors_rejects_an_origin_that_is_not_allowlisted() -> None:
    app = create_app(Settings(_env_file=None, cors_allowed_origins="https://custom.example.com"))
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/deals",
            headers={
                "Origin": "https://not-allowed.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert "access-control-allow-origin" not in response.headers
