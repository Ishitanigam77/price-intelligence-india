"""Flipkart adapter identity, capabilities, and operational policy.

Affiliate id and token are read from the environment at call time, never stored on config.
"""

from collections.abc import Mapping

from app.core.config import Settings
from app.domain.enums import SourceType
from app.retailer_adapters.base.config import (
    AdapterOperation,
    RateLimitConfig,
    RetailerAdapterConfig,
    RetryPolicy,
    build_adapter_config,
)

RETAILER_ID = "flipkart"
RETAILER_NAME = "Flipkart"

DEFAULT_API_BASE_URL = "https://affiliate-api.flipkart.net/affiliate"

SUPPORTED_CATEGORIES: tuple[str, ...] = (
    "mobiles",
    "electronics",
    "audio",
    "computers",
    "home-appliances",
    "fashion",
    "beauty",
    "grocery",
    "books",
    "sports",
    "toys",
    "automotive",
    "home-and-kitchen",
)

SUPPORTED_OPERATIONS: frozenset[AdapterOperation] = frozenset(
    {
        AdapterOperation.SEARCH_PRODUCTS,
        AdapterOperation.GET_PRODUCT,
        AdapterOperation.GET_PRICE,
        AdapterOperation.GET_AVAILABILITY,
    }
)

#: Documented Affiliate API limit is 20 calls/second/affiliate. Pace far below that.
RATE_LIMIT = RateLimitConfig(
    max_requests_per_minute=120, burst_size=1, max_concurrent_requests=1
)

OPTIONS: dict[str, str] = {
    "api_base_url": DEFAULT_API_BASE_URL,
}


def build_config(
    *,
    settings: Settings | None = None,
    env: Mapping[str, str] | None = None,
    enabled: bool | None = None,
) -> RetailerAdapterConfig:
    """Build this adapter's configuration from its declarations plus settings/environment."""
    return build_adapter_config(
        retailer_id=RETAILER_ID,
        retailer_name=RETAILER_NAME,
        source_type=SourceType.AFFILIATE_FEED,
        supported_categories=SUPPORTED_CATEGORIES,
        supported_operations=SUPPORTED_OPERATIONS,
        rate_limit=RATE_LIMIT,
        retry_policy=RetryPolicy(max_attempts=3, jitter_ratio=0.1),
        options=OPTIONS,
        enabled=enabled,
        settings=settings,
        env=env,
    )
