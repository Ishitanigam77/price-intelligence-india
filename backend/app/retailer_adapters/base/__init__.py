"""The retailer adapter framework: contract, configuration, models, and registry.

This package is retailer-agnostic by construction — it must never import from a specific
`app.retailer_adapters.<retailer_slug>` package. Core modules (`normalization/`, `matching/`,
`pricing/`, `sales/`, `recommendation/`) depend on this package only, never on an individual
adapter (see `RETAILER_ARCHITECTURE.md` §4).
"""

from app.retailer_adapters.base.config import (
    AdapterOperation,
    BackoffStrategy,
    RateLimitConfig,
    RetailerAdapterConfig,
    RetryPolicy,
    apply_environment_overrides,
    build_adapter_config,
    env_prefix_for,
)
from app.retailer_adapters.base.discovery import (
    AdapterKind,
    DiscoveredAdapter,
    discover_adapters,
)
from app.retailer_adapters.base.errors import (
    DEFAULT_RETRYABLE_ERROR_CODES,
    AdapterContractError,
    AdapterDisabledError,
    AdapterErrorCode,
    AdapterMisconfiguredError,
    AdapterTimeoutError,
    AdapterUnavailableError,
    InvalidRetailerResponseError,
    ProductNotFoundError,
    RateLimitExceededError,
    RetailerAdapterError,
    RetailerAlreadyRegisteredError,
    RetailerNotRegisteredError,
    RetailerRegistryError,
    TemporaryRetailerFailureError,
    UnexpectedAdapterFailureError,
    UnsupportedOperationError,
)
from app.retailer_adapters.base.execution import AdapterExecutor
from app.retailer_adapters.base.fleet import (
    FleetSearchOutcome,
    RetailerFailure,
    RetailerFleet,
)
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.metrics import AdapterMetricsRecorder
from app.retailer_adapters.base.models import (
    AvailabilityObservation,
    HealthCheckResult,
    HealthStatus,
    NormalizedProduct,
    PriceObservation,
    ProductIdentifierValue,
    ProductSearchQuery,
    ProductSearchResult,
    RetailerProduct,
    SellerInformation,
)
from app.retailer_adapters.base.rate_limit import (
    NullRateLimiter,
    RateLimiter,
    TokenBucketRateLimiter,
    build_rate_limiter,
)
from app.retailer_adapters.base.registry import RetailerRegistration, RetailerRegistry

__all__ = [
    "DEFAULT_RETRYABLE_ERROR_CODES",
    "AdapterContractError",
    "AdapterDisabledError",
    "AdapterErrorCode",
    "AdapterExecutor",
    "AdapterKind",
    "AdapterMetricsRecorder",
    "AdapterMisconfiguredError",
    "AdapterOperation",
    "AdapterTimeoutError",
    "AdapterUnavailableError",
    "AvailabilityObservation",
    "BackoffStrategy",
    "DiscoveredAdapter",
    "FleetSearchOutcome",
    "HealthCheckResult",
    "HealthStatus",
    "InvalidRetailerResponseError",
    "NormalizedProduct",
    "NullRateLimiter",
    "PriceObservation",
    "ProductIdentifierValue",
    "ProductNotFoundError",
    "ProductSearchQuery",
    "ProductSearchResult",
    "RateLimitConfig",
    "RateLimitExceededError",
    "RateLimiter",
    "RetailerAdapter",
    "RetailerAdapterConfig",
    "RetailerAdapterError",
    "RetailerAlreadyRegisteredError",
    "RetailerFailure",
    "RetailerFleet",
    "RetailerNotRegisteredError",
    "RetailerProduct",
    "RetailerRegistration",
    "RetailerRegistry",
    "RetailerRegistryError",
    "RetryPolicy",
    "SellerInformation",
    "TemporaryRetailerFailureError",
    "TokenBucketRateLimiter",
    "UnexpectedAdapterFailureError",
    "UnsupportedOperationError",
    "apply_environment_overrides",
    "build_adapter_config",
    "build_rate_limiter",
    "discover_adapters",
    "env_prefix_for",
]
