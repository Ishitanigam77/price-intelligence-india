"""Per-retailer rate limiting.

The purpose of this module is *restraint*: pacing our own requests so the platform stays within
whatever allowance a retailer publishes, and bounding how many requests are in flight to one
retailer at a time. It contains nothing that detects, works around, or evades a limit — a
retailer that signals throttling produces a `RateLimitExceededError`, which the retry policy
honours by waiting at least as long as the retailer asked (see `RetryPolicy.delay_for`).

Every adapter gets its own limiter instance built from its own `RateLimitConfig`, so a retailer
with a generous documented allowance and one with a strict one never share a budget.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from app.retailer_adapters.base.config import RateLimitConfig


@runtime_checkable
class RateLimiter(Protocol):
    """Gate an adapter operation. `acquire` returns the seconds it paused before admitting it."""

    async def acquire(self) -> float:
        """Wait until a request slot is available. Must be paired with `release`."""

    def release(self) -> None:
        """Give back the slot taken by `acquire`."""


class NullRateLimiter:
    """A limiter that never delays anything.

    Used for adapters that perform no outbound requests at all (the mock adapters) and in tests.
    """

    async def acquire(self) -> float:
        return 0.0

    def release(self) -> None:
        return None


class TokenBucketRateLimiter:
    """Token-bucket pacing plus a concurrency ceiling.

    `max_requests_per_minute` sets the sustained refill rate and `burst_size` the bucket
    capacity, so an adapter may issue a short burst and is then paced to the configured average.
    `max_concurrent_requests` caps simultaneous in-flight requests.

    The clock and sleep function are injected so the pacing behaviour is testable without real
    time passing.
    """

    def __init__(
        self,
        config: RateLimitConfig,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._config = config
        self._clock = clock
        self._sleep = sleep
        self._refill_rate = config.max_requests_per_minute / 60.0
        self._capacity = float(config.burst_size)
        self._tokens = float(config.burst_size)
        self._updated_at = clock()
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)

    @property
    def config(self) -> RateLimitConfig:
        return self._config

    @property
    def available_tokens(self) -> float:
        return self._tokens

    async def acquire(self) -> float:
        self._replenish()
        await self._semaphore.acquire()
        try:
            return await self._pace()
        except BaseException:
            self._semaphore.release()
            raise

    def release(self) -> None:
        self._semaphore.release()

    def _replenish(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._updated_at)
        self._updated_at = now
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)

    async def _pace(self) -> float:
        # The lock is deliberately held across the sleep: pacing means requests are admitted one
        # at a time in order, so concurrent callers queue rather than all waking at once.
        async with self._lock:
            self._replenish()
            waited = 0.0
            if self._tokens < 1.0:
                waited = (1.0 - self._tokens) / self._refill_rate
                await self._sleep(waited)
                # Credit exactly the tokens the completed sleep bought, instead of re-reading the
                # clock, so pacing is exact under an injected clock as well as a real one.
                self._tokens += waited * self._refill_rate
                self._updated_at = self._clock()
            self._tokens -= 1.0
            return waited


def build_rate_limiter(
    config: RateLimitConfig,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> RateLimiter:
    """Default limiter for a rate-limit configuration."""
    return TokenBucketRateLimiter(config, clock=clock, sleep=sleep)
