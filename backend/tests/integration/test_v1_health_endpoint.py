"""Integration tests for `/api/v1/health` and `/api/v1/health/ready`.

Extends Phase 1's `/health`/`/health/ready` coverage with the Phase 2 requirement that
readiness distinguish PostgreSQL availability from Redis availability independently.
"""

from collections.abc import Generator

import redis
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.deps import get_redis
from app.db.session import get_db
from app.main import app


def test_v1_liveness_returns_ok() -> None:
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "backend"
    assert "environment" in body


def test_v1_readiness_reports_postgresql_and_redis_independently() -> None:
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["postgresql"]["status"] == "ok"
    assert body["checks"]["redis"]["status"] == "ok"


def test_v1_readiness_reports_degraded_and_503_when_postgresql_is_unreachable() -> None:
    def _broken_db() -> Generator[Session, None, None]:
        class _BrokenSession:
            def execute(self, *args, **kwargs):
                raise OperationalError("SELECT 1", {}, Exception("simulated database outage"))

        yield _BrokenSession()  # type: ignore[misc]

    app.dependency_overrides[get_db] = _broken_db
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["postgresql"]["status"] == "unavailable"


def test_v1_readiness_reports_degraded_and_503_when_redis_is_unreachable() -> None:
    def _broken_redis() -> Generator[redis.Redis, None, None]:
        yield redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2)

    def _working_db() -> Generator[Session, None, None]:
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_redis] = _broken_redis
    app.dependency_overrides[get_db] = _working_db
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.pop(get_redis, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"]["status"] == "unavailable"
    assert body["checks"]["postgresql"]["status"] == "ok"
