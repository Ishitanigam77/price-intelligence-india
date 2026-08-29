"""Secrets must never appear in collection error text or log payloads."""

from app.collectors.sanitization import sanitize_mapping, sanitize_text
from app.observability.logging import REDACTED


def test_sanitize_text_redacts_bearer_tokens_and_password_assignments() -> None:
    raw = "Authorization: Bearer super-secret-token password=hunter2 api_key=abcd"
    cleaned = sanitize_text(raw)
    assert cleaned is not None
    assert "super-secret-token" not in cleaned
    assert "hunter2" not in cleaned
    assert "abcd" not in cleaned
    assert REDACTED in cleaned


def test_sanitize_text_redacts_redis_userinfo() -> None:
    cleaned = sanitize_text("broker redis://:hunter2@localhost:6379/1 failed")
    assert cleaned is not None
    assert "hunter2" not in cleaned
    assert REDACTED in cleaned


def test_sanitize_mapping_redacts_credential_keys() -> None:
    payload = sanitize_mapping(
        {
            "job_id": "abc",
            "api_key": "should-not-leak",
            "clerk_secret_key": "clerk-secret",
            "authorization": "Bearer xyz",
            "retailer_id": "mock-retailer-a",
        }
    )
    assert payload["api_key"] == REDACTED
    assert payload["clerk_secret_key"] == REDACTED
    assert payload["authorization"] == REDACTED
    assert payload["job_id"] == "abc"
    assert payload["retailer_id"] == "mock-retailer-a"


def test_sanitize_mapping_redacts_redis_credentials_in_values() -> None:
    payload = sanitize_mapping(
        {
            "job_id": "abc",
            "redis_url": "redis://:hunter2@localhost:6379/1",
        }
    )
    assert payload["job_id"] == "abc"
    assert "hunter2" not in payload["redis_url"]
    assert REDACTED in payload["redis_url"]
