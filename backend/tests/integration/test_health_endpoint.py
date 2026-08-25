"""Integration tests for the FastAPI health check skeleton."""

from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok() -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_reports_database_connectivity() -> None:
    # `tests/conftest.py` already points DATABASE_URL at the test database before `app.main`
    # (and therefore `app.db.session`) is first imported anywhere in the test process.
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
