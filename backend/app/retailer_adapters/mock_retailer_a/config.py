"""MockRetailerA's declared identity, capabilities, and operational policy."""

from collections.abc import Mapping

from app.core.config import Settings
from app.domain.enums import SourceType
from app.retailer_adapters.base.config import (
    AdapterOperation,
    RateLimitConfig,
    RetailerAdapterConfig,
    build_adapter_config,
)

RETAILER_ID = "mock-retailer-a"
RETAILER_NAME = "Fictional Mock Mart A"

#: This retailer's (fictional) official API covers phones and audio, and exposes every operation.
SUPPORTED_CATEGORIES: tuple[str, ...] = ("mobiles", "audio")
SUPPORTED_OPERATIONS: frozenset[AdapterOperation] = frozenset(
    {
        AdapterOperation.SEARCH_PRODUCTS,
        AdapterOperation.GET_PRODUCT,
        AdapterOperation.GET_PRICE,
        AdapterOperation.GET_AVAILABILITY,
        AdapterOperation.GET_PRODUCT_IDENTIFIERS,
    }
)

#: A mock adapter issues no outbound requests, so there is no retailer to be polite to; pacing
#: is configured permissively to keep test suites fast. A real adapter uses the allowance its
#: retailer publishes.
RATE_LIMIT = RateLimitConfig(
    max_requests_per_minute=6000, burst_size=100, max_concurrent_requests=8
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
        source_type=SourceType.OFFICIAL_API,
        supported_categories=SUPPORTED_CATEGORIES,
        supported_operations=SUPPORTED_OPERATIONS,
        rate_limit=RATE_LIMIT,
        options={"catalogue": "fixture"},
        enabled=enabled,
        settings=settings,
        env=env,
    )
