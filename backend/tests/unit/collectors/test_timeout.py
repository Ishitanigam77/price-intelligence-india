"""Unit tests for collection operation timeouts."""

import asyncio

import pytest

from app.collectors.errors import CollectionTimeoutError
from app.collectors.timeout import run_with_timeout


async def test_exceeding_timeout_fails_only_that_operation() -> None:
    async def hang() -> str:
        await asyncio.sleep(10)
        return "never"

    with pytest.raises(CollectionTimeoutError) as exc:
        await run_with_timeout(
            hang,
            timeout_seconds=0.05,
            retailer_id="store-a",
            operation_name="product_search",
            operation_target="fictional",
        )
    assert exc.value.category.value == "timeout"
    assert exc.value.retailer_id == "store-a"
    assert exc.value.retryable is True
    assert exc.value.operation == "product_search"


async def test_completing_within_timeout_returns_result() -> None:
    async def quick() -> str:
        return "ok"

    assert (
        await run_with_timeout(
            quick, timeout_seconds=1.0, retailer_id="store-a", operation_name="product_search"
        )
        == "ok"
    )
