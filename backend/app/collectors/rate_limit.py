"""Per-retailer collection rate limiting.

Limits are independent: retailer A's token bucket never blocks retailer B. This layer exists to
keep collection *inside* published retailer allowances. It does not detect, evade, or raise
those allowances, and it is not a substitute for `robots.txt`, authentication, or terms of
service. Phase 13 only drives mock/approved adapters.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.collectors.config import CollectionConfig
from app.retailer_adapters.base.config import RateLimitConfig
from app.retailer_adapters.base.rate_limit import RateLimiter, TokenBucketRateLimiter


class CollectionRateLimiterRegistry:
    """One token-bucket limiter per retailer id."""

    def __init__(
        self,
        config: CollectionConfig,
        *,
        clock: Callable[[], float],
        sleep: Callable[[float], Awaitable[None]],
    ) -> None:
        self._config = config
        self._clock = clock
        self._sleep = sleep
        self._limiters: dict[str, RateLimiter] = {}

    def limiter_for(self, retailer_id: str, *, adapter_rpm: int | None = None) -> RateLimiter:
        existing = self._limiters.get(retailer_id)
        if existing is not None:
            return existing
        rpm = self._config.rate_limit_requests_per_minute
        if adapter_rpm is not None:
            rpm = min(rpm, max(1, adapter_rpm))
        limiter = TokenBucketRateLimiter(
            RateLimitConfig(
                max_requests_per_minute=rpm,
                burst_size=self._config.rate_limit_burst_size,
                max_concurrent_requests=self._config.rate_limit_max_concurrent,
            ),
            clock=self._clock,
            sleep=self._sleep,
        )
        self._limiters[retailer_id] = limiter
        return limiter
