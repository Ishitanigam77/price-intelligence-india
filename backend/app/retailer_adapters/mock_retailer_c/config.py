"""MockRetailerC's declared identity, capabilities, and operational policy."""

from collections.abc import Mapping

from app.core.config import Settings
from app.domain.enums import SourceType
from app.retailer_adapters.base.config import (
    AdapterOperation,
    BackoffStrategy,
    RateLimitConfig,
    RetailerAdapterConfig,
    RetryPolicy,
    build_adapter_config,
)

RETAILER_ID = "mock-retailer-c"
RETAILER_NAME = "Fictional Mock Depot C"

#: A first-party store covering audio and home appliances. Its feed publishes no product
#: identifiers, so `GET_PRODUCT_IDENTIFIERS` is deliberately not declared.
SUPPORTED_CATEGORIES: tuple[str, ...] = ("audio", "home-appliances")
SUPPORTED_OPERATIONS: frozenset[AdapterOperation] = frozenset(
    {
        AdapterOperation.SEARCH_PRODUCTS,
        AdapterOperation.GET_PRODUCT,
        AdapterOperation.GET_PRICE,
        AdapterOperation.GET_AVAILABILITY,
    }
)

#: A small store's feed host is the least robust of the three, so this adapter retries a little
#: more patiently and paces itself the hardest.
RETRY_POLICY = RetryPolicy(
    max_attempts=4,
    backoff_strategy=BackoffStrategy.FIXED,
    initial_backoff_seconds=0.25,
    max_backoff_seconds=2.0,
)
RATE_LIMIT = RateLimitConfig(max_requests_per_minute=3000, burst_size=50, max_concurrent_requests=2)


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
        source_type=SourceType.PRODUCT_FEED,
        supported_categories=SUPPORTED_CATEGORIES,
        supported_operations=SUPPORTED_OPERATIONS,
        timeout_seconds=5.0,
        retry_policy=RETRY_POLICY,
        rate_limit=RATE_LIMIT,
        options={"feed_format": "nested_entries"},
        enabled=enabled,
        settings=settings,
        env=env,
    )
