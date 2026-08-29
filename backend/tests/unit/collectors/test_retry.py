"""Unit tests for collection retry / exponential backoff."""

import pytest

from app.collectors.config import CollectionConfig
from app.collectors.errors import (
    CollectionFailure,
    CollectionPermanentError,
    CollectionTimeoutError,
)
from app.collectors.retry import backoff_seconds, is_retryable
from app.domain.enums import CollectionErrorCategory


def test_exponential_backoff_is_deterministic_and_bounded() -> None:
    config = CollectionConfig(
        initial_backoff_seconds=1.0,
        backoff_multiplier=2.0,
        max_backoff_seconds=5.0,
    )
    assert backoff_seconds(config, attempt=1) == 1.0
    assert backoff_seconds(config, attempt=2) == 2.0
    assert backoff_seconds(config, attempt=3) == 4.0
    assert backoff_seconds(config, attempt=4) == 5.0
    assert backoff_seconds(config, attempt=8) == 5.0


def test_backoff_rejects_invalid_attempt() -> None:
    with pytest.raises(ValueError):
        backoff_seconds(CollectionConfig(), attempt=0)


def test_retryable_timeout_is_retried_until_max_attempts() -> None:
    error = CollectionTimeoutError("slow", retailer_id="store-a", operation="product_search")
    assert is_retryable(error, attempt=1, max_attempts=3) is True
    assert is_retryable(error, attempt=2, max_attempts=3) is True
    assert is_retryable(error, attempt=3, max_attempts=3) is False


def test_permanent_and_validation_errors_are_not_retried() -> None:
    permanent = CollectionPermanentError("not found", retailer_id="store-a")
    validation = CollectionFailure(
        "bad payload",
        category=CollectionErrorCategory.VALIDATION,
        retailer_id="store-a",
        retryable=False,
        operation="search_products",
    )
    assert is_retryable(permanent, attempt=1, max_attempts=5) is False
    assert is_retryable(validation, attempt=1, max_attempts=5) is False


def test_max_attempts_never_unbounded() -> None:
    config = CollectionConfig(max_retries=2)
    assert config.max_attempts == 3
    error = CollectionTimeoutError("slow", retailer_id="store-a")
    assert (
        is_retryable(
            error,
            attempt=config.max_attempts,
            max_attempts=config.max_attempts,
        )
        is False
    )
