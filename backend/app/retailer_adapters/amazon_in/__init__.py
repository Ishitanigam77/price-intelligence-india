"""Amazon.in adapter package (Associates Creators API).

Exposes the discovery convention: `RETAILER_ID`, `ADAPTER_KIND`, and `create_adapter`.
"""

from collections.abc import Callable, Mapping
from datetime import datetime

import httpx

from app.core.config import Settings
from app.observability.metrics import MetricsSink
from app.retailer_adapters.amazon_in.adapter import AmazonInAdapter
from app.retailer_adapters.amazon_in.config import (
    RETAILER_ID,
    RETAILER_NAME,
    build_config,
)
from app.retailer_adapters.base.discovery import AdapterKind
from app.retailer_adapters.base.rate_limit import RateLimiter

ADAPTER_KIND = AdapterKind.INTEGRATION


def create_adapter(
    *,
    settings: Settings | None = None,
    env: Mapping[str, str] | None = None,
    enabled: bool | None = None,
    metrics_sink: MetricsSink | None = None,
    rate_limiter: RateLimiter | None = None,
    clock: Callable[[], datetime] | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> AmazonInAdapter:
    """Build a configured Amazon.in adapter."""
    return AmazonInAdapter(
        build_config(settings=settings, env=env, enabled=enabled),
        metrics_sink=metrics_sink,
        rate_limiter=rate_limiter,
        clock=clock,
        env=env,
        http_client=http_client,
    )


__all__ = [
    "ADAPTER_KIND",
    "RETAILER_ID",
    "RETAILER_NAME",
    "AmazonInAdapter",
    "build_config",
    "create_adapter",
]
