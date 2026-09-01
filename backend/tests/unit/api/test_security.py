"""Unit tests for Phase 17 HTTP edge hardening."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.security import (
    SlidingWindowLimiter,
    is_expensive_path,
    is_health_path,
    sanitize_validation_errors,
    validate_runtime_security,
)
from app.core.config import Settings
from app.main import create_app


def test_health_and_expensive_path_classification() -> None:
    assert is_health_path("/health")
    assert is_health_path("/api/v1/health/ready")
    assert not is_health_path("/api/v1/products/search")
    assert is_expensive_path("/api/v1/products/search")
    assert is_expensive_path("/api/v1/products/abc/sale-price-prediction")
    assert is_expensive_path("/api/v1/products/abc/recommendation")
    assert is_expensive_path("/api/v1/products/abc/sale-intelligence")
    assert not is_expensive_path("/api/v1/products")


def test_sliding_window_limiter_blocks_after_limit() -> None:
    limiter = SlidingWindowLimiter()
    assert limiter.allow("ip", limit=2)
    assert limiter.allow("ip", limit=2)
    assert limiter.allow("ip", limit=2) is False


def test_validation_errors_omit_input_values() -> None:
    cleaned = sanitize_validation_errors(
        [
            {
                "type": "string_too_short",
                "loc": ("query", "q"),
                "msg": "String should have at least 1 character",
                "input": "CLERK_SECRET_KEY=sk_test_leaked",
                "ctx": {"min_length": 1},
            }
        ]
    )
    assert cleaned == [
        {
            "type": "string_too_short",
            "loc": ("query", "q"),
            "msg": "String should have at least 1 character",
        }
    ]
    assert "sk_test" not in str(cleaned)


def test_wildcard_cors_with_credentials_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_allowed_origins="*", cors_allow_credentials=True)


def test_rate_limiting_auto_is_off_locally_and_on_when_deployed() -> None:
    local = Settings(_env_file=None, environment="development")
    assert local.rate_limiting_enabled is False
    deployed = Settings(_env_file=None, environment="prod")
    assert deployed.is_production is True
    assert deployed.rate_limiting_enabled is True
    forced = Settings(_env_file=None, environment="development", api_rate_limit_enabled="true")
    assert forced.rate_limiting_enabled is True


def test_production_rejects_placeholder_database_url() -> None:
    settings = Settings(
        _env_file=None,
        environment="prod",
        database_url="postgresql+psycopg://priceradar_app:changeme@localhost:5432/priceradar",
    )
    with pytest.raises(ValueError, match="Placeholder database"):
        validate_runtime_security(settings)
    ok = settings.model_copy(
        update={
            "database_url": "postgresql+psycopg://app:not-a-placeholder@db.internal:5432/priceradar"
        }
    )
    validate_runtime_security(ok)


def test_production_requires_clerk_issuer_and_audience_when_configured() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+psycopg://app:real-password@db.internal:5432/priceradar",
        clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
    )
    with pytest.raises(ValueError, match="CLERK_ISSUER"):
        validate_runtime_security(settings)


def test_security_headers_are_present_on_health() -> None:
    app = create_app(Settings(_env_file=None, environment="development"))
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "no-store" in response.headers["cache-control"]


def test_rate_limit_returns_structured_429() -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        api_rate_limit_enabled="true",
        api_rate_limit_per_minute=2,
        api_rate_limit_expensive_per_minute=2,
    )
    app = create_app(settings)

    @app.get("/_rate-limit-probe")
    def _probe() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        assert client.get("/_rate-limit-probe").status_code == 200
        assert client.get("/_rate-limit-probe").status_code == 200
        limited = client.get("/_rate-limit-probe")
    assert limited.status_code == 429
    body = limited.json()
    assert body["error"]["code"] == "rate_limited"
    assert "Retry-After" in limited.headers


def test_openapi_is_disabled_in_deployed_environments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://app:not-a-placeholder@db.internal:5432/priceradar",
    )
    app = create_app(
        Settings(
            _env_file=None,
            environment="prod",
            database_url="postgresql+psycopg://app:not-a-placeholder@db.internal:5432/priceradar",
        )
    )
    assert app.docs_url is None
    assert app.openapi_url is None
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_create_app_keeps_docs_in_local_development() -> None:
    app = create_app(Settings(_env_file=None, environment="development"))
    assert app.docs_url == "/docs"
    assert "/health" in app.openapi()["paths"]
