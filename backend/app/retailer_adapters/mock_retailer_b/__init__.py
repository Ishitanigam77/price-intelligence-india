"""MockRetailerB adapter package (fixture-backed mock, not a real retailer).

Exposes the discovery convention: `RETAILER_ID`, `ADAPTER_KIND`, and `create_adapter`.
"""

from collections.abc import Callable, Mapping
from datetime import datetime

from app.core.config import Settings
from app.observability.metrics import MetricsSink
from app.retailer_adapters.base.discovery import AdapterKind
from app.retailer_adapters.base.rate_limit import RateLimiter
from app.retailer_adapters.mock_retailer_b.adapter import MockRetailerBAdapter
from app.retailer_adapters.mock_retailer_b.config import (
    RETAILER_ID,
    RETAILER_NAME,
    build_config,
)

ADAPTER_KIND = AdapterKind.MOCK


def create_adapter(
    *,
    settings: Settings | None = None,
    env: Mapping[str, str] | None = None,
    enabled: bool | None = None,
    metrics_sink: MetricsSink | None = None,
    rate_limiter: RateLimiter | None = None,
    clock: Callable[[], datetime] | None = None,
) -> MockRetailerBAdapter:
    """Build a configured MockRetailerB adapter."""
    return MockRetailerBAdapter(
        build_config(settings=settings, env=env, enabled=enabled),
        metrics_sink=metrics_sink,
        rate_limiter=rate_limiter,
        clock=clock,
    )


__all__ = [
    "ADAPTER_KIND",
    "RETAILER_ID",
    "RETAILER_NAME",
    "MockRetailerBAdapter",
    "build_config",
    "create_adapter",
]
