"""The common `RetailerAdapter` contract every retailer integration implements.

## What an adapter author writes

Subclass `RetailerAdapter`, declare capabilities in a `RetailerAdapterConfig`, and implement the
protected hooks for the operations you declared:

- `search_products(query)` → `_search_products` → `ProductSearchResult`
- `get_product(sku)` → `_get_product` → `RetailerProduct`
- `get_price(sku)` → `_get_price` → `PriceObservation`
- `get_availability(sku)` → `_get_availability` → `AvailabilityObservation`
- `get_product_identifiers(sku)` → `_get_product_identifiers` → identifiers
- `health_check()` → `_check_health` (required)
- `normalize_product(product)` → `normalize_product` (required) → `NormalizedProduct`

Declaring an operation without implementing its hook (or vice versa) raises
`AdapterContractError` at construction time, so a mis-wired adapter fails at startup rather than
in production.

## What the framework guarantees

The public methods are template methods; they are not overridden. Around every hook the
framework applies, uniformly for all retailers:

- **Errors.** Only `RetailerAdapterError` subclasses escape. A hook that leaks a retailer-native
  exception has it translated into `UnexpectedAdapterFailureError`, with the detail logged
  rather than propagated. Calling a disabled adapter raises `AdapterDisabledError`; calling an
  undeclared operation raises `UnsupportedOperationError`.
- **Timeouts.** Each attempt runs under `config.attempt_timeout_seconds`; exceeding it raises
  `AdapterTimeoutError`. Hooks must still pass their own timeout to any HTTP client they use —
  this is the outer bound, not a substitute.
- **Retries.** Governed by `config.retry_policy`; only retryable failure kinds are retried.
- **Rate limiting.** Every attempt passes through the adapter's own limiter.
- **Logging.** One structured record per attempt and per outcome, carrying `retailer_id`,
  `operation`, `correlation_id`, `attempt`, `duration_ms`, `success`, and `error_type`. Hooks
  must not log credentials or raw payloads.
- **Metrics.** Request/success/failure counts, latency, timeouts, retries, rate-limit waits and
  health status, via the injected `MetricsSink`.

## What an adapter must never do

Reach into `app/db/`, `app/repositories/`, or `app/api/`; return fabricated data; or acquire data
by any means other than the legitimate source declared in `config.source_type` (see
`RETAILER_ARCHITECTURE.md` §2).
"""

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime

from app.observability.metrics import MetricsSink
from app.retailer_adapters.base.config import (
    AdapterOperation,
    RetailerAdapterConfig,
)
from app.retailer_adapters.base.errors import (
    AdapterContractError,
    AdapterDisabledError,
    InvalidRetailerResponseError,
    RetailerAdapterError,
    UnsupportedOperationError,
)
from app.retailer_adapters.base.execution import AdapterExecutor
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
)
from app.retailer_adapters.base.rate_limit import RateLimiter, build_rate_limiter

