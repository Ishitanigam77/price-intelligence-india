"""Unit tests for `app.core.config.Settings`.

No database or Redis is needed here — these exercise pure settings parsing/validation.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_are_sane_for_local_development() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.is_production is False
    assert settings.is_test is False
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.db_pool_size >= 1
    assert settings.redis_max_connections >= 1


def test_is_production_is_case_insensitive() -> None:
    assert Settings(_env_file=None, environment="Production").is_production is True
    assert Settings(_env_file=None, environment="PRODUCTION").is_production is True
    assert Settings(_env_file=None, environment="development").is_production is False


def test_is_test_reflects_environment_value() -> None:
    assert Settings(_env_file=None, environment="test").is_test is True
    assert Settings(_env_file=None, environment="development").is_test is False


def test_log_level_is_normalized_to_uppercase() -> None:
    assert Settings(_env_file=None, log_level="debug").log_level == "DEBUG"


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level="not-a-level")


def test_cors_allowed_origins_list_parses_comma_separated_values() -> None:
    settings = Settings(
        _env_file=None,
        cors_allowed_origins="http://localhost:3000, https://app.example.com ,,",
    )
    assert settings.cors_allowed_origins_list == [
        "http://localhost:3000",
        "https://app.example.com",
    ]


def test_cors_allowed_origins_list_is_empty_when_unset() -> None:
    settings = Settings(_env_file=None, cors_allowed_origins="")
    assert settings.cors_allowed_origins_list == []


def test_disabled_retailer_ids_parses_comma_separated_values() -> None:
    settings = Settings(
        _env_file=None, retailer_adapters_disabled="mock-retailer-a, mock-retailer-c"
    )
    assert settings.disabled_retailer_ids == frozenset({"mock-retailer-a", "mock-retailer-c"})


def test_retailer_adapter_kinds_default_to_mock() -> None:
    settings = Settings(_env_file=None)
    assert settings.retailer_adapter_kind_values == ("mock",)


def test_retailer_adapter_kinds_parses_comma_separated_values() -> None:
    settings = Settings(_env_file=None, retailer_adapter_kinds="mock, integration")
    assert settings.retailer_adapter_kind_values == ("mock", "integration")


def test_invalid_retailer_adapter_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, retailer_adapter_kinds="scraping")


def test_database_url_and_redis_url_never_default_to_a_wildcard_or_empty_secret() -> None:
    """Sanity check that defaults are non-secret placeholders, never blank/production values."""
    settings = Settings(_env_file=None)
    assert "changeme" in settings.database_url
    assert settings.redis_url.startswith("redis://")


def test_clerk_settings_default_to_empty_placeholders() -> None:
    settings = Settings(_env_file=None)
    assert settings.clerk_publishable_key == ""
    assert settings.clerk_secret_key == ""
    assert settings.clerk_jwks_url == ""
    assert settings.clerk_is_configured is False


def test_clerk_is_configured_when_jwks_url_is_set() -> None:
    settings = Settings(
        _env_file=None,
        clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
    )
    assert settings.clerk_is_configured is True
