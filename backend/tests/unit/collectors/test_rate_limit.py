"""Per-retailer collection rate limiting is isolated between retailers."""

from app.collectors.config import CollectionConfig
from app.collectors.rate_limit import CollectionRateLimiterRegistry
from tests.unit.retailer_adapters.helpers import FakeClock


def _registry(clock: FakeClock) -> CollectionRateLimiterRegistry:
    return CollectionRateLimiterRegistry(
        CollectionConfig(
            rate_limit_requests_per_minute=60,
            rate_limit_burst_size=1,
            rate_limit_max_concurrent=1,
        ),
        clock=clock,
        sleep=clock.sleep,
    )


async def test_rate_limit_is_per_retailer_and_does_not_block_another() -> None:
    clock = FakeClock()
    registry = _registry(clock)
    limiter_a = registry.limiter_for("store-a")
    limiter_b = registry.limiter_for("store-b")

    waited_a_first = await limiter_a.acquire()
    limiter_a.release()
    waited_a_second = await limiter_a.acquire()
    limiter_a.release()
    waited_b = await limiter_b.acquire()
    limiter_b.release()

    assert waited_a_first == 0.0
    assert waited_a_second == 1.0  # 60 rpm => 1s spacing with burst 1
    assert waited_b == 0.0
    assert limiter_a is not limiter_b


async def test_adapter_rpm_caps_collection_limiter() -> None:
    clock = FakeClock()
    registry = _registry(clock)
    limiter = registry.limiter_for("store-a", adapter_rpm=30)
    await limiter.acquire()
    limiter.release()
    waited = await limiter.acquire()
    limiter.release()
    assert waited == 2.0