#: Declarable operation -> the protected hook that implements it.
OPERATION_HOOKS: dict[AdapterOperation, str] = {
    AdapterOperation.SEARCH_PRODUCTS: "_search_products",
    AdapterOperation.GET_PRODUCT: "_get_product",
    AdapterOperation.GET_PRICE: "_get_price",
    AdapterOperation.GET_AVAILABILITY: "_get_availability",
    AdapterOperation.GET_PRODUCT_IDENTIFIERS: "_get_product_identifiers",
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RetailerAdapter(ABC):
    """Common contract for every retailer integration. See the module docstring for the rules."""

    def __init__(
        self,
        config: RetailerAdapterConfig,
        *,
        metrics_sink: MetricsSink | None = None,
        rate_limiter: RateLimiter | None = None,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._enabled = config.enabled
        self._clock = clock or _utc_now
        self._monotonic = monotonic
        self._metrics = AdapterMetricsRecorder(config.retailer_id, metrics_sink)
        limiter = rate_limiter or build_rate_limiter(config.rate_limit)
        self._executor = AdapterExecutor(
            config, rate_limiter=limiter, metrics=self._metrics, monotonic=monotonic
        )
        # Health probes are paced with the same budget but never retried: a health check exists
        # to report the current state, and retrying would mask a degraded retailer.
        self._health_executor = AdapterExecutor(
            config.model_copy(
                update={"retry_policy": config.retry_policy.model_copy(update={"max_attempts": 1})}
            ),
            rate_limiter=limiter,
            metrics=self._metrics,
            monotonic=monotonic,
        )
        self._verify_declared_operations_are_implemented()

    # ------------------------------------------------------------------ identity & capabilities

    @property
    def config(self) -> RetailerAdapterConfig:
        return self._config

    @property
    def retailer_id(self) -> str:
        return self._config.retailer_id

    @property
    def retailer_name(self) -> str:
        return self._config.retailer_name

    @property
    def supported_operations(self) -> frozenset[AdapterOperation]:
        return self._config.supported_operations

    @property
    def supported_categories(self) -> tuple[str, ...]:
        return self._config.supported_categories

    @property
    def metrics(self) -> AdapterMetricsRecorder:
        return self._metrics

    def supports(self, operation: AdapterOperation) -> bool:
        """Whether this adapter declares support for `operation`."""
        return self._config.supports(operation)

    def serves_category(self, category: str) -> bool:
        """Whether this adapter covers the given category slug."""
        return self._config.serves_category(category)

    # -------------------------------------------------------------------------- enabled state

    @property
    def enabled(self) -> bool:
        """Runtime enablement. Initialized from configuration; toggled via the registry."""
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    # -------------------------------------------------------------------------- public contract

    async def search_products(self, query: ProductSearchQuery) -> ProductSearchResult:
        """Find candidate listings at this retailer for `query`."""
        operation = AdapterOperation.SEARCH_PRODUCTS
        self._ensure_operable(operation)
        result = await self._executor.execute(operation, lambda: self._search_products(query))
        self._assert_own_payload(result, operation=operation, payload_name="ProductSearchResult")
        for product in result.products:
            self._assert_own_payload(product, operation=operation, payload_name="RetailerProduct")
        return result

    async def get_product(self, retailer_sku: str) -> RetailerProduct:
        """Fetch one listing's current product data by the retailer's own SKU."""
        operation = AdapterOperation.GET_PRODUCT
        self._ensure_operable(operation)
        product = await self._executor.execute(operation, lambda: self._get_product(retailer_sku))
        self._assert_own_payload(product, operation=operation, payload_name="RetailerProduct")
        return product

    async def get_price(self, retailer_sku: str) -> PriceObservation:
        """Observe the current price of one listing."""
        operation = AdapterOperation.GET_PRICE
        self._ensure_operable(operation)
        observation = await self._executor.execute(operation, lambda: self._get_price(retailer_sku))
        self._assert_own_payload(observation, operation=operation, payload_name="PriceObservation")
        return observation

    async def get_availability(self, retailer_sku: str) -> AvailabilityObservation:
        """Observe the current availability of one listing."""
        operation = AdapterOperation.GET_AVAILABILITY
        self._ensure_operable(operation)
        observation = await self._executor.execute(
            operation, lambda: self._get_availability(retailer_sku)
        )
        self._assert_own_payload(
            observation, operation=operation, payload_name="AvailabilityObservation"
        )
        return observation

    async def get_product_identifiers(
        self, retailer_sku: str
    ) -> tuple[ProductIdentifierValue, ...]:
        """Fetch the cross-retailer identifiers (GTIN/EAN/UPC/MPN/...) this retailer exposes."""
        operation = AdapterOperation.GET_PRODUCT_IDENTIFIERS
        self._ensure_operable(operation)
        return await self._executor.execute(
            operation, lambda: self._get_product_identifiers(retailer_sku)
        )

    async def health_check(self) -> HealthCheckResult:
        """Probe the adapter's source and report status, latency, and failure kind.

        Never raises: an unhealthy retailer is a *result*, not an exception, because callers
        (registry sweeps, retailer-health reporting) need every adapter's outcome, not the first
        failure. A disabled adapter reports `UNKNOWN` without probing anything.
        """
        checked_at = self._clock()
        if not self._enabled:
            result = HealthCheckResult(
                retailer_id=self.retailer_id,
                status=HealthStatus.UNKNOWN,
                checked_at=checked_at,
                duration_ms=0.0,
                detail="Adapter is disabled; no probe was attempted.",
            )
            self._metrics.health_reported(result.status)
            return result

        started_at = self._monotonic()
        try:
            detail = await self._health_executor.execute(
                AdapterOperation.HEALTH_CHECK, self._check_health
            )
        except RetailerAdapterError as error:
            result = HealthCheckResult(
                retailer_id=self.retailer_id,
                status=(
                    HealthStatus.DEGRADED if error.inherently_retryable else HealthStatus.UNHEALTHY
                ),
                checked_at=checked_at,
                duration_ms=(self._monotonic() - started_at) * 1000.0,
                detail=error.message[:500],
                error_code=error.code,
            )
        else:
            result = HealthCheckResult(
                retailer_id=self.retailer_id,
                status=HealthStatus.HEALTHY,
                checked_at=checked_at,
                duration_ms=(self._monotonic() - started_at) * 1000.0,
                detail=detail,
            )
        self._metrics.health_reported(result.status)
        return result

    @abstractmethod
    def normalize_product(self, product: RetailerProduct) -> NormalizedProduct:
        """Map this retailer's standardized payload onto the retailer-agnostic shape.

        Pure and synchronous — no I/O, no matching decisions, no invented values. Structural
        mapping only (see `NormalizedProduct`).
        """

    # ------------------------------------------------------------------------------ hooks

    async def _search_products(self, query: ProductSearchQuery) -> ProductSearchResult:
        raise self._unsupported(AdapterOperation.SEARCH_PRODUCTS)

    async def _get_product(self, retailer_sku: str) -> RetailerProduct:
        raise self._unsupported(AdapterOperation.GET_PRODUCT)

    async def _get_price(self, retailer_sku: str) -> PriceObservation:
        raise self._unsupported(AdapterOperation.GET_PRICE)

    async def _get_availability(self, retailer_sku: str) -> AvailabilityObservation:
        raise self._unsupported(AdapterOperation.GET_AVAILABILITY)

    async def _get_product_identifiers(
        self, retailer_sku: str
    ) -> tuple[ProductIdentifierValue, ...]:
        raise self._unsupported(AdapterOperation.GET_PRODUCT_IDENTIFIERS)

    @abstractmethod
    async def _check_health(self) -> str | None:
        """Probe the retailer's source. Raise a `RetailerAdapterError` when unhealthy.

        Returns an optional short, non-sensitive detail string for the healthy case.
        """

    # ------------------------------------------------------------------------------ internals

    def _now(self) -> datetime:
        """Current time from the injected clock — use this for every observation timestamp."""
        return self._clock()

    def _unsupported(self, operation: AdapterOperation) -> UnsupportedOperationError:
        return UnsupportedOperationError(
            f"Operation {operation.value!r} is not supported by this adapter.",
            retailer_id=self.retailer_id,
            operation=operation.value,
        )

    def _ensure_operable(self, operation: AdapterOperation) -> None:
        if not self._enabled:
            raise AdapterDisabledError(
                "Adapter is disabled.",
                retailer_id=self.retailer_id,
                operation=operation.value,
            )
        if not self.supports(operation):
            raise self._unsupported(operation)

    def _assert_own_payload(
        self, payload: object, *, operation: AdapterOperation, payload_name: str
    ) -> None:
        """Reject a payload attributed to a different retailer.

        Cheap insurance that a mapping bug cannot smuggle one retailer's data into another's
        identity, which would corrupt comparison downstream.
        """
        retailer_id = getattr(payload, "retailer_id", None)
        if retailer_id != self.retailer_id:
            raise InvalidRetailerResponseError(
                f"{payload_name} was attributed to retailer_id={retailer_id!r} instead of "
                f"{self.retailer_id!r}.",
                retailer_id=self.retailer_id,
                operation=operation.value,
            )

    def _verify_declared_operations_are_implemented(self) -> None:
        """Fail fast when declared capabilities and implemented hooks disagree."""
        missing: list[str] = []
        undeclared: list[str] = []
        for operation, hook_name in OPERATION_HOOKS.items():
            implemented = getattr(type(self), hook_name) is not getattr(RetailerAdapter, hook_name)
            declared = operation in self._config.supported_operations
            if declared and not implemented:
                missing.append(f"{operation.value} (expected {hook_name})")
            elif implemented and not declared:
                undeclared.append(f"{operation.value} ({hook_name})")
        problems: list[str] = []
        if missing:
            problems.append(f"declared but not implemented: {', '.join(sorted(missing))}")
        if undeclared:
            problems.append(f"implemented but not declared: {', '.join(sorted(undeclared))}")
        if problems:
            raise AdapterContractError(
                f"Adapter {type(self).__name__} for retailer_id="
                f"{self._config.retailer_id!r} has an inconsistent contract — "
                f"{'; '.join(problems)}."
            )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(retailer_id={self.retailer_id!r}, "
            f"enabled={self._enabled!r}, operations="
            f"{sorted(operation.value for operation in self.supported_operations)!r})"
        )
