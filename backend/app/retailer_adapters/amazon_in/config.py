"""Amazon.in adapter identity, capabilities, and operational policy.

Credentials are never stored here. OAuth client id/secret and the Associates partner tag are
read from the environment by the adapter at call time (see `auth.py` and the package README).
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

RETAILER_ID = "amazon-in"
RETAILER_NAME = "Amazon.in"

#: Official Creators API catalog host. Overridable via env (non-secret).
DEFAULT_API_BASE_URL = "https://creatorsapi.amazon"
#: India is in the EU/IN Creators API credential region (version 3.2).
DEFAULT_TOKEN_URL = "https://api.amazon.co.uk/auth/o2/token"
DEFAULT_MARKETPLACE = "www.amazon.in"
DEFAULT_CREDENTIAL_VERSION = "3.2"
DEFAULT_LANGUAGE = "en_IN"

#: Categories this adapter will accept. Each slug maps to a Creators API SearchIndex
#: (see `client.py`); unknown slugs are not claimed.
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
        AdapterOperation.GET_PRODUCT_IDENTIFIERS,
    }
)

#: Documented initial Creators API allowance is 1 TPS / 8640 TPD. Pace at 1 request per
#: second and never burst above that. Operators may lower this further via env overrides.
RATE_LIMIT = RateLimitConfig(
    max_requests_per_minute=60, burst_size=1, max_concurrent_requests=1
)

OPTIONS: dict[str, str] = {
    "api_base_url": DEFAULT_API_BASE_URL,
    "oauth_endpoint": DEFAULT_TOKEN_URL,
    "marketplace": DEFAULT_MARKETPLACE,
    "oauth_version": DEFAULT_CREDENTIAL_VERSION,
    "language": DEFAULT_LANGUAGE,
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
