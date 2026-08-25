"""Tests for the per-retailer rate-limit abstraction."""

import pytest

from app.observability.metrics import InMemoryMetricsSink
from app.retailer_adapters.base.config import AdapterOperation, RateLimitConfig
from app.retailer_adapters.base.execution import AdapterExecutor
from app.retailer_adapters.base.metrics import (
    ADAPTER_RATE_LIMIT_WAITS,
    AdapterMetricsRecorder,
)
from app.retailer_adapters.base.rate_limit import (
    NullRateLimiter,
    TokenBucketRateLimiter,
    build_rate_limiter,
)
from tests.unit.retailer_adapters.helpers import FakeClock, make_config


class TestNullRateLimiter:
    async def test_never_delays(self) -> None:
        limiter = NullRateLimiter()
        assert await limiter.acquire() == 0.0
        limiter.release()


class TestTokenBucketRateLimiter:
    async def test_paces_after_the_burst_is_spent(self) -> None:
        clock = FakeClock()
        limiter = TokenBucketRateLimiter(
            RateLimitConfig(max_requests_per_minute=60, burst_size=2, max_concurrent_requests=2),
            clock=clock,
            sleep=clock.sleep,
        )
        first = await limiter.acquire()
        limiter.release()
        second = await limiter.acquire()
        limiter.release()
        third = await limiter.acquire()
        limiter.release()
        assert first == 0.0
        assert second == 0.0
        assert third == pytest.approx(1.0)
        assert clock.now == pytest.approx(1.0)

    async def test_two_retailers_do_not_share_a_budget(self) -> None:
        clock = FakeClock()
        tight = RateLimitConfig(max_requests_per_minute=60, burst_size=1, max_concurrent_requests=1)
        generous = RateLimitConfig(
            max_requests_per_minute=6000, burst_size=100, max_concurrent_requests=8
        )
        limiter_a = TokenBucketRateLimiter(tight, clock=clock, sleep=clock.sleep)
        limiter_b = TokenBucketRateLimiter(generous, clock=clock, sleep=clock.sleep)
        await limiter_a.acquire()
        limiter_a.release()
        waited_a = await limiter_a.acquire()
        limiter_a.release()
        waited_b = await limiter_b.acquire()
        limiter_b.release()
        waited_b2 = await limiter_b.acquire()
        limiter_b.release()
        assert waited_a == pytest.approx(1.0)
        assert waited_b == 0.0
        assert waited_b2 == 0.0

    def test_build_rate_limiter_returns_a_token_bucket(self) -> None:
        limiter = build_rate_limiter(RateLimitConfig())
        assert isinstance(limiter, TokenBucketRateLimiter)
        assert limiter.config.min_interval_seconds == pytest.approx(1.0)


class TestRateLimitMetrics:
    async def test_executor_records_a_rate_limit_wait(self) -> None:
        clock = FakeClock()
        sink = InMemoryMetricsSink()
        limiter = TokenBucketRateLimiter(
            RateLimitConfig(max_requests_per_minute=60, burst_size=1, max_concurrent_requests=1),
            clock=clock,
            sleep=clock.sleep,
        )
        config = make_config()
        executor = AdapterExecutor(
            config,
            rate_limiter=limiter,
            metrics=AdapterMetricsRecorder(config.retailer_id, sink),
            sleep=clock.sleep,
            monotonic=clock,
            jitter=lambda: 0.0,
        )

        async def ok() -> str:
            return "ok"

        await executor.execute(AdapterOperation.GET_PRICE, ok)
        await executor.execute(AdapterOperation.GET_PRICE, ok)
        assert (
            sink.counter_value(
                ADAPTER_RATE_LIMIT_WAITS, retailer_id="scripted-store", operation="get_price"
            )
            == 1
        )
