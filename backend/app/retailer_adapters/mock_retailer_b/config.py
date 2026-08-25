"""MockRetailerB's declared identity, capabilities, and operational policy."""

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

RETAILER_ID = "mock-retailer-b"
RETAILER_NAME = "Fictional Mock Bazaar B"

#: A marketplace covering phones and laptops. Its feed has no standalone availability lookup, so
#: `GET_AVAILABILITY` is deliberately not declared — callers must ask capability, not assume it.
SUPPORTED_CATEGORIES: tuple[str, ...] = ("mobiles", "laptops")
SUPPORTED_OPERATIONS: frozenset[AdapterOperation] = frozenset(
    {
        AdapterOperation.SEARCH_PRODUCTS,
        AdapterOperation.GET_PRODUCT,
        AdapterOperation.GET_PRICE,
        AdapterOperation.GET_PRODUCT_IDENTIFIERS,
    }
)

#: A batch feed is fetched rarely and is slower to respond, so this adapter is configured with a
#: longer timeout and a gentler backoff curve than the API-backed one.
RETRY_POLICY = RetryPolicy(
    max_attempts=2,
    backoff_strategy=BackoffStrategy.LINEAR,
    initial_backoff_seconds=1.0,
    max_backoff_seconds=5.0,
)
RATE_LIMIT = RateLimitConfig(
    max_requests_per_minute=6000, burst_size=100, max_concurrent_requests=4
)


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
        timeout_seconds=20.0,
        retry_policy=RETRY_POLICY,
        rate_limit=RATE_LIMIT,
        options={"feed_format": "flat_rows"},
        enabled=enabled,
        settings=settings,
        env=env,
    )
