"""Outer timeouts for collection operations so one hung retailer cannot block the system."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.collectors.errors import CollectionTimeoutError

T = TypeVar("T")


async def run_with_timeout(
    operation: Callable[[], Awaitable[T]],
    *,
    timeout_seconds: float,
    retailer_id: str,
    operation_name: str,
    operation_target: str | None = None,
) -> T:
    """Run `operation` under `timeout_seconds`. On expiry, fail only this call."""
    try:
        return await asyncio.wait_for(operation(), timeout=timeout_seconds)
    except TimeoutError as exc:
        raise CollectionTimeoutError(
            f"Collection operation {operation_name!r} exceeded its {timeout_seconds}s timeout.",
            retailer_id=retailer_id,
            operation=operation_name,
            operation_target=operation_target,
        ) from exc
